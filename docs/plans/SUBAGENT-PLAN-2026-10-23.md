# Subagent plan for the submission follow-ups, 2026-10-23 (#214 to #219)

This page is **reasoning plus a dated snapshot**, not a tracker; the live state is each Issue.
It orders the six follow-ups from the submission review
([`SUBMISSION-REVIEW-2026-10-23.md`](SUBMISSION-REVIEW-2026-10-23.md)) into subagent-sized
pieces, says what each subagent gets and returns, and what only a human can do. Each piece has
its own spec folder under `docs/specs/`, written to the after-submission plan's rule: a subagent
gets the spec, the issue, `AGENTS.md` and the named files, and nothing from the conversation that
wrote them.

## The pieces

| Order | Issue | Spec | Who | Depends on | Returns |
|---|---|---|---|---|---|
| 0 | #216, #217 | done in PR #220 | human merges #220 | nothing | close both issues on merge |
| 1 | #214 model attribution + flag source | `docs/specs/space-model-attribution/` | one worker subagent, medium | #220 merged (so `main` carries the README wording the footer must agree with) | branch, tests, Codex result, PR |
| 1 (parallel) | #219 guide | `docs/specs/caregiver-conversations/` subagent A | one doc-writer subagent, low | nothing | `guide.md`, `notes-template.md` |
| 2 | #215 action-first page | `docs/specs/space-action-first/` | one worker subagent, medium | #214 landed on `main` (same file region) | branch, screenshot, tests, Codex result, PR |
| 3 | deploy | `deploy-space.yml` on merge | human merges the #214 and #215 PRs | 1 and 2 | `Build:` line, live judge check scorecard on #37 |
| 4 | #218 gallery | `docs/specs/devpost-gallery/` | one worker subagent, medium | 3 (labels in frame) | four images, captions on #218 |
| 4 (parallel) | video (#5) | `docs/VIDEO_SCRIPT.md` | founder records | 3 | public YouTube link on #5 |
| 5 | #219 paragraph | subagent B | one doc-writer subagent, medium | founder's notes (by 10-26) | PR touching the Devpost draft and README |

Three code PRs (#214, #215, gallery script), two doc PRs (guide, paragraph). Every PR is
Codex-reviewed before it is opened (REVIEW.md) and merged by a human, which is also what keeps
the Space's deploys deliberate in the last week.

## Why this order

- #214 before #215: both edit the header region of `webapp.py`; sequential lands without a
  conflict, parallel means a merge the second worker has to resolve by hand.
- The video and the gallery wait for the deploy that carries both: the footer and the try-first
  line are in frame in shots 1 to 5 and in images 1 to 3. Recording before that deploy means
  re-shooting.
- The caregiver guide is first because the calls are the long pole and only the founder can make
  them; the guide removes the preparation.

## Dates that make the video possible

- 10-24: #220 merged in the morning; #214 lands by midday; #215 lands by evening; both PRs merged
  and deployed the same day.
- 10-25: founder records on the new build; gallery subagent runs the same day.
- 10-26: founder's three calls done; paragraph PR 10-27.
- 10-29: freeze, v1.0.0, final scorecard, submit (unchanged from the final-week plan).

## Cost

Fleet boot costs: worker about 33K tokens, doc writer about 28K. Expected totals: #214 about 400K,
#215 about 350K, gallery about 150K, guide about 50K, paragraph about 80K; roughly 1M tokens, under
$10 at list price, recorded as `Cost-estimate` trailers per PR.

## Rules that do not change

One issue, one branch, one PR; tests red before green; a key only through `scripts/with_key.sh`
(none of these pieces needs one); the attribution trailers; `scripts/openai_review.sh` before a PR
is opened; media never committed; no internal tracker ids in anything pushed.
