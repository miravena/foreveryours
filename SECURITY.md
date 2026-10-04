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
