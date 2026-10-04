# Team Status: ForeverYours

**Last updated:** 2026-10-03 · **Deadline:** 2026-10-30 10:00 PDT

The single entry point for syncing. Start here, then the linked Issue, then
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Critical path

| Item | Status | Issue | Owner |
|------|--------|-------|-------|
| Narrow the "help me" false trigger | 🔴 Open, blocks deploy | [#33](../../issues/33), [#15](../../issues/15) | unassigned |
| Verify Linux TTS fix on hosted instance | 🟡 Fix landed (PR #29) | [#28](../../issues/28) | unassigned |
| Go live on HF Spaces | ⬜ Waiting on #33 and a team key | [#11](../../issues/11) | unassigned |
| Latency under 2s | 🟢 ~0.91s measured (M11); #17 stays open for first-sound measurement | [#17](../../issues/17) | unassigned |
| Demo video on hosted URL | ⬜ Waiting on #11 | [#5](../../issues/5) | unassigned |
| Devpost draft | 🟡 Text drafted | [#20](../../issues/20), [#6](../../issues/6) | unassigned |
| Memory fixes | 🟡 Open | [#32](../../issues/32), [#34](../../issues/34) | unassigned |

Milestones are tracked as [GitHub milestones](../../milestones); filter Issues by milestone for the per-milestone view.

Legend: 🟢 done · 🟡 in progress · 🔴 blocked/needs fix · ⬜ waiting on a blocker.
Put your GitHub handle in Owner when you start an item.

## Schedule (milestone due dates)

Deadline **2026-10-30 10:00 PDT**. MVP is a live URL by 10-09; 10-11 to 10-21 is the iterate
window; 10-26 onward is review and freeze, leaving two days of buffer.

| Due | Milestone | Depends on | Unblocks |
|-----|-----------|------------|----------|
| 10-05 | M10 Team Nebius key ([#36](../../issues/36)) | - | M5 |
| 10-07 | M4 Voice I/O + memory quality | - | - |
| **10-09** | **M5 Judge-accessible hosting (MVP)** | M10, [#33](../../issues/33), [#28](../../issues/28) | M11, M9, M8 |
| 10-11 | M11 Latency verified on hosted instance | M5 | M8 |
| 10-16 | M9 Representative + early Devpost draft | M5 | M13 |
| 10-21 | M8 Final demo video | M5, M11, [#21](../../issues/21) | M12, M13 |
| 10-24 | M12 Final Devpost text | M8 | M13 |
| **10-28** | **M13 Final review and submit** ([#37](../../issues/37)) | M8, M12 | - |

Order follows due date, not the M-number. See [open milestones](../../milestones).

## Blockers

Blocking is tracked on the Issues themselves with GitHub's **blocked by / blocking**
relationships (Issue sidebar -> *Relationships*), so a blocked Issue shows it and clears when
the blocker closes. Milestones cannot depend on each other; the table above is that view.
When you add a blocker, also say why in a comment.

## Where things live

| Document | Purpose | Update |
|----------|---------|--------|
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Critical path and milestones | Weekly |
| [`docs/WORK_LOG.md`](docs/WORK_LOG.md) | Dated log of what was tried, results, gotchas | After each session |
| [`docs/decisions/`](docs/decisions/README.md) | Decision log (ADRs): why each choice | When a decision is made |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, per release | In every PR |
| [`docs/PRD.md`](docs/PRD.md), [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | What and how | When scope changes |
| [`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md) | Data handling | When it changes |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | What each beat proves | When the demo changes |
| [`HOW_TO_WORK_HERE.md`](HOW_TO_WORK_HERE.md) | The workflow | Rarely |

## Sync protocol

**Before a session:** `git pull`; read open Issues and the last `WORK_LOG.md` entries.

**After a session:** add a `WORK_LOG.md` entry, comment on the Issue, update `CHANGELOG.md`
if something user-visible changed.

**Weekly (Sunday):** refresh this file's table, write ADRs for decisions made, close landed
Issues, file Issues for anything new.

## Milestones

M5 deploy (blocked on #33, team key) · M8 video (needs M5) · M9 Devpost Representative (team
decision pending) · M11 latency (done) · M12 Devpost text (done, needs final links). Full table
in the roadmap.
