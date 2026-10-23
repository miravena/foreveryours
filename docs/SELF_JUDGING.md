# Self-judging: score our own mock submissions before a real judge does

Why this exists: with 29 days and a 2-person team, waiting for a real Devpost judge is the
only feedback loop we don't control and the only one that happens exactly once. A mock
submission — the current repo + whatever demo/video exists, even unfinished — scored against
the real rubric, as often as we want, is how we find out we're weak on Design *before*
submission instead of after. Score early, score often, score honestly.

## Who scores what

- **Both of you score independently first, then compare.** Comparing after, not before, is the
  point — one of you might see something as obviously fine that the other flags, and you want
  that disagreement visible, not averaged away.
- **The founder's job in this process is the same as with a real judge: direction, not just
  grading.** Low scores plus a clear "what's the single highest-leverage fix" beat a precise
  number — see the "founder call" row in the log below.
- The teammate scoring this is also how a newer builder learns to read code/product the way a
  judge will — treat disagreements in scores as the interesting part, not noise to resolve
  quickly.

## The rubric (mirrors Devpost's actual four, equally weighted)

Score each 1–5. Don't round up to be nice — a 3 you can act on beats a 4 you can't justify to
a stranger.

### 1. Technological Implementation
- [ ] Does the demo actually run, end to end, right now, without us explaining it first?
- [ ] Is there a real engineering decision here a judge would notice (not just "we called an
      API")? (Candidates: streamed TTS/latency design, the fast-path safety net, session
      history — see `docs/ROADMAP.md`.)
- [ ] Would reading the code for 2 minutes change a skeptical judge's mind, or confirm their
      skepticism?

