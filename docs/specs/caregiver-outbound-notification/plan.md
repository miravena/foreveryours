# Plan: The alert reaches a person (#201)

## Goal

A flag written by the orchestrator produces one minimised notification to the caregiver's
configured channel, with success or failure visible on the flag.

## Affected files

- `caregiver.py`: `CaregiverFlag` gains `notified: bool | None` and `notify_error: str | None`
  (error type only); `FlagStore.add` unchanged in signature
- `notify.py` (new): `Notifier` protocol, `SmtpNotifier` (standard library `smtplib`,
  `email.message`), `WebhookNotifier` (`urllib`), `NullNotifier`; `from_env()` returns
  `NullNotifier` when `FY_NOTIFY_CHANNEL` is unset; a per-household token bucket
- `pipeline/orchestrator.py`: after a flag is persisted (fast-path and AUDIT paths), schedule
  `notifier.send(flag)` on the existing background thread, then update the flag record
- `webapp.py`: panel text "notified" / "notification failed" / nothing when off; remove
  "DISPATCHED"
- `.env.example`: `FY_NOTIFY_CHANNEL`, `FY_NOTIFY_TO`, SMTP host/port/user vars, documented
  as optional
- `tests/test_notify.py` (new), `tests/test_orchestrator.py`, `tests/test_webapp.py`
- `docs/decisions/ADR-0xx-outbound-notification.md`, `docs/SAFETY_AND_PRIVACY.md`,
  `docs/PRIVACY.md`, `CHANGELOG.md`

## Steps

1. ADR first (issue-first rule): channel choice and the privacy rules above. Recommend SMTP
   as default (no vendor, works with any mailbox) and webhook as the second, for a phone push
   via the caregiver's own automation.
2. `notify.py` with the three notifiers, `from_env()`, the message builder (category text,
   severity, told state, household label, timestamp; nothing else), and the rate limiter.
3. Orchestrator hook: both flag sites call one helper `_notify_flag(flag_store, flag)`; the
   helper never raises; failures set `notified=False` and `notify_error=type(e).__name__`.
4. Panel wording; `.env.example`.
5. Tests red-then-green: message body contains no transcript substring and no `sk-`/`hf_`
   shaped string; `NullNotifier` when unset; rate limit; failure recorded; `webapp` panel
   shows the three states.
6. Docs, CHANGELOG, `scripts/openai_review.sh`, `scripts/smoke.sh`.

## Tests

`tests/test_notify.py` for the module; orchestrator tests with a stub notifier on the fast-path
and the AUDIT path; a webapp test that the hosted default constructs no sender; the privacy
benchmark (`tests/test_mature_benchmarks.py` Benchmark 4) still green.

## Splitting across subagents

- Subagent A: step 1 (ADR draft) and step 2 (`notify.py` + `tests/test_notify.py`), offline.
- Subagent B (after A's interface is fixed in the ADR): steps 3 to 5, orchestrator and webapp.
- Subagent C: step 6 docs.
Each needs this file, #201, `caregiver.py`, the orchestrator's flag sites, and
`docs/SAFETY_AND_PRIVACY.md`. No subagent needs a real mailbox; SMTP is tested with a stub
server (`smtpd`-style thread or a fake transport).

## Review

Privacy-relevant: different-vendor review per REVIEW.md and `scripts/openai_review.sh`.
