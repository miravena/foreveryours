# Safety & privacy design

Short, because the design choices matter more than the length of this doc.

## No silent surveillance

Every caregiver flag records whether the senior was actually told, in the
conversation — `CaregiverFlags.add()` takes `disclosed_to_senior` as a
required argument, not a default, specifically so this can't quietly drift
from true to false:

- **Fast-path flags** (`safety/fastpath.py`) are always recorded, and
  disclosed whenever speech works — the immediate reply the senior hears
  ("I'm letting your family know right now so someone can check on you.")
  *is* the disclosure, spoken before anything else happens. If speech
  synthesis fails or times out (`TTS_TIMEOUT_S`), the flag is still recorded
  with `disclosed_to_senior: False` and "spoken disclosure failed; shown as
  text only", and the same sentence reaches the senior as text (Office #23233).
- **Audit flags** (`pipeline/audit.py`, see below) try to disclose via a
  spoken follow-up line after the fact. If that follow-up fails for some
  reason, the flag is recorded as `disclosed_to_senior=False` — honestly,
  not papered over — rather than assumed to have succeeded. "Told" means the
  browser actually received the line's audio: the streaming turn keeps
  listening after its reply until the audit finishes (bounded), and a line
  that arrives after the browser stopped listening is recorded undisclosed
  (Office #23231). The same rule gates lifestyle notes.

The senior is never meant to be monitored silently behind their back; the
code's job is to make that true in both cases above, not just the easy one.
The caregiver-facing panel in `webapp.py` applies the same rule to what it
*shows*: safety flags render either way, labeled with their disclosure
status, but the "Briefed memory" list never renders EMOTIONAL-scope
memories extracted from the senior's own words — active or decayed —
only caregiver-authored memos/notes and non-EMOTIONAL conversation facts
(Fixes #140). Any future caregiver summary or digest (the weekly digest
`docs/PRD.md` describes) must be built the same way: only from counters
and disclosed flags, never from model-written free text about the
conversation.

Flag *text* is minimised on the same principle: it is a fixed description
of the trigger category — `safety/fastpath.py`'s `CAREGIVER_FLAG_TEXT` —
and never contains the senior's utterance or the auditor's one-sentence
reason. A flag says *what kind* of event happened (crisis, distress,
confusion, unsafe advice), not what the senior said or what the model wrote
about it, so the caregiver panel can never become a transcript leak (#23232).

**Refinement (implemented 2026-10-03):** the fast-path reply today discloses this *one* instance ("I'm letting your family know right now so someone can check on you.") but also states the standing rule — i.e. when disclosure happens and when it doesn't. Spelling that rule out loud, e.g. *"I'll only tell them if I'm worried about your safety,"* answers the "elder surveillance" objection more directly than a single-instance disclosure can: it tells the senior the boundary up front, not just that this one thing got reported.

## No medical claims

The companion is a companion, not a diagnostic tool. `pipeline/audit.py`'s
secondary model pass exists to catch medical advice or diagnosis language
in a reply **after it has already been spoken** (it runs async, off the
latency-critical path — see below, and note this means it can flag and
disclose, but it cannot retract something already said). If `AUDIT_MODEL`
flags a reply `UNSAFE`, that's logged as a caregiver flag and spoken to the
senior as a follow-up, not silently dropped.

## Two safety layers, different jobs

1. **Fast-path** (`safety/fastpath.py`) — synchronous, regex-based, runs
   before the LLM call. Catches the clearest distress/confusion signals
   instantly, speaking an immediate reassurance before the model is even
   called, so the highest-stakes replies are also the fastest. The
   conversation then continues into THINK with a short context note, rather
   than ending the turn — a distress signal shouldn't make the companion go
   silent right after. Deliberately conservative patterns — a false positive
   here (an unnecessary caregiver note) is far cheaper than a false negative.
   The public demo's daily request cap never blocks it: at the cap the
   fast-path still speaks and flags, and only the paid THINK continuation is
   withheld (`webapp._cap_decision`, Office #23228).
2. **Audit** (`pipeline/audit.py`) — asynchronous, a second small-model pass
   over every *other* reply and the senior's transcript. It checks for
   medical-hallucination or unsafe-advice risk and provides a wider,
   graded `DISTRESS`/`CRISIS` backstop for phrasing the regex cannot cover.
   Runs after the reply is already on its way to audio, so it never adds
   latency — it can only flag and disclose after the fact, not block in time.
   Empty, malformed, or failed audit responses are recorded as `unknown`, not
   treated as safe.

Neither layer is a substitute for the other. The fast-path is a narrow net
for the highest-urgency, most time-critical cases; the audit pass is a wider
net for everything else, accepted at the cost of running after the words are
already said.

## What's stored

Caregiver memos and caregiver daily notes, stored verbatim. For the senior's
turn, Nemotron (via Nebius Token Factory, `pipeline/think.py`'s
`extract_memory_llm`) runs first and returns a specific `ADD:`/`SUPERSEDE:`/
`DELETE:` command, which lets a correction ("my grandson's name is Liam, not
Leo") or a forget request update or remove the existing fact instead of
piling on a new one (#54). When that call fails (not just when the model
decides there's nothing to extract — see #82), the offline `DURABLE_MARKERS`
heuristic in `pipeline/think.py` is the fallback: it cannot see which stored
fact a correction targets, so it stores only plain new facts, never a
correction or forget request or a question, and **stores the whole turn's
transcript verbatim, not just the fact** — it has no LLM call available to
do the per-fact extraction instead.
Nothing else is kept on purpose, but audio does touch disk, so here is
exactly where and for how long (issue #18):

Lifestyle observations are a separate caregiver-only scope. They are written
only after the senior has heard the disclosure, expire after seven days, and
are excluded from both senior-facing profile facts and conversational search.
Expired legacy lifestyle records are scrubbed when the profile is loaded.

Hosted-demo session directories are also swept at startup and periodically,
so an abandoned session is removed after `SESSION_TTL_S` even if no new
visitor opens the demo after a process restart.

- **Hosted web demo (`webapp.py`).** Each browser tab is its own throwaway
  household under `FY_SESSIONS_DIR`. The reply WAVs from one turn are deleted
  at the start of the next; the whole household (memory, flags)
  is deleted about an hour (3600s) after the tab disconnects — Gradio's
  `gr.State` `delete_callback` (`_end_session`) fires once Gradio's own
  closed-session timer expires, which is a fixed 3600s in the installed
  Gradio version (confirmed against the `gradio` package in this repo's
  `.venv`) regardless of `SESSION_TTL_S` — or after
  `SESSION_TTL_S` of inactivity (the sweeper) if the close event never
  arrives. We never promise deletion the instant the tab closes. Uploaded or
  recorded input clips and served reply audio separately pass through
  Gradio's own file cache (`delete_cache=GRADIO_CACHE_SWEEP`), which is swept
  every `GRADIO_CACHE_SWEEP[0]` seconds (600s) and drops files older than
  `GRADIO_CACHE_SWEEP[1]` seconds (`SESSION_TTL_S`), so a clip can
  live up to roughly `SESSION_TTL_S + 600` seconds (~70 minutes by default).
  This cache cleanup is separate from removal of the household session
  directory; closing a tab does not itself delete cached input or reply audio.
  No other visitor can see another tab's household.
- **Local CLI (`main.py`).** Reply audio stays in `out/audio/` and memory in
  `data/` until you delete them. That's your own machine, and keeping them is
  what lets `day2` prove persistence.
- **Third parties.** Transcripts (text, not audio) of each turn go to Nebius
  Token Factory for THINK/AUDIT. With the default `ASR_BACKEND=whisper_local`
  (what the hosted demo runs; Token Factory has no transcription endpoint,
  PR #25), speech recognition is local, so raw audio is never sent to a
  model provider.

## What this is not

No medical certification, no clinical claims, no emergency-dispatch
integration (a caregiver flag is a notification, not a 911 call). These are
explicitly out of scope for the hackathon build — see the main README.
