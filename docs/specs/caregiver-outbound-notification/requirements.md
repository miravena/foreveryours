# PRD: The alert reaches a person (#201)

## Problem

"I'm letting your family know right now" ends in a JSON flag read by a page poll every two
seconds. The caregiver is at work, not watching a browser tab. #21 scoped one outbound channel
and closed without it; the Devpost text lists it first under "What's next" and answers judge
question 2 by admitting it.

## Users

- The caregiver: wants to know within a minute that something happened and whether Dad was
  told, from a phone, without the transcript.
- The senior: the promise "I'm letting your family know" must be true or the reply must say it
  failed.

## Scope

One channel, environment-gated, off when unset. The page keeps working without it. A
notification, never emergency dispatch (`docs/PRD.md` non-goals). Off on the hosted Space.

## Requirements

1. **Channel decision.** E-mail over SMTP, a push service, or a webhook; recorded in an ADR
   with the privacy reasoning. No third-party account on the senior's side.
2. **Content minimisation.** The message carries `CAREGIVER_FLAG_TEXT` for the category, the
   severity, and whether the senior was told. Never the transcript, never senior free text,
   never a key or a session id.
3. **Truthful state.** Sent from the same code path that persists the flag, after persisting,
   in the background. A send failure is recorded on the flag (`notified: false`, reason type
   only) and shown in the caregiver panel. The spoken line never claims more than "letting
   your family know"; the panel says "notified" or "notification failed", never "dispatched".
4. **Rate limit.** One notification per flag; a per-household cap per hour; a loop cannot
   spam a phone.
5. **Hosted default off.** The Space never holds a real caregiver address; the env var is
   unset there and the code path is covered by a test that asserts no sender is constructed.
6. **Docs.** `docs/SAFETY_AND_PRIVACY.md` and `docs/PRIVACY.md` say what leaves the system and
   to whom; the "dispatched" wording in `webapp.py` is replaced (#109).
7. **Tests.** Stubbed sender: success, failure, rate limit, and no secret-shaped string in the
   body.

## Acceptance criteria

The checkboxes on #201.

## Non-goals

No caregiver dashboard, no two-way messaging, no paid SMS gateway for the demo.

## Risks

- A notification arrives before the senior was told (the TTS path can fail). Mitigation: the
  message's "told" field is written from the flag after disclosure is recorded, and a late
  disclosure updates nothing; the message says "told: not yet confirmed" in that case.
- SMTP credentials on a laptop. Mitigation: `.env` only, `envload.load_repo_env()`, the
  pre-commit secret scan, and the no-secret-in-body test.
