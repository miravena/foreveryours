"""Outbound caregiver notification (#201, ADR-014).

One channel, chosen by FY_NOTIFY_CHANNEL (`smtp` or `webhook`); unset means off
and nothing is constructed. The message carries the fixed category text, the
severity, whether the senior was told, a household label and a timestamp --
never a transcript, senior free text, a session id or a key. Standard library
only. `send` raises on any failure; the orchestrator's `_notify_flag` turns
that into `notified=False` on the flag.
"""
from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Callable, Protocol

DEFAULT_MAX_PER_HOUR = 6
DEFAULT_HOUSEHOLD_LABEL = "ForeverYours household"
_TIMEOUT_S = 10.0
_MAX_FIELD = 400

# Defence in depth: the flag text is already a fixed category description, but
# nothing key-shaped may ever leave the machine, so the builder scrubs it.
_KEY_SHAPED = re.compile(
    r"\b(?:sk|hf|pk|rk|nvapi|ghp|gho|ghs|xox[abp])[-_][A-Za-z0-9_-]{6,}"
    r"|\b[A-Za-z0-9+/_-]{32,}={0,2}(?![A-Za-z0-9])"
)


class NotifyError(Exception):
    """Base class; only the type name is ever recorded on a flag."""


class ConfigError(NotifyError):
    """The channel is selected but not usable (missing host, bad scheme...)."""


class DeliveryError(NotifyError):
    """The channel answered, but not with success."""


class RateLimited(NotifyError):
    """The household's hourly cap is spent."""


def _clean(text: str) -> str:
    return _KEY_SHAPED.sub("[redacted]", " ".join(str(text).split()))[:_MAX_FIELD]


@dataclass(frozen=True)
class Message:
    subject: str
    body: str
    text: str
    severity: str
    told: bool
    household: str
    timestamp: str


