# ADR-015: During judging only `v1.0.x` patches deploy, and rollback is by tag

**Status:** Accepted (founder 2026-10-23; teammate review open on the issue)
**Date:** 2026-10-23
**Decided by:** Both maintainers (comment on the issue before the freeze)
**Affects:** `.github/workflows/deploy-space.yml` (no change), `HOW_TO_WORK_HERE.md`, `CHANGELOG.md`
**Related issue:** [#197](../../issues/197)

Amends [ADR-003](ADR-003-hosting.md).

## Question

After the Devpost submission is frozen, what may be deployed to the Space that judges open?

## Context

The submission cannot change after 2026-10-30 17:00Z, but the Project can, and the Space is what
judges open. Some judges may score from the frozen text and video alone. A deploy that adds or
changes visible behaviour can therefore only create a contradiction between the frozen text and the
live page; it cannot add points. The workflow already enforces the mechanics: after `FREEZE_UTC`
only a published Release or a manual run deploys. No document says what is allowed to ship.

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| A. Full freeze, no deploys | No drift from the text | A real regression or a safety bug stays live for six weeks | No |
| B. Patch-only on a `v1.0.x` line, with a safety exception | Fixes keep the claims already made; features wait | Needs a judgement call on each patch | No |
| C. Keep deploying from `main` | Fastest fixes | Live page drifts from the frozen text; unreviewed change under judge traffic | Yes, before the freeze |

## Decision

**We chose B.** From the freeze to the end of judging (2026-12-15):

1. **Patch-only.** Only `v1.0.x` releases deploy. Work that does not qualify as a patch stays on its
   own branch and does not merge to `main` until after 2026-12-15, because a tag deploys the whole
   tagged revision and a merged feature would ship inside the next patch. It is released as `v1.1.0`.
2. **The test for a patch.** A change is patch-eligible only if it keeps a claim the frozen
   Devpost text, video or README already makes: a judge turn that regressed, a crash, a privacy
   fix, a dependency pin, or wording that matches the submission (#204). Anything that adds a
   visible feature, or changes wording a judge could compare against the text, waits for
   `v1.1.0`. The reviewer of the patch PR quotes the claim the patch keeps.
3. **Safety exception.** A fix for a missed emergency flag or a false "family notified" claim ships
   as a patch even if it changes a reply, because the frozen text promises that behaviour.
4. **Process.** Every judging-window deploy is a published Release from a tag on `main`, runs the
   live judge check (`scripts/live_judge_check.py`), and is posted on #196 with the scorecard
   before and after.
5. **Rollback.** Re-run `deploy-space.yml` on the previous tag. The rehearsal lives in #196.

## Rationale

`docs/HACKATHON_RULES.md` section 5 says: "After it ends you may not change the Submission,
though you may keep updating the Project in your Devpost portfolio." The Project may change, but
the judged Submission may not, so a deploy that moves the live page away from the frozen text
risks a contradiction with no upside. Patches that restore a claim already made close that gap
instead of widening it, and the safety exception keeps the one promise the text makes about
people's wellbeing. The weekly check (#196) and the safety exception are the counterweight to
over-caution.

## Consequences

- **Unlocked:** a bounded, reviewable path to fix a regression during judging; a one-step rollback.
- **Locked in to:** the `v1.0.x` / `v1.1.0` release-line convention and a published Release for
  every deploy until 2026-12-15.
- **Gotchas:** a patch can widen into a feature; the "keeps a claim already made" test is the gate.
  No workflow change is needed: `FREEZE_UTC` and the Release trigger already behave this way.

## When to revisit

After 2026-12-15 (the `v1.1.0` line opens), or if the hackathon organisers change the judging
dates or the rules on post-deadline updates.
