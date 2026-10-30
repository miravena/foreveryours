# Security policy

ForeverYours handles voice and personal memories for older adults, so privacy bugs matter.

**Report privately.** Use GitHub's *Report a vulnerability* button under the Security tab
(private vulnerability reporting is on). Please don't open a public Issue for a security or
privacy problem, and don't include real personal data or API keys in any report.

In scope: leaks of one visitor's memory or audio to another, API keys or paths in repo or logs,
anything that defeats the safety fast-path or the honest-disclosure behaviour
(see [`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md)).

This is a hackathon project: we'll respond as quickly as we can but make no SLA.

Never commit `.env` or keys; secret scanning with push protection is enabled on this repo.

## Abuse limits and owner alerts

The public demo is anonymous and the owner pays for the model calls, so it limits abuse
(`guardrails.py`; every limit is an environment variable, listed in `.env.example` and the README):

- **Input size.** A typed message, a speech transcript, a caregiver memo and an interview answer each
  have a size limit, and a memo a limit on separate facts. An over-long input gets a short, friendly
  refusal before any safety scan or model call, and nothing is stored.
- **Shared budget.** Hosted model turns are limited per hour and per day across all visitors, and per
  visitor address (a salted hash held in memory only, never written to disk or a log). When a budget is
  spent the demo says it is busy; the offline safety fast path still answers, tells the senior and flags
  the family, because a safety reply is never withheld.
- **Owner alerts.** If the owner configures a webhook or e-mail address, the app sends a short
  message when usage crosses set points, a limit is hit or a visitor is throttled. It carries counts,
  the limit and a time, never anything a visitor typed, a session id, an address or a key.
- **Gradio's monitoring dashboard is off.**

These are best-effort protections for a hackathon demo, not a security boundary; counters reset when the
app restarts.
