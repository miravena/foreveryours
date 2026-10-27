#!/usr/bin/env python3
"""Uptime monitor for the hosted demo, run by .github/workflows/uptime.yml.

    python3 scripts/uptime_check.py              # check, then open/comment/close the outage Issue
    python3 scripts/uptime_check.py --dry-run    # check, print what it WOULD do, write nothing

A probe is "up" when the Space runtime stage is RUNNING and ``GET /config`` on the
app returns 200 within the timeout. The Space is "down" only when two probes a few
minutes apart both fail, so a cold start does not page anyone.

State lives in GitHub, not on disk: the open Issue labelled ``outage`` is the
"currently down" flag. If one is open (including one a person labelled by hand) the
monitor adopts it instead of opening a second. While it stays down the monitor adds
at most one comment per COMMENT_EVERY; when the Space is back it comments the
downtime and closes the Issue. Stop labelling or close the Issue to silence it.

Uses ``urllib`` for the probes and the ``gh`` CLI (``GH_TOKEN``, ``issues: write``)
for GitHub. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

SPACE = "elevenbaselab/foreveryours"
RUNTIME_URL = f"https://huggingface.co/api/spaces/{SPACE}/runtime"
CONFIG_URL = "https://elevenbaselab-foreveryours.hf.space/config"
LABEL = "outage"
ASSIGNEES = ("elevenbaselab", "SirTehTarik")
TRACKING_ISSUE = 252
STOP_AFTER = datetime(2027, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
COMMENT_EVERY = timedelta(hours=6)
HTTP_TIMEOUT = 20
RETRY_GAP = 180
MARKER = "<!-- uptime-monitor -->"
SINCE_RE = re.compile(r"<!-- down-since: (\S+) -->")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def human(td: timedelta) -> str:
    mins = max(int(td.total_seconds() // 60), 0)
    h, m = divmod(mins, 60)
    return f"{h} h {m} min" if h else f"{m} min"


def http_get(url: str, timeout: float = HTTP_TIMEOUT) -> tuple[int, str]:
    """Return (status, body); status 0 means no HTTP answer (timeout, DNS, reset)."""
    req = urllib.request.Request(url, headers={"User-Agent": "uptime-monitor"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001 - any transport failure is "no answer"
        return 0, ""


def probe(get=http_get) -> dict:
    """One probe: {'up': bool, 'stage': str, 'config': int}."""
    code, body = get(RUNTIME_URL)
    stage = "UNKNOWN"
    if code == 200:
        try:
            stage = str(json.loads(body).get("stage") or "UNKNOWN")
        except ValueError:
            pass
    else:
        stage = f"RUNTIME_API_{code}" if code else "RUNTIME_API_UNREACHABLE"
    cfg, _ = get(CONFIG_URL)
    return {"up": stage == "RUNNING" and cfg == 200, "stage": stage, "config": cfg}


def check(get=http_get, sleep=time.sleep, gap: float = RETRY_GAP) -> dict:
    """Up if the first probe passes; otherwise probe again after ``gap`` seconds."""
    first = probe(get)
    if first["up"]:
        return first
    sleep(gap)
    second = probe(get)
    second["tries"] = 2
    return second


def evidence(r: dict) -> str:
    cfg = r["config"] or "no answer"
    return f"runtime stage `{r['stage']}`; `/config` {cfg}"


class GitHub:
    """Thin ``gh`` CLI wrapper. Reads always run; writes are skipped in dry-run."""

    def __init__(self, repo: str, dry_run: bool = False, run=subprocess.run):
        self.repo, self.dry_run, self._run = repo, dry_run, run
        self.log: list[str] = []

    def _gh(self, *args: str) -> str:
        p = self._run(["gh", *args], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args[:2])} failed: {p.stderr.strip()}")
        return p.stdout

    def _write(self, what: str) -> bool:
        self.log.append(what)
        return not self.dry_run

    def open_outage(self) -> dict | None:
        out = self._gh("issue", "list", "--repo", self.repo, "--label", LABEL,
                       "--state", "open", "--json", "number,title,body,createdAt",
                       "--limit", "1")
        items = json.loads(out or "[]")
        if not items:
            return None
        issue = items[0]
        raw = self._gh("api", f"repos/{self.repo}/issues/{issue['number']}/comments",
                       "--paginate")
        # --paginate emits one JSON array per page, back to back; decode them in turn.
        comments, dec, i, raw = [], json.JSONDecoder(), 0, raw.strip()
        while i < len(raw):
            page, i = dec.raw_decode(raw, i)
            comments += page
            while i < len(raw) and raw[i].isspace():
                i += 1
        ours = [c["created_at"] for c in comments if MARKER in (c.get("body") or "")]
        issue["last_comment"] = max(ours) if ours else None
        return issue

    def ensure_label(self) -> None:
        if self._write(f"ensure label `{LABEL}`"):
            p = self._run(["gh", "label", "create", LABEL, "--repo", self.repo,
                           "--color", "d93f0b", "--description",
                           "Live demo is down (opened by the uptime monitor)"],
                          capture_output=True, text=True)
            if p.returncode != 0 and "already exists" not in p.stderr:
                raise RuntimeError(f"gh label create failed: {p.stderr.strip()}")

    def create_issue(self, title: str, body: str) -> None:
        if self._write(f"open Issue: {title}"):
            self._gh("issue", "create", "--repo", self.repo, "--title", title,
                     "--body", body, "--label", LABEL,
                     "--assignee", ",".join(ASSIGNEES))

    def comment(self, number: int, body: str) -> None:
        if self._write(f"comment on #{number}"):
            self._gh("issue", "comment", str(number), "--repo", self.repo,
                     "--body", body)

    def close(self, number: int) -> None:
        if self._write(f"close #{number}"):
            self._gh("issue", "close", str(number), "--repo", self.repo)


def act(result: dict, gh: GitHub, now: datetime) -> str:
    """Apply the open/comment/close rules; return a one-line summary."""
    issue = gh.open_outage()
    when = iso(now)
    if result["up"]:
        if issue is None:
            return "up; no open outage Issue"
        m = SINCE_RE.search(issue.get("body") or "")
        since = parse_iso(m.group(1)) if m else parse_iso(issue["createdAt"])
        gh.comment(issue["number"],
                   f"{MARKER}\nRecovered at {when} UTC, down for {human(now - since)}. "
                   f"Now {evidence(result)}. Closing.")
        gh.close(issue["number"])
        return f"up; recovered, would close #{issue['number']}" if gh.dry_run \
            else f"up; recovered, closed #{issue['number']}"
    if issue is None:
        gh.ensure_label()
        title = f"Live demo down: {result['stage']} since {when} UTC"
        body = (f"{MARKER}\n<!-- down-since: {when} -->\n"
                f"The monitor found the hosted demo down on two checks "
                f"{RETRY_GAP // 60} minutes apart.\n\n"
                f"- Space: https://huggingface.co/spaces/{SPACE}\n"
                f"- Evidence: {evidence(result)}\n"
                f"- First seen: {when} UTC\n\n"
                f"Background: #{TRACKING_ISSUE}. This Issue closes itself when the "
                f"checks pass again. To silence it, close the Issue and remove the "
                f"`{LABEL}` label from anything you do not want adopted.")
        gh.create_issue(title, body)
        return "down; would open a new outage Issue" if gh.dry_run \
            else "down; opened a new outage Issue"
    last = parse_iso(issue["last_comment"]) if issue.get("last_comment") \
        else None
    if last is not None and now - last < COMMENT_EVERY:
        return f"down; #{issue['number']} already open, commented {human(now - last)} ago"
    gh.comment(issue["number"],
               f"{MARKER}\nStill down at {when} UTC: {evidence(result)}.")
    return f"down; adopted open #{issue['number']}" + (
        ", would comment" if gh.dry_run else ", commented")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default="miravena/foreveryours")
    ap.add_argument("--dry-run", action="store_true",
                    help="probe and read GitHub, but write nothing")
    ap.add_argument("--gap", type=float, default=RETRY_GAP,
                    help="seconds between the two probes (default %(default)s)")
    args = ap.parse_args(argv)
    now = utcnow()
    if now > STOP_AFTER:
        print("past the monitoring window; nothing to do")
        return 0
    result = check(gap=args.gap)
    gh = GitHub(args.repo, dry_run=args.dry_run)
    summary = act(result, gh, now)
    print(f"{iso(now)} {evidence(result)} -> {summary}")
    for line in gh.log:
        print(("DRY-RUN would: " if args.dry_run else "did: ") + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
