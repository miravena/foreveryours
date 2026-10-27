"""Expiry for a dated memo: a fact about a named future day outlives 24 hours.

`MemoryStore.add` gives a time-marked fact ("4 PM", "today", "tomorrow") the
TEMPORARY scope and a 24 h life. That is right for a same-day errand, but wrong
for "Dr. Tan on Thursday at 10 AM" said on Monday: it would expire before the
day it matters (#248). `dated_expiry` is the deterministic rule that reads the
day words in the text itself -- the extractor's label is never trusted -- and
returns the end of the latest named future day in the household's timezone.

Rules (all relative to "today" in `tz`, never the server's clock zone):
  * "tomorrow", "day after tomorrow", "in N days": that day.
  * "<weekday>", "this <weekday>", "coming <weekday>": its next occurrence;
    the same weekday as today means today, so a same-day errand keeps 24 h.
  * "next <weekday>": that weekday of the following Mon-Sun week. "next Tuesday"
    said on a Monday is ambiguous (tomorrow, or a week on); the later reading
    keeps the fact alive for both.
  * "this week" / "next week": the end of that week (Sunday). Deliberately
    generous: a reminder that lingers a few days beats one that vanishes.
  * explicit dates: "2026-10-30", "30 October", "Oct 30th", "on the 30th".
    A named month already past is next year's, except within the last 14 days
    where it is read as a past event (no extension). A bare "the 30th" rolls
    to the next month that has that day.
  * recurring wording ("every Thursday", "Thursdays", "each Monday") and past
    wording ("last Thursday", "yesterday") name no future day and are ignored.
The result is never earlier than `now + 24 h`, so no existing fact gets shorter.
"""
from __future__ import annotations

import datetime as dt
import re
import zoneinfo

DAY_SECONDS = 24 * 3600

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEKDAY_ALIASES = {"tues": 1, "thurs": 3}
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WEEKDAY_RE = "|".join(list(_WEEKDAYS) + list(_WEEKDAY_ALIASES))
_ORD = r"(?:st|nd|rd|th)?"

_RECURRING = re.compile(r"\b(?:every|each|all|most)\s+(?:other\s+)?$")
_WEEKDAY = re.compile(rf"\b(?:(next|last|this|coming|past)\s+)?({_WEEKDAY_RE})\b")
_TOMORROW = re.compile(r"\b(day\s+after\s+)?tomorrow\b")
_IN_DAYS = re.compile(r"\bin\s+(\d{1,2})\s+days?\b")
_WEEK = re.compile(r"\b(this|next)\s+week\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_DAY = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}}){_ORD}\b(?!\s*(?::|am|pm|a\.m|p\.m))")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?({_MONTH_RE})\b")
_BARE_ORDINAL = re.compile(r"\b(?:on\s+)?the\s+(\d{1,2})(?:st|nd|rd|th)\b")


def _end_of_day(day: dt.date, tz: zoneinfo.ZoneInfo) -> float:
    """First instant of the day after `day` (local), i.e. 23:59:59.999 is still `day`."""
    return dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), tzinfo=tz).timestamp()


def _safe_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def _named_dates(text: str, today: dt.date) -> list[dt.date]:
    out: list[dt.date] = []
    for m in _ISO.finditer(text):
        d = _safe_date(int(m[1]), int(m[2]), int(m[3]))
        if d and d >= today:
            out.append(d)
    pairs = [(_MONTHS[m[1]], int(m[2])) for m in _MONTH_DAY.finditer(text)]
    pairs += [(_MONTHS[m[2]], int(m[1])) for m in _DAY_MONTH.finditer(text)]
    for month, day in pairs:
        d = _safe_date(today.year, month, day)
        if d is None:
            continue
        if d < today - dt.timedelta(days=14):
            d = _safe_date(today.year + 1, month, day)  # a named month long gone means next year's
        if d and d >= today:
            out.append(d)
    for m in _BARE_ORDINAL.finditer(text):
        day = int(m[1])
        year, month = today.year, today.month
        for _ in range(13):  # the next month that has that day (skips a 31st in a 30-day month)
            d = _safe_date(year, month, day)
            if d and d >= today:
                out.append(d)
                break
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def future_days(text: str, today: dt.date) -> list[dt.date]:
    """Every named day on or after `today` that `text` talks about (see module doc)."""
    t = text.lower()
    days: list[dt.date] = []
    for m in _TOMORROW.finditer(t):
        days.append(today + dt.timedelta(days=2 if m[1] else 1))
    for m in _IN_DAYS.finditer(t):
        days.append(today + dt.timedelta(days=int(m[1])))
    for m in _WEEKDAY.finditer(t):
        qualifier, name = m[1], m[2]
        if qualifier in ("last", "past") or _RECURRING.search(t[: m.start()]):
            continue
        target = _WEEKDAYS.index(name) if name in _WEEKDAYS else _WEEKDAY_ALIASES[name]
        if qualifier == "next":  # that weekday of NEXT calendar week (Mon-Sun)
            days.append(today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7 + target))
        else:
            days.append(today + dt.timedelta(days=(target - today.weekday()) % 7))
    for m in _WEEK.finditer(t):
        sunday = today + dt.timedelta(days=6 - today.weekday())
        days.append(sunday + dt.timedelta(days=7 if m[1] == "next" else 0))
    days.extend(_named_dates(t, today))
    return [d for d in days if d >= today]


def dated_expiry(text: str, now: float, tz_name: str = "UTC") -> float | None:
    """Epoch second at which a time-marked fact should expire, or None for the
    ordinary 24 h life (a same-day errand, or no named future day at all)."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo("UTC")
    today = dt.datetime.fromtimestamp(now, tz).date()
    days = future_days(text, today)
    if not days:
        return None
    end = _end_of_day(max(days), tz)
    return end if end > now + DAY_SECONDS else None


def expiry_label(expires_at: float, now: float, tz_name: str = "UTC") -> str:
    """The caregiver panel's words for when a Temporary fact goes: "in 4h 59m"
    inside the next 24 h, otherwise the local day and time ("Thu 23:59", or
    "Thu 30 Oct 23:59" a week or more out). An end-of-day expiry reads as
    23:59 rather than a midnight that belongs to the next day."""
    remaining = expires_at - now
    if remaining <= DAY_SECONDS:
        mins = max(1, int(remaining // 60))
        return f"in {mins}m" if mins < 60 else f"in {mins // 60}h {mins % 60}m"
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo("UTC")
    at = dt.datetime.fromtimestamp(expires_at, tz)
    if at.time() == dt.time():
        at -= dt.timedelta(minutes=1)  # midnight ends the previous day
    today = dt.datetime.fromtimestamp(now, tz).date()
    day = at.strftime("%a") if (at.date() - today).days < 7 else at.strftime("%a %d %b").replace(" 0", " ")
    return f"{day} {at:%H:%M}"
