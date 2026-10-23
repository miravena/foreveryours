# Final-week plan, 2026-10-23: what lands before the 2026-10-30 submission, and who owns it

This page is **reasoning plus a dated snapshot**, not a tracker. Per `HOW_TO_WORK_HERE.md`, work
state (open/closed, owner, due date, blocked-by) lives only on GitHub Issues and milestones, and the
Office queue holds the fleet's tickets; the verdict labels (`must-before-freeze`, `should-if-time`,
`after-submission`), milestones and priorities set from this plan are the live state. If a row here
and GitHub disagree, GitHub is right. Snapshot taken 2026-10-23 from `gh issue list --state open`
(30 issues), the fleet's Office queue (23 open ForeverYours tickets plus the planning ticket
itself; `office#` rows below, the same ids `CHANGELOG.md` already cites), and judge-check run
[39802780048](https://github.com/miravena/foreveryours/actions/runs/39802780048) (deploy of
`7fe1ad2`, 2026-10-22 15:17Z): **12 of 21 live judge turns passed**.

**Timebox.** Code freeze 2026-10-29 (founder; `#37` keeps 10-26 as the "only fixes" line). Devpost
cutoff 2026-10-30 10:00 PT / 17:00Z (`docs/ROADMAP.md`; `deploy-space.yml` `FREEZE_UTC`). Judging
2026-12-01 to 12-15 on four equally weighted criteria (`docs/HACKATHON_RULES.md` §6):
**Technological Implementation** (tie-break first), **Design**, **Potential Impact**, **Quality of
the Idea**.

**Verdict scale** (MoSCoW, for a fixed timebox): **MUST** = without it the submission is weaker on a
criterion a judge will actually exercise, or it is a submission artefact; **SHOULD** = lands before
the freeze only if the MUST list is done; **AFTER** = deferred past 2026-10-30; **CLOSE** = done,
duplicate or obsolete. Owner is who does the work: `fleet` (the Office tickets),
`teammate` (@SirTehTarik, human co-author and Devpost Representative), `founder` (elevenbaselab,
human). Protected issues (authored by or assigned to the teammate) carry owner `teammate` and are
never closed, relabelled or re-milestoned by this plan: section 4 proposes, he decides.

**What moves the score in six days.** Of the 9 failing judge turns in run 39802780048, six are on
the critical path (T05/T06 listening honesty, T09-T11 Dr. Tan memo recall, T14/T16 fall and
crisis wording) and three (T04 personalize, T15 fall-honesty, and the publish of 32 local commits
that already fix some of them) had no ticket until this plan. The video, the Devpost text and the
v1.0.0 tag are the three artefacts a judge opens; everything else is SHOULD or AFTER.

## Verdicts

