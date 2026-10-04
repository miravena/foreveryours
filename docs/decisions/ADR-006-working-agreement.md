# ADR-006: Working agreement: commits to `main`, three writers

**Status:** Accepted
**Date:** 2026-10-04
**Decided by:** Team (maintainers)
**Affects:** `CONTRIBUTING.md`, repo access, `.github/CODEOWNERS`

## Question

How do we collaborate on a shared repo under a hard deadline: PR-gated or direct commits?

## Decision

- **Direct commits to `main` are fine.** A branch + PR is for when you want the other person's
  eyes first (safety-critical code such as `safety/fastpath.py` is a good example). Reviews are
  requested, not required; no required-review branch protection.
- **Guardrails that stay on:** CI runs the tests on every push and PR; force-push and deletion
  of `main` are blocked; secret scanning with push protection is enabled.
- **Access:** `pvjthomas` keeps write access alongside the two maintainers. `CODEOWNERS` lists
  only the two maintainers, who are asked to review PRs.

## Rationale

Two or three people, 27 days, and reverting is cheap. Gating every change on review would cost
more time than it saves; the guardrails cover the failures that are expensive to undo.

## When to revisit

A bad change reaches `main` and the demo breaks, a secret is pushed, or more contributors join.
