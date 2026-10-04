# ADR-003: Host the judge demo on Hugging Face Spaces

**Status:** Accepted (not yet live; tracked in [#11](../../issues/11))
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

- **Gotcha:** free Spaces sleep and a cold first click can hang. Keep it awake through judging.
- Needs a team Nebius key so deploying does not depend on one person's credits.

## When to revisit

Spaces cold-starts or resource limits break the demo, or we get a better free host.