| Ref | Verdict | Owner | Reason |
|---|---|---|---|
| gh#5 | MUST | founder | Design + Impact: the <=3 min video is a submission requirement (rules item 7); founder records the narration ~2026-10-24 per the #5 phone-first checklist |
| gh#11 | MUST | fleet | All four criteria score zero without the live Space through 2026-12-15; keep-awake is in ADR-003, but the cap decision and browser time-to-first-audio on the Space are still unrecorded (Office #17637) |
| gh#14 | CLOSE | fleet | Decided 2026-10-07: the canonical ChatGPT sentence is recorded on #81/#14; the remaining work is #20's text, which must carry it |
| gh#20 | MUST | fleet | Design + Idea: Devpost text due 2026-10-24 (M12); Office #23217 drafts it, both review it on the issue, the teammate pastes it |
| gh#21 | CLOSE | fleet | Done: the split-screen disclosure scene is built, hosted and confirmed as the defining moment (2026-10-07); the remaining deliverable is #5's video |
| gh#37 | MUST | teammate | Submission: freeze 2026-10-29, final live judge check on the frozen Space, Devpost form submitted by the Representative before 2026-10-30 17:00Z |
| gh#42 | AFTER | fleet | Process: attribution guardrails are warn-only by ADR-007 and not scored |
| gh#48 | SHOULD | teammate | Tech Impl: live benchmark numbers; run 39802780048 already exercises privacy (T18-T21) and crisis live, so see section 4 for a close-or-one-run proposal |
| gh#50 | AFTER | fleet | Process: pre-push hook hardening; CI re-checks every push, nothing judge-visible |
| gh#59 | AFTER | fleet | Process ADR, unanswered since 2026-10-06; not scored |
| gh#62 | AFTER | fleet | Already cut by the 2026-10-07 plan (#81); observability is not scored |
| gh#67 | SHOULD | fleet | Tech Impl: public repo hygiene (CI secret scan, rotation runbook); key_status/with_key helpers already exist |
| gh#75 | AFTER | fleet | Key custody; matters only if a rotation is needed during judging |
| gh#77 | AFTER | fleet | Offline memory fallback; the Space runs with a key, so a judge never hits this path |
| gh#89 | AFTER | fleet | English-only is stated in #20's text; other languages are past the timebox by the issue's own words |
| gh#107 | AFTER | fleet | Test and CI hygiene nits; none judge-visible |
| gh#108 | SHOULD | fleet | Tech Impl: docs that disagree with the code mislead a judge reading the repo for two minutes |
| gh#109 | SHOULD | fleet | Design: orchestrator/webapp nits a judge can see (repeated disclosure line, fake senior line) |
| gh#114 | SHOULD | fleet | Tech Impl: record the piper-tts GPL licence decision in an MIT repo before judges read `requirements.txt` |
| gh#126 | SHOULD | teammate | Tech Impl: the required Codex review already runs on fleet PRs; section 4 proposes the install lines for his machine |
| gh#130 | SHOULD | teammate | Design: judge-facing circadian labels in `docs/DEMO_SCRIPT.md` and the UI; small cleanup, his call |
| gh#133 | AFTER | teammate | Enhancement past the timebox; #132 is fixed and demo-safe |
| gh#135 | SHOULD | fleet | Tech Impl: `docs/PRD.md` non-goal contradicts the shipped bounded session history; one-paragraph fix |
| gh#138 | SHOULD | fleet | Impact honesty: `docs/PRD.md` overclaims TV-crosstalk rejection; fix the wording now, verify recordings after |
| gh#141 | AFTER | fleet | Journal hygiene; not scored |
| gh#162 | AFTER | fleet | The caregiver panel already fails closed on senior-derived facts (#174); an explicit permission flow is feature work past the timebox |
| gh#164 | AFTER | fleet | Same ground as #162: fail-closed is shipped, authorization flow deferred |
| gh#173 | SHOULD | fleet | Tech Impl: CHANGELOG contradicts the code on perseveration disclosure; one-line doc fix |
| gh#174 | SHOULD | fleet | Tech Impl: `docs/SAFETY_AND_PRIVACY.md` disagrees with the fail-closed panel; doc fix |
| gh#175 | SHOULD | fleet | Impact: `supersede()` can surface model-written text as attested; privacy fix if time, else an AFTER issue |
| gh#183 | MUST | fleet | Coordination: the single thread that tells the teammate what only he can do and by when (M13); opened by this plan |
| office#16086 | AFTER | fleet | Privacy firewall already fails closed on origin/main (#174); the explicit-permission flow is feature work past the timebox |
| office#17637 | MUST | fleet | Criteria 1-4 all need a reachable demo through 2026-12-15 (#11): keep-awake is in ADR-003 already; record the cap decision and the browser time-to-first-audio measured on the Space |
| office#21085 | AFTER | fleet | Winner study informs the next entry, not this submission |
| office#23216 | MUST | fleet | Design + Impact: the video (#5) is recorded from this script ~2026-10-24 |
| office#23217 | MUST | fleet | Design + Idea: Devpost text (#20) due 2026-10-24, carries the #14 answer; the teammate pastes it |
| office#23218 | CLOSE | fleet | Done: Load sample family shipped in PR #182 (origin/main 7fe1ad2); only AC mechanics block the ticket |
| office#23219 | MUST | fleet | Tech Impl + Idea: T05/T06 listening honesty FAIL in run 39802780048 (12/21); rule 19 is in local main 89c1ecb and needs the publish batch |
| office#23220 | MUST | fleet | Impact: T14 fall (no "are you hurt") and T16 crisis (988 twice) FAIL in run 39802780048 |
| office#23221 | AFTER | fleet | T12/T13 driving already PASS in run 39802780048; the low-severity note adds nothing a judge sees |
| office#23222 | MUST | fleet | Design: a judge must find caregiver mode and the fictional-household label on first open |
| office#23223 | CLOSE | fleet | Done: `scripts/live_judge_check.py` shipped in PR #182 and runs on every deploy; blocked only on AC date mechanics |
| office#23224 | CLOSE | fleet | Done: v0.2.0 tag adc877a and the GitHub Release were published 2026-10-22; accept so #23227's dependency clears |
| office#23225 | MUST | fleet | Tech Impl: T09-T11 Dr. Tan memo recall FAIL in run 39802780048 (memo stored as one blob) |
| office#23227 | MUST | fleet | Submission: v1.0.0 tag at the 2026-10-29 freeze is the commit the Devpost form and Release link |
| office#23229 | SHOULD | fleet | Tech Impl: memo-as-data prompt hardening is not on a judge-visible path; land if time |
| office#23230 | MUST | fleet | Impact: a chest-pain turn told to call 988 contradicts the safety pitch in one typed line |
| office#23233 | MUST | fleet | Impact: fast-path flag survives TTS failure; landed in local main 1ba4d84, ships with the publish batch |
| office#23234 | MUST | fleet | Idea: honest disclosure on every confusion reply; small fast-path wording change |
| office#23235 | MUST | fleet | Tech Impl: concurrent profile writers never lose a flag; landed in local main a4d038d, ships with the publish batch |
| office#23236 | SHOULD | fleet | Design honesty: "dispatched" overclaims; land if time, and #23216's script avoids the wording regardless |
| office#23238 | MUST | fleet | Design: two judges typing at once no longer queue; landed in local main 78602cf, ships with the publish batch |
| office#23240 | MUST | fleet | Tech Impl: caregiver fact updates supersede; landed in local main 72c9ad4, ships with the publish batch |
| office#23242 | MUST | fleet | Design: a reply that restarts or repeats its audio is the most audible defect a judge meets; landed in local main 475abd2, ships with the publish batch |
| office#23245 | MUST | fleet | This plan: the ranking, its application to Office and GitHub, and the coordination issue |
| office#23246 | MUST | fleet | Critical path step 1: publish-20261023 PR carries local main's 32 commits, the Space redeploys, scorecard on an Issue; filed by this plan |
| office#23247 | MUST | fleet | Impact: T15 fall-honesty FAIL in run 39802780048 ("I haven't told Sarah" after the flag was sent); filed by this plan |
| office#23248 | MUST | fleet | Design: T04 personalize FAIL in run 39802780048 (reply ignores the pre-brief); filed by this plan |
| office#23249 | MUST | fleet | Submission: the final live judge check on the frozen v1.0.0 Space posted on #37 with every failing turn on an Issue; filed by this plan |