def build_message(flag, household_label: str = DEFAULT_HOUSEHOLD_LABEL) -> Message:
    """The only place message content is decided: category text, severity,
    told state, household label, UTC timestamp. Nothing else."""
    severity = _clean(flag.severity).lower() or "unknown"
    text = _clean(flag.text)
    label = _clean(household_label) or DEFAULT_HOUSEHOLD_LABEL
    told = bool(flag.disclosed_to_senior)
    stamp = datetime.fromtimestamp(float(flag.created_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = "\n".join([
        text,
        "",
        f"Severity: {severity.upper()}",
        f"Senior told: {'yes' if told else 'not yet confirmed'}",
        f"Household: {label}",
        f"Time: {stamp}",
        "",
        "This is a notification, not an emergency call.",
    ])
    return Message(f"ForeverYours: {severity} alert", body, text, severity, told, label, stamp)


class _HourlyCap:
    """At most `cap` sends per household key in any rolling hour."""

    def __init__(self, cap: int, clock: Callable[[], float] = time.time):
        self.cap, self._clock = cap, clock
        self._sent: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            recent = [t for t in self._sent.get(key, []) if now - t < 3600]
            if len(recent) >= self.cap:
                self._sent[key] = recent
                raise RateLimited("hourly cap reached")
            recent.append(now)
            self._sent[key] = recent


class Notifier(Protocol):
    def send(self, flag, household: str) -> None: ...


class NullNotifier:
    """Channel off: does nothing, opens nothing."""

    def send(self, flag, household: str) -> None:
        return None


class _Base:
    def __init__(self, max_per_hour: int = DEFAULT_MAX_PER_HOUR, clock=time.time,
                 household_label: str = DEFAULT_HOUSEHOLD_LABEL):
        self._cap = _HourlyCap(max_per_hour, clock)
        self.household_label = household_label

    def send(self, flag, household: str) -> None:
        self._validate()
        self._cap.take(household)
        self._deliver(build_message(flag, self.household_label))


class SmtpNotifier(_Base):
    def __init__(self, host: str = "", port: int = 587, user: str = "", password: str = "",
                 to: str = "", sender: str = "", security: str = "starttls",
                 timeout: float = _TIMEOUT_S, **kw):
        super().__init__(**kw)
        self.host, self.port, self.user, self.password = host, port, user, password
        self.to, self.sender, self.security, self.timeout = to, sender or user or to, security, timeout

    def _validate(self) -> None:
        if not (self.host and self.to):
            raise ConfigError("FY_NOTIFY_SMTP_HOST and FY_NOTIFY_TO are required")
        if self.security not in ("starttls", "ssl", "none"):
            raise ConfigError("FY_NOTIFY_SMTP_SECURITY must be starttls, ssl or none")

    def _deliver(self, msg: Message) -> None:
        mail = EmailMessage()
        mail["Subject"], mail["From"], mail["To"] = msg.subject, self.sender, self.to
        mail.set_content(msg.body)
        # Verified TLS only: the credentials and the alert must not be readable
        # by whoever impersonates the server.
        context = ssl.create_default_context()
        if self.security == "ssl":
            client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
        else:
            client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        with client as smtp:
            if self.security == "starttls":
                smtp.starttls(context=context)
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(mail)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib turns a redirected POST into a GET with no body, which would
    report success for an alert that never arrived: refuse to follow."""

    def redirect_request(self, *args, **kwargs):
        return None


def _no_redirect_opener():
    return urllib.request.build_opener(_NoRedirect)


class WebhookNotifier(_Base):
    def __init__(self, url: str = "", opener=None, timeout: float = _TIMEOUT_S, **kw):
        super().__init__(**kw)
        self.url, self.timeout = url, timeout
        self._opener = opener or _no_redirect_opener().open

    def _validate(self) -> None:
        if urllib.parse.urlparse(self.url).scheme not in ("http", "https"):
            raise ConfigError("FY_NOTIFY_WEBHOOK_URL must be an http(s) URL")

    def _deliver(self, msg: Message) -> None:
        payload = {"text": msg.text, "severity": msg.severity, "told": msg.told,
                   "household": msg.household, "timestamp": msg.timestamp}
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with self._opener(req, timeout=self.timeout) as resp:
            status = getattr(resp, "status", 200)
        if not 200 <= int(status) < 300:
            raise DeliveryError(f"webhook answered {status}")


class _Broken:
    """A selected-but-unusable channel: every send fails visibly."""

    def __init__(self, reason: str):
        self.reason = reason

    def send(self, flag, household: str) -> None:
        raise ConfigError(self.reason)


def _int(raw: str | None, default: int) -> int:
    try:
        value = int(str(raw).strip())
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def from_env() -> Notifier:
    """NullNotifier unless FY_NOTIFY_CHANNEL names a channel -- and always
    NullNotifier on a Hugging Face Space (SPACE_ID set): the hosted demo never
    holds a real caregiver address."""
    channel = (os.environ.get("FY_NOTIFY_CHANNEL") or "").strip().lower()
    if not channel or os.environ.get("SPACE_ID"):
        return NullNotifier()
    common = {
        "max_per_hour": _int(os.environ.get("FY_NOTIFY_MAX_PER_HOUR"), DEFAULT_MAX_PER_HOUR),
        "household_label": os.environ.get("FY_NOTIFY_HOUSEHOLD_LABEL") or DEFAULT_HOUSEHOLD_LABEL,
    }
    if channel == "smtp":
        return SmtpNotifier(
            host=os.environ.get("FY_NOTIFY_SMTP_HOST", ""),
            port=_int(os.environ.get("FY_NOTIFY_SMTP_PORT"), 587),
            user=os.environ.get("FY_NOTIFY_SMTP_USER", ""),
            password=os.environ.get("FY_NOTIFY_SMTP_PASSWORD", ""),
            to=os.environ.get("FY_NOTIFY_TO", ""),
            sender=os.environ.get("FY_NOTIFY_FROM", ""),
            security=(os.environ.get("FY_NOTIFY_SMTP_SECURITY") or "starttls").strip().lower(),
            **common,
        )
    if channel == "webhook":
        return WebhookNotifier(url=os.environ.get("FY_NOTIFY_WEBHOOK_URL", ""), **common)
    return _Broken("FY_NOTIFY_CHANNEL must be smtp or webhook")


_cache: tuple[tuple, Notifier] | None = None
_cache_lock = threading.Lock()
_ENV_KEYS = ("FY_NOTIFY_CHANNEL", "FY_NOTIFY_TO", "FY_NOTIFY_FROM", "FY_NOTIFY_SMTP_HOST",
             "FY_NOTIFY_SMTP_PORT", "FY_NOTIFY_SMTP_USER", "FY_NOTIFY_SMTP_PASSWORD",
             "FY_NOTIFY_SMTP_SECURITY", "FY_NOTIFY_WEBHOOK_URL", "FY_NOTIFY_MAX_PER_HOUR",
             "FY_NOTIFY_HOUSEHOLD_LABEL", "SPACE_ID")


def get_notifier() -> Notifier:
    """Process-wide `from_env()`, rebuilt when the relevant environment
    changes, so the hourly cap survives across turns."""
    global _cache
    signature = tuple(os.environ.get(k) for k in _ENV_KEYS)
    with _cache_lock:
        if _cache is None or _cache[0] != signature:
            _cache = (signature, from_env())
        return _cache[1]
