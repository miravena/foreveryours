# ADR-003: Host the judge demo on Hugging Face Spaces

**Status:** Accepted
**Date:** 2026-10-01
**Decided by:** Team
**Affects:** `app.py`, `webapp.py`, `scripts/deploy_hf_space.py`
**Related issue:** [#11](../../issues/11)

## Question

Where do we run the app so judges can use it without their own key?

## Context

Devpost needs a live link or test build. Cloudflare Pages serves only the static landing page.

## Decision

**Hugging Face Spaces (Gradio)**, deployed with `scripts/deploy_hf_space.py`, using our own
Nebius key configured as a Space secret.

## Rationale

Free tier, Gradio-native, handles long-lived model calls. Per-visitor sessions with
auto-deletion (PR #26) keep visitors isolated and honor the no-retention privacy claim.

## Consequences

- **Gotcha:** free Spaces sleep after ~48h idle, and the sleep time cannot be configured
  (Hugging Face [Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview)); judging
  runs 2026-12-01 to 2026-12-15, five weeks after the last commit, so an un-kept Space will have
  slept long before the first judge arrives (#81 A2).
  **Keep-awake:** a daily request from any always-on machine (oracle), from deploy through
  2026-12-15:
  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' https://<user>-<space>.hf.space/
  ```
  Scheduled once a day; a non-200 means the Space needs attention before the next judge hits it.
- Needs a team Nebius key so deploying does not depend on one person's credits.

## When to revisit

Spaces cold-starts or resource limits break the demo, or we get a better free host.