### 2. Design
- [ ] Does the demo *look and sound* like the product it claims to be, or like a prototype
      wearing the idea as a costume? (Robotic TTS, a bare terminal, etc. count against this —
      see issue #17/VENDOR_DECISIONS.md.)
- [ ] Is there one moment in under 30 seconds that's clearly the point of the product? (The
      split-screen disclosure beat from issue #21 is our current bet on this — does it land?)
- [ ] Would a judge understand what's happening with the sound off, from visuals alone?

### 3. Potential Impact
- [ ] Is there a specific scenario (not "eldercare is important") that makes the stakes
      concrete? (See issue #14/#21's "ChatGPT sympathizes and moves on, nobody's told" scenario
      — is it actually in the pitch yet, or still just an idea in an issue thread?)
- [ ] Does the demo show the *caregiver* benefiting, not just the senior? (Two-sided value is
      the actual differentiator — a demo that only shows the senior's side undersells it.)

### 4. Quality of the Idea
- [ ] If a judge asks "why not just use ChatGPT voice mode," do we have an answer that's a
      scenario, not an architecture diagram? (Issue #14.)
- [ ] Is there anything in the current build that reads as generic "AI wrapper," and if so,
      is that the fast-path, the memory, or something else specifically?

## Mock submission checklist

A "mock submission" doesn't need to be finished — it needs to be gradeable the way a real judge
would grade it. At minimum:
- [ ] Something runs live (CLI beats or `webapp.py` — whichever exists at the time)
- [ ] A rough video walkthrough exists, even a phone recording of a terminal/screen — doesn't
      need to be the final `<=3min` cut
- [ ] A one-paragraph pitch draft exists, even rough

If any of those three don't exist yet, the mock is really "review the plan," which is still
useful but is a different exercise — note that in the log instead of forcing a score.

## Score log

Append a row after each mock pass. Keep every row — the trend matters more than any single
score.

| Date | What was scored | Tech Impl | Design | Impact | Idea | Total /20 | Biggest single gap | Next action |
|---|---|---|---|---|---|---|---|---|
| 2026-10-01 | Repo + webapp.py (not hosted, not yet in a real browser) | — | — | — | — | — | *(not yet scored — do this once webapp.py is actually clicked through in a browser, not just backend-tested)* | Host + browser-test webapp.py, then run the first real mock score |
| 2026-10-23 | docs/DEVPOST_DRAFT.md @ main `b7d3d82` (first written in `faed145`) + live Space build `e5d436e` (four typed turns through its public API) + repo. Mock checklist: runs live yes; video no (#5 open, only the CLI proof-of-concept clip exists); pitch paragraph yes. One scorer (AI-assisted), second human score pending | 3 | 3 | 3 | 4 | 13 | The Space runs a build behind `main`, so the hosted demo says "Caregiver notified" when nothing is sent, and it invented details about Leo | Publish `main` and redeploy the Space, then re-score text + new build + video |

### Gaps (2026-10-23, docs/DEVPOST_DRAFT.md)

What the Space showed on 2026-10-23 (build `e5d436e`, typed turns "What's happening today?",
"Tell me about my grandson.", "I fell down earlier and I'm scared", "I don't want to be here
anymore"), and what costs points. One line each: rubric item, then the proposed fix.

- Space build `e5d436e` is behind local `main` (the #201 simulated-alert labels, #211 911 reply,
  #198/#191 fall and crisis wording are not live). *Technological Implementation.* Fix: publish
  `main`, redeploy, check the new `Build:` line, re-run this pass.
- The caregiver column says "HIGH PRIORITY SAFETY ALERT DISPATCHED" and "Status: Caregiver
  notified", and the senior side says "Caregiver notified with Dad's knowledge", but nothing is
  sent. Contradicts the honesty pitch. *Design, Quality of the Idea.* Fix: the #201 labels already
  on `main`; redeploy.
- "Tell me about my grandson." got "he's 10 years old and loves dinosaurs. He visited you last
  weekend and you baked cookies together", none of it in the briefing. *Technological
  Implementation.* Fix: confirm THINK rule 20 stops it on a live turn after redeploy; add that
  question to a live probe.
- The crisis turn said the apology and the 988 line twice (fast-path, then the model
  continuation). *Design.* Fix: #191 on `main`; redeploy and recheck.
- The first turn of a fresh session printed "Your demo household was reset after a period of
  inactivity." *Design.* Fix: show the reset note only when an earlier session really expired.
- End to end through the public API, the four typed turns took 7.9, 5.8, 8.8 and 10.2 s (single
  runs, from oracle), slower than ADR-003's 1.9 to 6.4 s. *Technological Implementation.* Fix:
  measure browser time to first audio on the Space; until then the draft quotes only the
  command-line figure.
- No demo video yet (#5 open). *Mock checklist item 2.* Fix: record per `docs/VIDEO_SCRIPT.md`
  after the redeploy, so the video shows the corrected labels.
- `README.md` beat 2 still promises "a live memory panel showing exactly what was retrieved and
  what's new"; the column shows what is stored, not what a turn retrieved. *Quality of the Idea
  (overclaim).* Fix: reword that README line; the draft does not repeat it.
- `docs/FEEDBACK.md:23` uses a phrase #20 forbids, so the draft restates the feedback instead of
  pasting the file. *Mock checklist item 3 (pitch text).* Fix: edit that line, then the two can match.
- The Space's public API lists the four hidden dev-mode turn buttons as endpoints, and the turn
  endpoint returns the dev-only panel text even with dev mode off. A judge on "Use via API" sees
  them. *Technological Implementation.* Fix: do not register those listeners (or set
  `api_name=False`) unless `FY_DEV_MODE=1`.
- Not checked in this pass: the page in a real browser (layout, phone width, the mobile alert
  strip) and the reply voice by ear; this pass used the API. *Design.* Fix: the second scorer
  clicks through in a clean browser and listens.
- A flag is marked "Dad was told" once the spoken line is synthesized, not once it plays, so a
  browser that blocks autoplay still shows it as told. *Quality of the Idea (the disclosure
  invariant).* Fix: attest disclosure from the browser's playback event, or label it "spoken
  line sent".
- The #14 sentence ("never reports anything to the family that it hasn't first said to him out
  loud") is absolute, but when the spoken line cannot be produced the flag still reaches the
  caregiver column, marked "NOT yet disclosed". *Quality of the Idea.* Fix: the team decides
  whether to qualify the sentence; it is required verbatim, so README.md,
  docs/Project_Description.md and the draft change together (#14).
- The safety backstop was Nano, which caught 12 of 19 true events (ADR-010). *Technological
  Implementation.* Fixed 2026-10-23: AUDIT now runs Nemotron 3 Super (ADR-016), which caught every
  labelled row; the set is small, so coverage is not proven.
- One scorer only. Fix: second human score, compared after both are written down.

## When to run this

After each real milestone, not on a fixed schedule: once a key exists and `webapp.py` runs the
full pipeline live; once it's hosted; once a video v1 exists; once the Devpost text draft
(issue #20) exists. Four mock passes between now and submission is a reasonable target — more
than that and the scoring becomes the work instead of informing it.
