# ADR-014: One outbound caregiver notification channel: SMTP e-mail, webhook second, off by default

**Status:** Accepted (founder 2026-10-23; teammate review open on the issue)
**Date:** 2026-10-23
**Decided by:** Team
**Affects:** `notify.py` (new), `caregiver.py` (two optional flag fields), `pipeline/orchestrator.py`, `webapp.py` (caregiver panel wording), `.env.example`
**Related issue:** [#201](../../issues/201); context [#21](../../issues/21), [#109](../../issues/109), [#117](../../issues/117)

## Question

"I'm letting your family know right now" ends today in a JSON flag read by a page poll. How does
the flag reach a caregiver who is not watching a browser tab, without a third-party account on
the senior's side, without leaking what the senior said, and without ever claiming a send that
did not happen?

## Context

- The caregiver panel already follows a privacy rule: a flag carries a fixed description of its
  category (`safety/fastpath.py` `CAREGIVER_FLAG_TEXT`), never the transcript, never the
  auditor's reason. The notification must follow the same rule.
- The product is a notification, never emergency dispatch (`docs/PRD.md` non-goals).
- The hosted Space is a throwaway demo and must never hold a real caregiver address.
- The repo is standard-library-first; a new runtime dependency needs a reason.

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| **SMTP e-mail** (default) | Works with any mailbox, no vendor SDK, no account for the senior or a judge, standard library (`smtplib`, `email.message`) | Needs SMTP credentials in `.env`; mail can land in spam | Stub server only (no real mailbox in tests) |
| **Webhook** (second) | The caregiver's own automation turns it into a phone push, chat message or SMS; standard library `urllib` | The caregiver must run the receiver | Stub opener only |
| Push service (ntfy, Pushover, FCM) | Direct phone push | A third-party account and app; a vendor sees every alert; Pushover is paid | No |
| SMS gateway (Twilio etc.) | Reaches any phone | Paid account; phone numbers to a vendor | No |

## Decision

One channel at a time, chosen by `FY_NOTIFY_CHANNEL`: `smtp` or `webhook`. **Unset means off**:
`from_env()` returns a `NullNotifier`, nothing is constructed, no socket is opened, and the
flag file and the panel behave as before. Any other value builds a notifier whose every send
fails with `ConfigError`, so a typo shows as "notification failed" instead of silent nothing.
When the process runs on a Hugging Face Space (`SPACE_ID` is set) `from_env()` returns
`NullNotifier` regardless, so the hosted demo can never send.

### Interface (fixed here so the orchestrator and the tests agree)

```python
class Notifier(Protocol):
    def send(self, flag: CaregiverFlag, household: str) -> None: ...   # raises on any failure
```

`NullNotifier`, `SmtpNotifier`, `WebhookNotifier`; `from_env()` builds one; `get_notifier()` is a
process-wide cached `from_env()` so the rate limiter survives across turns. The orchestrator
calls one helper, `_notify_flag(flags, flag, notifier=None)`, after `flags.add` returns, at the
three safety flag sites (fast-path, perseveration, AUDIT). The `severity="info"` memory-ambiguity
flag written by `MemoryStore.escalate_asked_conflicts` is not a safety event and does not notify.
The helper never raises into
the turn path; it runs on a daemon thread (or the existing AUDIT background thread) and records
the result on the flag: `notified=True`, or `notified=False` with `notify_error` set to the
exception **type name only**. With the channel off the helper returns at once and the flag
record keeps `notified=None`, which is not written to the flag file.

### What the message carries (and nothing else)

The fixed category text, the severity, whether the senior was told ("yes" or "not
yet confirmed"), a household label (`FY_NOTIFY_HOUSEHOLD_LABEL`, default "ForeverYours
household") and a UTC timestamp. It never carries the transcript, any senior free text, a session
id, a path, or a key. As defence in depth the builder replaces anything shaped like a key
(`sk-...`, `hf_...`, other vendor prefixes, long opaque tokens) with `[redacted]`. Tests assert
both the absence of transcript text and of key-shaped strings.

### Truthful state and rate limit

- One notification per flag: the helper is called once per `flags.add`.
- A per-household cap per hour (`FY_NOTIFY_MAX_PER_HOUR`, default 6), a token bucket keyed by the
  household's flag file. Over the cap the flag records `notified=False`,
  `notify_error="RateLimited"`; the panel still shows the flag.
- The panel says "notified" or "notification failed" and nothing when the channel is off; the
  word "dispatched" is gone. The spoken line stays "letting your family know".
- "Told" is read from the flag when it is persisted, after the disclosure attempt; a later
  disclosure updates nothing and the message says "not yet confirmed" in that case.

### Transport

SMTP over `starttls` (default) or `ssl` uses a certificate-verifying context
(`ssl.create_default_context()`); `none` exists only for a local relay or a test stub. The webhook
client refuses HTTP redirects: urllib would replay a redirected POST as a body-less GET and the
flag would read "notified" for an alert that never arrived.

### Secrets

SMTP credentials and the recipient live in `.env` only (`envload.load_repo_env()`), are never
logged, and never appear in the body. `.env.example` documents the variables, commented out.

## Consequences

- What leaves the system, and to whom, is documented in `docs/SAFETY_AND_PRIVACY.md` and
  `docs/PRIVACY.md`: one short fixed-text message to the caregiver's own mailbox or endpoint.
- A flag file written before this change loads unchanged; the new fields default to `None`.
- A notification can arrive before the senior's spoken disclosure finished; the "not yet
  confirmed" wording is the mitigation.
- Delivery is best effort. `notified=True` means the SMTP server or the webhook accepted the
  message, not that a person read it.

## Follow-ups and amendments

- "Told" in the message is **attested**: for the fast-path and perseveration lines it is true only
  when the streaming consumer acknowledged every audio chunk (the `_speak_disclosure` rule), and
  the acknowledgement is resolved on the notification thread so the turn never waits. Without a
  streaming consumer the message says "not yet confirmed". The panel's own "Dad was told" line is
  unchanged.
- Senders run on their own daemon threads (`TurnResult.notify_threads`), never inside
  `background_thread`, so a hung mail server cannot stall the next turn's join. Each send has an
  overall deadline (`NOTIFY_DEADLINE_S`, 30 s); past it the flag records `TimeoutError`.
- `CaregiverFlags` loading ignores unknown keys, so a flag file written by a build with more
  fields still loads on an older one.
- The chat's "Honest Safety Disclosure" line and the panel follow the channel: with no channel
  configured they call the alert a simulated caregiver alert shown on the caregiver panel; with a
  channel the panel shows the send's own status ("notification sent" or "notification failed").
- Space behaviour: with no active channel (always on the Space, or `FY_NOTIFY_CHANNEL` unset) the
  panel shows, under the latest high-priority flag, "Preview — the message Sarah would receive:" with
  the exact `notify.build_message` output (same redaction, no transcript text) and "Not sent:
  notifications are off in this demo" (Space) or "Not sent: no notification channel is set up"
  (local). Judges see the feature without anything leaving the demo. The chat line says the caregiver
  would be notified and that nothing is sent. The spoken disclosure is unchanged.

## When to revisit

A real trial household (#202) needs SMS or app push; the webhook receiver proves too much work
for a caregiver; or spam filtering makes e-mail unreliable.
