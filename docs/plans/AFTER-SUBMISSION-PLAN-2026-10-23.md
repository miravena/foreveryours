# After-submission plan, 2026-10-23: the judging window, then the backlog, and who owns what

This page is **reasoning plus a dated snapshot**, not a tracker. Work state (open/closed, owner,
labels, blocked-by) lives only on GitHub Issues; if a row here and GitHub disagree, GitHub is
right. Companion to [`FINAL-WEEK-PLAN-2026-10-23.md`](FINAL-WEEK-PLAN-2026-10-23.md), which
covers everything up to the 2026-10-30 cutoff. Snapshot taken 2026-10-23 after PR #187 (live
judge check 16 of 21) and the opening of #196 to #206.

**The rule that shapes this.** `docs/HACKATHON_RULES.md` section 5: after the Submission Period
ends the Submission cannot change, but the Project may keep updating; section 4: the Project
must stay available free and unrestricted to the judges until the Judging Period ends on
2026-12-15, and judges may score from the text and video alone. So "after submission" is two
windows with opposite rules:

| Window | Dates | What ships | Why |
|---|---|---|---|
| **Judging** | 2026-10-30 17:00Z to 2026-12-15 | `v1.0.x` patches only, by published Release, each one keeping a claim the frozen text already makes | A visible change can only contradict the frozen text; it cannot add points. The Space must stay up, funded and correct |
| **After judging** | from 2026-12-16 | `v1.1.0` onward: the features the Devpost text lists under "What's next", the safety long tail, privacy hardening, process debt, the retro | This is the real backlog; it starts from a known-good, judged `v1.0.0` |

Labels carry the window: `judging-window` for the first, `after-submission` for the second. The
verdict labels from the final-week plan (`must-before-freeze`, `should-if-time`) are retired by
the freeze triage (#203).

## Judging window: what is owned and by whom

| Ref | What | Owner | Spec |
|---|---|---|---|
| #196 | Keep the frozen demo alive and checked through 12-15: keep-awake, credit, HF token, weekly live judge check, daily-cap record, rollback rehearsal | founder (accounts), fleet (checks) | `docs/specs/judging-window-operations/` |
| #197 | ADR: what may deploy during judging; patch-only, the "keeps a claim already made" test, the safety exception, rollback by tag | fleet drafts, both review | `docs/specs/post-deadline-deploy-policy/` |
| #203 | Freeze triage: every red turn in the final scorecard owned, every verdict label retired | fleet, teammate for the protected issues | `docs/specs/freeze-carry-over/` |
| #204 | README, Project_Description, FEEDBACK, SAFETY_AND_PRIVACY, PRIVACY match the pasted Devpost text; `video/` retired; shipped as `v1.0.1` | fleet | `docs/specs/judge-facing-docs-drift/` |
| #75 | Nebius key issued from a shared organisation so either member can rotate it during judging (relabelled from after-submission) | founder, teammate | on the issue |

Order: #197 before the freeze (it is the rule the others follow), #203 on freeze day, #204 in the
first week of November, #196 weekly throughout, #75 before 12-01.

## After judging: what is owned and by whom

In priority order. The first three are the safety long tail that ADR-010 and the #56 live probe
measured and that the Devpost text admits; they come before any feature.

| Ref | What | Why first | Spec |
|---|---|---|---|
| #198 | Falls phrased outside the fast-path raise no flag (AUDIT on Nano misses 5 of 6 fixture falls; regex matches none) | The pitch's own scenario, unflagged | `docs/specs/fall-detection-long-tail/` |
| #199 | Crisis paraphrases return SAFE ("I don't want to be here anymore") | Highest-stakes judge phrase, admitted in the text | `docs/specs/crisis-paraphrase-backstop/` |
| #200 | AUDIT model switch rule: Super 120B recall 1.00 vs Nano 0.63 at equal false flags | Unblocks #198 cheaply; decision can be made during judging, ships in 1.1.0 | `docs/specs/audit-model-switch-rule/` |
| #201 | The alert reaches a person: one outbound caregiver channel | First item under "What's next" in the Devpost text | `docs/specs/caregiver-outbound-notification/` |
| #205 | Self-judging retro: prediction on 10-29, comparison with the real result, winner study | The only feedback that happens once | `docs/specs/self-judging-retro/` |
| #202 | One-week trial with a real caregiver and older adult | The only measurement that matters | `docs/specs/real-user-trial/` |
| #206 | Guided get-to-know-you interview mode for the caregiver | Onboarding a real caregiver needs it; feeds #202 | `docs/specs/caregiver-interview-mode/` |
| #162, #164 | Caregiver-visible facts gated independently of model classification | Privacy hardening; fail-closed already shipped | on the issues |
| #77, #89 | Offline correction fallback; languages other than English | Product gaps the text states honestly | on the issues |
| #42, #50, #59, #62, #107, #141, #193 | Process, hooks, observability, test hygiene | Not judge-visible; cheap once the pressure is off | on the issues |

## How to work any of these with subagents

Every spec folder has a `requirements.md` (the PRD: problem, users, scope, requirements,
non-goals, risks) and a `plan.md` (affected files, ordered steps, tests, and a "Splitting across
subagents" section naming which steps are independent, what each subagent needs, and what it
returns). A subagent gets the two files, the issue, `AGENTS.md` and the ADRs named in the plan,
and nothing from the conversation that wrote them. The rules that do not change: one Issue, one
branch, one PR; tests red before green; a key only through `scripts/with_key.sh`; the three
attribution trailers; `scripts/openai_review.sh` before "done"; fast-path changes need an ADR.

## What is deliberately not here

The stretch items in `docs/ROADMAP.md` that no issue owns (a Nebius AI Cloud VM, a caregiver UI
beyond the column, the early-memory-loss framing) stay stretch. A full caregiver dashboard was
cut once and stays cut (`docs/PRD.md` non-goals).