The coordination issue (gh#183) and the four Office drafts filed for MUST gaps (#23246-#23249)
were created while this plan was executed and are in the table above, so it matches GitHub and
Office at merge time; four of the five allowed gap drafts were used.

## Critical path

Dates are the plan; the enforced version is each Issue's milestone and the Office priority.

1. **2026-10-23 - publish the 32 local commits.** Local `main` is 32 commits ahead of
   `origin/main` 7fe1ad2 and carries the fixes for #23219 (listening honesty, T05/T06), #23233,
   #23235, #23238, #23240, #23242 and #23237. Nothing a judge sees changes until a `publish-20261023` PR
   merges, the Actions deploy runs and the live judge check scorecard is posted on an Issue. This
   had no ticket; it is Office #23246. Fleet.
2. **2026-10-23/24 - video script, then the video.** Office #23216 rewrites `docs/VIDEO_SCRIPT.md`
   to the #5 rules (fall moment inside 10 s, one human narrator, no architecture slide, no latency
   claim); the founder records narration and the screen capture ~2026-10-24 on the live Space, and
   the public YouTube link goes on #5. Fleet writes, founder records.
3. **2026-10-24 - Devpost text (M12, #20).** Office #23217 posts the draft as a comment on #20 with
   the #14 sentence, the stack wording from `README.md`, the live URL and testing instructions, and
   adds a scored row to `docs/SELF_JUDGING.md`. Both members review on #20; the teammate pastes the
   final text into the form. Fleet drafts, teammate pastes.
4. **By 2026-10-27 - the judge-turn fixes land and publish.** On the path to a green final check:
   T05/T06 (#23219, publish), T09-T11 (#23225), T14/T16 (#23220), T15 (#23247) and T04 (#23248). Each
   publish redeploys the Space and re-runs the check. Fleet.
5. **2026-10-29 - freeze and v1.0.0.** Office #23227 renames `[Unreleased]`, tags `v1.0.0` on the
   frozen commit and publishes the Release; the Release deploy runs the live judge check
   (`deploy-space.yml` runs the suite on every deploy). Fleet, then the teammate's sanity pass.
6. **2026-10-29 - final live judge check and submit.** The scorecard from the Release deploy is
   posted on #37. **Green means every turn passes, or every failing turn is on a GitHub Issue**
   (`HOW_TO_WORK_HERE.md`, "After every Space deploy"). The teammate submits the Devpost form on
   2026-10-29, a day before the 2026-10-30 17:00Z cutoff (#37's own recommendation), and captures
   the confirmation on #37.

**Which of the 9 failing turns are on the path, and which are accepted.** On the path: T05, T06
(#23219, landed locally), T09, T10, T11 (#23225), T14, T16 (#23220), T15 (#23247) and T04 (#23248).
Accepted as known failures if still red at the 2026-10-29 check: T04 (an open-ended invitation
that does not mention the pre-brief is a softer reply, not a wrong one) and T15 (the fast-path
already told Dad the family is being notified; the contradiction is in the follow-up sentence).
Any turn still failing at the freeze is listed on #37 by number with the reply text, which is what
makes the final deploy "done" by the repo's own rule. Not accepted as known failures: T05/T06
(a false "Sarah cannot hear" answer without the safety-flag caveat is the honesty claim the whole
pitch rests on), T09-T11 (memo recall is beat 1 of the demo script) and T14/T16 (the fall scene is
the video's defining moment).

## Who owns what

Humans own what only humans can do; every item has exactly one owner.

**Fleet** (Office tickets, in priority order)
- Publish batch `publish-20261023` + Actions deploy + scorecard on an Issue (#23246) - 2026-10-23.
- `docs/VIDEO_SCRIPT.md` rewrite (#23216) - 2026-10-23, so recording can happen 2026-10-24.
- Devpost text draft on #20 + self-judging row (#23217) - 2026-10-24.
- Judge-turn fixes: #23220, #23225, #23230, #23234, #23222, #23242, #23247, #23248 - landed and
  published by 2026-10-27.
- Hosting record for #11 (#17637): cap decision and browser time-to-first-audio measured on the
  Space, added to ADR-003 next to the keep-awake it already records - 2026-10-27.
- v1.0.0 tag + Release + Release deploy (#23227) - 2026-10-29 after the freeze commit is named.
- Final scorecard and known-failure list on #37 (#23249) - 2026-10-29.
- Fleet-owned GitHub state: labels, milestones and the two CLOSE issues (#14, #21) - 2026-10-23.

**Founder** (elevenbaselab, human)
- Record the narration and the 1080p screen capture of the live Space from the rewritten script;
  upload public, unlisted-is-not-enough, to YouTube; link on #5 - 2026-10-24/25, latest 2026-10-27.
- Name the freeze commit on #37 (or on Office #23227) on 2026-10-29 so the tag is not guessed.
- Hold the Hugging Face account/token and the Nebius key through 2026-12-15 (keep-awake plan in
  ADR-003 is the fleet's; the accounts are his).

**Teammate** (@SirTehTarik, Devpost Representative) - the asks, with dates
- 2026-10-25: reply on the coordination issue #183 - agree to this split or edit it.
- 2026-10-26: review the Devpost text draft on #20 (one comment: approve or list changes).
- 2026-10-27: decide the three protected SHOULD issues (#48, #126, #130): do, hand to the fleet by
  comment, or close - see section 4.
- 2026-10-29, after the v1.0.0 Release deploy: final demo sanity pass on the frozen Space from a
  clean browser, following `docs/DEMO_SCRIPT.md`; one comment on #37 with what he saw.
- 2026-10-29: paste the final text, video link, repo link, Release link and track (Personal AI)
  into the Devpost form, submit, and post the confirmation on #37. Be reachable 2026-10-29 and
  2026-10-30 until 17:00Z in case the form or the Space needs a fix.

Rules that stay: each side merges its own PRs (the fleet's merge step refuses the other side's), the
fleet never takes over his PRs without the founder, and the coordination issue is the only place
this plan tags him.

## Proposals for teammate-owned issues

Proposals only; nothing below changes an issue he authored.

- **#48 (SHOULD) Prompt hardening against live Nemotron.** Since 2026-10-22 the live judge check
  (`scripts/live_judge_check.py`, run on every deploy) observes real model output for privacy
  (T18-T21), crisis (T16/T17) and listening honesty (T05/T06). Proposal: either close #48 as
  superseded by that suite, or run Benchmarks 2/4/6 once live with `scripts/with_key.sh` and paste
  the numbers, then close. The fleet can do the run if he comments "fleet, run it".
- **#126 (SHOULD) Make the Codex review runnable.** `scripts/openai_review.sh` already runs on
  every fleet PR (PR #182's Provenance block is one example). Proposal: add to
  `CONTRIBUTING.md` the two lines a contributor needs (`npm install -g @openai/codex`, then
  `codex login`, both outside the repo) and have the script print which prerequisite is missing;
  the fleet can land that doc change if he prefers.
- **#130 (SHOULD) Circadian labels and README disclosure wording.** Judge-facing but small.
  Proposal: he lands the two label fixes before the freeze; for the optional README sentence, the
  fleet's recommendation is to restore the crisp honest-disclosure line, because it is the #14
  answer in one sentence.
- **#133 (AFTER) Persistent delivery marker.** Proposal: milestone Backlog, label
  `after-submission`; #132 is fixed and demo-safe, so nothing here is needed for the entry.
