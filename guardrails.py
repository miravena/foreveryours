"""Abuse guardrails and owner alerts for the public web demo (#37).

The demo is anonymous and free for judges, so a deliberate script could (1) freeze
the app with one huge typed input, (2) burn the owner's Nebius credits by opening
unlimited sessions (the 50-a-day cap is per session) or (3) block every visitor's
memo saves with a huge memo. This module is the small, dependency-free answer:

* input caps (`input_refusal`, `memo_refusal`), checked before any model, safety
  or store work;
* a process-wide budget for hosted (Nebius) turns plus per-client limits
  (`admit_hosted_turn`). Running out never blocks a safety reply: webapp.py
  withholds only THINK, AUDIT and extraction, exactly like the per-session cap;
* owner alerts (`OwnerAlerts`) through notify.py's SMTP and HTTP transports, off
  unless configured, rate limited, counts and a timestamp only.

Everything is in memory (a restart resets it) and every limit is an environment
variable with a generous default (see `.env.example`). Standard library only.
Nothing here stores a transcript, a session id, an IP address or a key.
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import ipaddress
import os
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

import notify

_HOUR = 3600.0
_MAX_TRACKED_CLIENTS = 5000

# Messages the visitor sees. Warm, short, and clear that nothing was sent or saved.
INPUT_REFUSAL = ("That is a lot to take in at once ({n} characters; the limit is {cap}). "
                 "Could you say it in a few shorter sentences? Nothing was sent.")
MEMO_CHARS_REFUSAL = ("That note is too long to save in one go ({n} characters; the limit is {cap}). "
                      "Please split it into shorter notes. Nothing was saved.")
MEMO_FACTS_REFUSAL = ("That note has {n} separate facts; the limit is {cap} at once. "
                      "Please save it in smaller notes. Nothing was saved.")
BUSY_REPLY = "The demo is busy right now -- please try again shortly."


def _env_int(env, name: str, default: int) -> int:
    """A positive integer, else `default` (blank, text, zero and negatives all fall back)."""
    try:
        value = int(str(env.get(name, "")).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class Ticket:
    """One admitted hosted turn: what `refund_hosted_turn` takes back, so a
    refund removes exactly its own entry even when other turns were admitted since."""
    at: float
    day: datetime.date
    client: str | None


@dataclass(frozen=True)
class Config:
    max_input_chars: int = 2000
    max_memo_chars: int = 2000
    max_memo_facts: int = 30
    global_turns_per_hour: int = 600
    global_turns_per_day: int = 3000
    client_turns_per_hour: int = 120
    client_new_sessions_per_hour: int = 30
    alert_refusals_per_hour: int = 20
    owner_alerts_per_hour: int = 6
    client_ip_source: str = "auto"  # auto | peer | forwarded | off

    @classmethod
    def from_env(cls, env=os.environ) -> "Config":
        d = cls()
        source = (env.get("FY_CLIENT_IP_SOURCE") or "auto").strip().lower()
        return cls(
            max_input_chars=_env_int(env, "FY_MAX_INPUT_CHARS", d.max_input_chars),
            max_memo_chars=_env_int(env, "FY_MAX_MEMO_CHARS", d.max_memo_chars),
            max_memo_facts=_env_int(env, "FY_MAX_MEMO_FACTS", d.max_memo_facts),
            global_turns_per_hour=_env_int(env, "FY_GLOBAL_TURNS_PER_HOUR", d.global_turns_per_hour),
            global_turns_per_day=_env_int(env, "FY_GLOBAL_TURNS_PER_DAY", d.global_turns_per_day),
            client_turns_per_hour=_env_int(env, "FY_CLIENT_TURNS_PER_HOUR", d.client_turns_per_hour),
            client_new_sessions_per_hour=_env_int(
                env, "FY_CLIENT_NEW_SESSIONS_PER_HOUR", d.client_new_sessions_per_hour),
            alert_refusals_per_hour=_env_int(env, "FY_ALERT_REFUSALS_PER_HOUR", d.alert_refusals_per_hour),
            owner_alerts_per_hour=_env_int(env, "FY_OWNER_ALERTS_PER_HOUR", d.owner_alerts_per_hour),
            client_ip_source=source if source in ("auto", "peer", "forwarded", "off") else "auto",
        )


# --------------------------------------------------------------------------- client identity

def _parse_ip(raw: str):
    """An ip_address from an `X-Forwarded-For` token (optionally with a port or
    brackets), or None if it is not an IP at all."""
    token = (raw or "").strip().strip('"')
    if not token:
        return None
    candidates = [token]
    if token.startswith("[") and "]" in token:
        candidates.append(token[1:token.index("]")])
    elif token.count(":") == 1:  # "1.2.3.4:5678"
        candidates.append(token.split(":", 1)[0])
    for cand in candidates:
        try:
            return ipaddress.ip_address(cand)
        except ValueError:
            continue
    return None


def _header(request, name: str) -> str | None:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get(name)
        if value is not None:
            return str(value)
        for key, val in headers.items():  # a plain dict from some Gradio environments
            if str(key).lower() == name:
                return str(val)
    except Exception:
        return None
    return None


def forwarded_client_ip(header_value: str | None) -> str | None:
    """The visitor's address from an `X-Forwarded-For` value.

    The header is a list that each proxy APPENDS the address it received the
    request from, while a visitor can send any prefix they like. So the leftmost
    entries are forgeable and only the right-hand ones were written by our own
    infrastructure. Walk from the right, skip internal hops (private, loopback,
    link-local, CGNAT: Space-internal proxies), and take the first public
    address: the outermost trusted proxy's view of the real peer. A forged prefix
    is therefore never used, and one visitor cannot pick another's key. If an
    entry on that walk is not an IP, or none is public, there is no reliable
    answer and the caller skips per-client limits."""
    if not header_value:
        return None
    for token in reversed([t for t in str(header_value).split(",")]):
        ip = _parse_ip(token)
        if ip is None:
            return None
        if ip.is_global:
            return str(ip)
    return None


def client_ip(request, source: str = "auto", on_space: bool | None = None) -> str | None:
    """The visitor's IP address, or None when it cannot be determined reliably.

    Why not `request.client.host` on a Hugging Face Space: the Space sits behind
    Hugging Face's reverse proxy, so the socket peer is the proxy, the same for
    every visitor, and keying on it would throttle all judges together. The proxy
    chain reports the real peer in `X-Forwarded-For`, read by
    `forwarded_client_ip` (right to left, so a visitor's own header cannot choose
    the key). `X-Real-IP` is not used: nothing guarantees the proxy overwrites
    it, so a visitor could set it. Off a Space there is no proxy of ours, the
    socket peer IS the visitor, and forwarded headers are never trusted (they
    are plain visitor input). `source` overrides this: `forwarded`, `peer`,
    `off`."""
    if source == "off" or request is None:
        return None
    if on_space is None:
        on_space = bool(os.environ.get("SPACE_ID"))
    mode = source if source in ("peer", "forwarded") else ("forwarded" if on_space else "peer")
    if mode == "forwarded":
        return forwarded_client_ip(_header(request, "x-forwarded-for"))
    host = getattr(getattr(request, "client", None), "host", None)
    ip = _parse_ip(host or "")
    return str(ip) if ip is not None else None


# --------------------------------------------------------------------------- owner alerts

# kind -> (subject, reason, noisy). The text is fixed here: nothing a visitor typed,
# no session id, no IP and no client hash can reach an alert. Counts are ints.
_EVENTS: dict[str, tuple[str, str, bool]] = {
    "daily_50": ("daily budget 50%", "Hosted turns today have reached 50% of the daily budget.", False),
    "daily_80": ("daily budget 80%", "Hosted turns today have reached 80% of the daily budget.", False),
    "daily_100": ("daily budget used up",
                  "The daily hosted-turn budget is used up. Until it resets (00:00 UTC) the demo answers "
                  "'busy'; safety replies still work.", False),
    "hourly_cap": ("hourly cap reached",
                   "The hourly hosted-turn cap was hit. Turns are answered 'busy' until the hour rolls over; "
                   "safety replies still work.", False),
    "client_throttled": ("a visitor was throttled",
                         "One visitor went over the per-visitor limit and is being answered 'busy' for a while.",
                         True),
    "refusals_high": ("many oversize inputs",
                      "Oversize typed inputs or memos are being refused unusually often.", True),
}


class OwnerAlerts:
    """Tells the owner about abuse. Off unless a webhook (FY_OWNER_ALERT_WEBHOOK, e.g.
    an ntfy.sh topic URL: it takes a plain POST body) or SMTP settings
    (FY_OWNER_ALERT_SMTP_HOST + FY_OWNER_ALERT_TO) are set. At most
    `per_hour` alerts an hour (noisy kinds at most half of that, so a flood of
    throttled visitors cannot starve the budget alerts). Delivery runs in a
    background thread and a failure only logs its exception type."""

    def __init__(self, per_hour: int = 6, clock: Callable[[], float] = time.time,
                 sender: Callable[[str, str], None] | None = None,
                 spawn: Callable[[Callable[[], None]], None] | None = None,
                 env=None):
        self.per_hour, self._clock = per_hour, clock
        self._sender, self._spawn, self._env = sender, spawn, env
        self._sent: collections.deque = collections.deque()  # (timestamp, noisy)
        self._lock = threading.Lock()

    # -- configuration -------------------------------------------------------
    def _environ(self):
        return self._env if self._env is not None else os.environ

    def _transports(self) -> list[Callable[[str, str], None]]:
        if self._sender is not None:
            return [self._sender]
        env, out = self._environ(), []
        url = (env.get("FY_OWNER_ALERT_WEBHOOK") or "").strip()
        if url:
            def post(subject: str, body: str, url=url) -> None:
                notify.post_http(url, body.encode("utf-8"),
                                 {"Content-Type": "text/plain; charset=utf-8",
                                  "Title": subject.encode("ascii", "replace").decode("ascii"),
                                  "Tags": "warning"})
            out.append(post)
        host, to = (env.get("FY_OWNER_ALERT_SMTP_HOST") or "").strip(), (env.get("FY_OWNER_ALERT_TO") or "").strip()
        if host and to:
            security = (env.get("FY_OWNER_ALERT_SMTP_SECURITY") or "starttls").strip().lower()
            if security not in ("starttls", "ssl", "none"):
                security = "starttls"  # a typo must never fall through to plaintext login

            def mail(subject: str, body: str) -> None:
                user = env.get("FY_OWNER_ALERT_SMTP_USER", "")
                notify.send_smtp(
                    host, _env_int(env, "FY_OWNER_ALERT_SMTP_PORT", 587), user,
                    env.get("FY_OWNER_ALERT_SMTP_PASSWORD", ""),
                    (env.get("FY_OWNER_ALERT_FROM") or user or to).strip(), to,
                    security, subject, body)
            out.append(mail)
        return out

    def configured(self) -> bool:
        return bool(self._transports())

    # -- emitting ------------------------------------------------------------
    def emit(self, kind: str, counts: dict[str, int]) -> str:
        """Log the event (always) and send the alert if configured and under the
        rate limit. Returns "sent", "suppressed" or "not_configured". Never raises."""
        try:
            subject, reason, noisy = _EVENTS[kind]
            counts = {str(k): int(v) for k, v in counts.items()}
            stamp = datetime.datetime.fromtimestamp(self._clock(), tz=datetime.timezone.utc)
            transports = self._transports()
            state = "not_configured"
            if transports:
                state = "sent" if self._take(noisy) else "suppressed"
            print(f"[guardrails] event={kind} alert={state} "
                  + " ".join(f"{k}={v}" for k, v in sorted(counts.items())), file=sys.stderr)
            if state == "sent":
                body = "\n".join([
                    notify.scrub(reason),
                    "",
                    *[f"{k}: {v}" for k, v in sorted(counts.items())],
                    f"Time: {stamp.strftime('%Y-%m-%d %H:%M UTC')}",
                ])
                title = "ForeverYours demo: " + subject
                self._run(lambda: self._deliver(transports, title, body))
            return state
        except Exception as exc:  # an alert must never affect a turn
            print(f"[guardrails] alert failed: {type(exc).__name__}", file=sys.stderr)
            return "suppressed"

    def _take(self, noisy: bool) -> bool:
        now = self._clock()
        with self._lock:
            while self._sent and now - self._sent[0][0] >= _HOUR:
                self._sent.popleft()
            if len(self._sent) >= self.per_hour:
                return False
            if noisy and sum(1 for _, n in self._sent if n) >= max(1, self.per_hour // 2):
                return False
            self._sent.append((now, noisy))
            return True

    def _run(self, fn: Callable[[], None]) -> None:
        if self._spawn is not None:
            self._spawn(fn)
        else:
            threading.Thread(target=fn, name="owner-alert", daemon=True).start()

    @staticmethod
    def _deliver(transports, title: str, body: str) -> None:
        for send in transports:
            try:
                send(title, body)
            except Exception as exc:  # type name only: a message can carry a URL
                print(f"[guardrails] alert delivery failed: {type(exc).__name__}", file=sys.stderr)


# --------------------------------------------------------------------------- the guard

class Guardrails:
    """Input caps, the process-wide hosted-turn budget and per-client limits.
    Thread-safe; `clock` is injectable for tests."""

    def __init__(self, config: Config | None = None, clock: Callable[[], float] = time.time,
                 alerts: OwnerAlerts | None = None, salt: bytes | None = None,
                 on_space: bool | None = None):
        self.config = config or Config.from_env()
        self._clock = clock
        self.alerts = alerts or OwnerAlerts(self.config.owner_alerts_per_hour, clock)
        self._salt = salt if salt is not None else secrets.token_bytes(16)  # per process, never persisted
        self._on_space = on_space
        self._lock = threading.Lock()
        self._hour: collections.deque = collections.deque()  # admitted hosted turns, last hour
        self._day: datetime.date | None = None
        self._day_count = 0
        self._day_fired: set[int] = set()
        self._hour_alerted = False
        self._refusals: collections.deque = collections.deque()
        self._refusals_alerted = False
        self._clients: dict[str, dict] = {}  # hash -> {"turns": deque, "sessions": deque, "alerted": float, "seen": float}
        self._ip_path_logged = False

    # -- input caps ----------------------------------------------------------
    def input_refusal(self, text: str | None) -> str | None:
        """Refusal text for a typed message or ASR transcript over the cap, else None."""
        n = len(text or "")
        if n <= self.config.max_input_chars:
            return None
        self._note_refusal()
        return INPUT_REFUSAL.format(n=n, cap=self.config.max_input_chars)

    def memo_refusal(self, text: str | None, count_facts: Callable[[str], int]) -> str | None:
        """Refusal text for a memo (typed, dictated or an interview answer) over
        the character or fact cap, else None. `count_facts` runs only on text
        already under the character cap, so a huge memo never reaches the splitter."""
        n = len(text or "")
        if n > self.config.max_memo_chars:
            self._note_refusal()
            return MEMO_CHARS_REFUSAL.format(n=n, cap=self.config.max_memo_chars)
        facts = count_facts(text or "")
        if facts > self.config.max_memo_facts:
            self._note_refusal()
            return MEMO_FACTS_REFUSAL.format(n=facts, cap=self.config.max_memo_facts)
        return None

    def _note_refusal(self) -> None:
        now, fire = self._clock(), None
        with self._lock:
            self._refusals.append(now)
            while self._refusals and now - self._refusals[0] >= _HOUR:
                self._refusals.popleft()
            count = len(self._refusals)
            if count > self.config.alert_refusals_per_hour:
                if not self._refusals_alerted:
                    self._refusals_alerted = True
                    fire = {"refusals_last_hour": count, "threshold": self.config.alert_refusals_per_hour}
            else:
                self._refusals_alerted = False
        if fire:
            self.alerts.emit("refusals_high", fire)

    # -- client identity -----------------------------------------------------
    def client_key(self, request) -> str | None:
        """A salted hash of the visitor's IP, or None if it cannot be determined
        reliably (per-client limits are then skipped; the global ones still apply)."""
        try:
            ip = client_ip(request, self.config.client_ip_source, self._on_space)
        except Exception:
            return None
        if not self._ip_path_logged:  # once, no address: lets the owner see the source works
            self._ip_path_logged = True
            print(f"[guardrails] client identity: source={self.config.client_ip_source} "
                  f"resolved={'yes' if ip is not None else 'no'}", file=sys.stderr)
        if ip is None:
            return None
        return hashlib.sha256(self._salt + ip.encode("ascii")).hexdigest()[:16]

    def _client(self, key: str, now: float) -> dict:
        rec = self._clients.get(key)
        if rec is None:
            if len(self._clients) >= _MAX_TRACKED_CLIENTS:
                self._prune_clients(now)
            rec = self._clients[key] = {"turns": collections.deque(), "sessions": collections.deque(),
                                        "alerted": None, "seen": now}
        rec["seen"] = now
        return rec

    def _prune_clients(self, now: float) -> None:
        for key in [k for k, r in self._clients.items() if now - r["seen"] >= _HOUR]:
            del self._clients[key]
        if len(self._clients) >= _MAX_TRACKED_CLIENTS:  # still full: drop the stalest quarter
            stale = sorted(self._clients, key=lambda k: self._clients[k]["seen"])
            for key in stale[: _MAX_TRACKED_CLIENTS // 4]:
                del self._clients[key]

    @staticmethod
    def _trim(dq: collections.deque, now: float) -> None:
        while dq and now - dq[0] >= _HOUR:
            dq.popleft()

    def note_new_session(self, client: str | None) -> None:
        """Count a session started by this client. It never blocks the page load;
        too many in an hour makes the client's turns answer 'busy'."""
        if client is None:
            return
        now = self._clock()
        with self._lock:
            rec = self._client(client, now)
            rec["sessions"].append(now)
            self._trim(rec["sessions"], now)

    # -- hosted-turn budget --------------------------------------------------
    def admit_hosted_turn(self, client: str | None) -> bool:
        """`admit(client)` without the ticket: whether this turn may spend a hosted call."""
        return self.admit(client)[0]

    def admit(self, client: str | None) -> tuple[bool, Ticket | None]:
        """Whether this turn may spend a hosted (Nebius) call, and the ticket to
        refund it with. Counts the turn when it may. False means "answer busy":
        the caller keeps the offline safety fast path and withholds only the paid
        continuation. Never raises: an accounting bug lets the turn through."""
        try:
            ticket, events = self._admit(client)
        except Exception as exc:  # a bug in accounting must not take the demo down
            print(f"[guardrails] budget check failed: {type(exc).__name__}", file=sys.stderr)
            return True, None
        for kind, counts in events:  # outside the lock; emit() never raises
            self.alerts.emit(kind, counts)
        return ticket is not None, ticket

    def _admit(self, client: str | None) -> tuple[Ticket | None, list]:
        cfg, now, events = self.config, self._clock(), []
        today = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).date()
        with self._lock:
            if today != self._day:
                self._day, self._day_count, self._day_fired = today, 0, set()
            self._trim(self._hour, now)
            rec = None
            if client is not None:
                rec = self._client(client, now)
                self._trim(rec["turns"], now)
                self._trim(rec["sessions"], now)
                over_turns = len(rec["turns"]) >= cfg.client_turns_per_hour
                over_sessions = len(rec["sessions"]) > cfg.client_new_sessions_per_hour
                if over_turns or over_sessions:
                    if rec["alerted"] is None or now - rec["alerted"] >= _HOUR:
                        rec["alerted"] = now
                        events.append(("client_throttled", {
                            "turns_last_hour": len(rec["turns"]),
                            "turn_limit": cfg.client_turns_per_hour,
                            "new_sessions_last_hour": len(rec["sessions"]),
                            "new_session_limit": cfg.client_new_sessions_per_hour,
                            "clients_tracked": len(self._clients)}))
                    return None, events
            if len(self._hour) >= cfg.global_turns_per_hour:
                if not self._hour_alerted:
                    self._hour_alerted = True
                    events.append(("hourly_cap", {"turns_last_hour": len(self._hour),
                                                  "hourly_cap": cfg.global_turns_per_hour,
                                                  "turns_today": self._day_count,
                                                  "daily_cap": cfg.global_turns_per_day}))
                return None, events
            if self._day_count >= cfg.global_turns_per_day:
                if 100 not in self._day_fired:  # also covers a cap lowered mid-day
                    self._day_fired.add(100)
                    events.append(("daily_100", self._daily_counts()))
                return None, events
            self._hour_alerted = False  # room again: arm the hourly alert for the next time
            self._hour.append(now)
            self._day_count += 1
            if rec is not None:
                rec["turns"].append(now)
            pct = self._day_count * 100 // cfg.global_turns_per_day
            for step in (50, 80, 100):
                if pct >= step and step not in self._day_fired:
                    self._day_fired.add(step)
                    events.append((f"daily_{step}", self._daily_counts()))
            return Ticket(now, today, client), events

    def _daily_counts(self) -> dict[str, int]:
        return {"turns_today": self._day_count, "daily_cap": self.config.global_turns_per_day,
                "turns_last_hour": len(self._hour), "hourly_cap": self.config.global_turns_per_hour}

    def refund_hosted_turn(self, ticket: Ticket | None) -> None:
        """Undo one `admit`, when a later check (the per-session cap) turned the
        same turn away, so it does not eat the shared budget. Removes that
        ticket's own entries, never a newer turn's."""
        if ticket is None:
            return
        with self._lock:
            try:
                self._hour.remove(ticket.at)
                if ticket.day == self._day:
                    self._day_count = max(0, self._day_count - 1)
            except ValueError:
                pass  # already aged out of the window
            rec = self._clients.get(ticket.client) if ticket.client is not None else None
            if rec is not None:
                try:
                    rec["turns"].remove(ticket.at)
                except ValueError:
                    pass


GUARDRAILS = Guardrails()
