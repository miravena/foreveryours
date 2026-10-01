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

## When to run this

After each real milestone, not on a fixed schedule: once a key exists and `webapp.py` runs the
full pipeline live; once it's hosted; once a video v1 exists; once the Devpost text draft
(issue #20) exists. Four mock passes between now and submission is a reasonable target — more
than that and the scoring becomes the work instead of informing it.
