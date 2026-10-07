# Product requirements

Short and concrete on purpose — the demo script is the acceptance bar, not a separate
test plan that can drift from it.

## The pitch

**The companion the family briefs — your voice in Dad's day when you can't be there.**

A voice-first AI companion for older adults. The caregiver gives it context once (a voice
memo: names, preferences, daily updates, things to avoid). The senior gets a warm, low-friction
voice conversation that actually uses that context. The caregiver gets honest safety flags —
told in-conversation to the senior, never a silent report behind their back.

## Personas

- **The senior** (e.g. "Dad") — talks to the companion by voice. Wants a warm, natural
  conversation, not a bot that announces "according to my notes." Should never feel watched.
- **The caregiver** (e.g. a working adult child) — can't be there all day. Gives context once
  (a voice memo) instead of repeating themselves to every visit or call. Wants to know,
  honestly, if something concerning came up — and wants the senior to know they were told,
  not to find out secretly.

Both personas are first-class. A design that serves the caregiver by surveilling the senior
fails the product; a design that serves the senior by hiding real concerns from the caregiver
also fails it. "Honest safety flags, never silent surveillance" is the resolution, and it's
non-negotiable — see `SAFETY_AND_PRIVACY.md`.

## What this is NOT (explicit non-goals)

Cut from build scope on purpose — these are roadmap-slide material for the pitch deck, not
things we're building or claiming:

- Weather/news reporting
- A weekly digest or summary email
- Physical hardware (this is software; assume a phone/speaker exists)
- Medical certification, diagnosis, or clinical claims of any kind
- Emergency dispatch (a caregiver flag is a notification, not a 911 call)
- Conversation history across sessions (single-turn-at-a-time for this build — see
  `IMPLEMENTATION_PLAN.md`'s open items)

## Acceptance bar: the demo script

`docs/DEMO_SCRIPT.md` is the acceptance bar, not a nice-to-have. A change that breaks a beat
in it is a blocker for `main`, full stop — see `CONTRIBUTING.md`. In order:

1. **Caregiver memo** — caregiver submits context once; it's saved and provably recalled later
   (not re-asked for, not forgotten).
2. **Senior conversation uses that context** — the companion naturally uses caregiver facts
   and respects caregiver guardrails ("avoid talking about driving"), with a live panel proving
   what was recalled/saved — under 2 seconds to first audio.
3. **A worrying remark → honest flag, conversation continues** — distress/confusion triggers an
   immediate, honest, in-conversation disclosure to the senior, a caregiver flag, and the
   conversation keeps going rather than dead-ending.

If a beat can't be demoed end to end, the build isn't done — a passing unit test over a mocked
pipeline doesn't count. See `CONTRIBUTING.md`'s "keep main demo-able" rule.

## Judging-relevant framing

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/)
(Personal AI track, which permits either Nebius Token Factory or Nebius AI Cloud). This project runs
on Nebius Token Factory with open-weight NVIDIA Nemotron models; it does not use Nebius AI Cloud —
see `README.md`'s Pipeline section for exactly where that model call sits and why latency (under 2s
to first audio) is treated as a judging risk, not an afterthought.

## Acoustic and Conversational Observations (Advanced Features)

These are observational signals surfaced to the caregiver, not a clinical or diagnostic layer — see
"Designed for Trust" in `docs/Project_Description.md`.
- **Acoustic Environment & Real-World Speech:** TV crosstalk is rejected using aggressive Voice Activity Detection (VAD). **Note:** Full-Duplex Barge-In (stopping audio mid-sentence) is an explicitly intended *hardware-layer* integration for production, not possible natively in the push-to-talk web demo.
- **Circadian Dynamics:** The system modifies its behavior based on the time of day, natively adapting to Sundowning Syndrome (16:00 - 20:00) by keeping responses simple and soothing, and entering Night Mode for quiet rest.
- **Acoustic and Conversational Observations:** The system computes acoustic biomarkers (Speaking Rate / Pauses) from the current clip only and watches for repeated logistical questions within a conversation (Perseveration Tracking, #63). These are observations passed to the caregiver, not a detection of any medical or cognitive condition.
