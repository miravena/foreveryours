# Plan: what three caregivers told us (#219)

## Goal

Three 15-minute conversations with people who look after an older parent, before the freeze, and
one honest paragraph in the Devpost text and README about what they said and what changed because
of it. The judges' first piece of advice was to talk to users before locking the project; today
no one has been asked.

## What the founder does

Three calls, 15 minutes each, by 2026-10-26. Notes go to the fleet as plain text (no names, no
health details of the parent). The guide below is written so the call needs no preparation.

## Interview guide (the subagent drafts this as `guide.md`, one page)

Consent line to read first: this is for a hackathon entry; nothing you say is recorded or
published with your name; I will summarise what three people told us in general terms.

1. When you are not with your parent, what do you most want to know, and how do you find out today?
2. Tell me about the last time something worried you that you learned about late.
3. If a voice companion could be briefed by you, what three things would you tell it first?
4. What should it never tell you about? What should it never do?
5. We show the parent out loud that the family is being told, before the family hears it. How
   does that land with you?
6. What would make you stop using it after a week?

Note template: one line per question, plus "what surprised me" and "what I would change".

## What the fleet does afterwards

- `docs/DEVPOST_DRAFT.md` Inspiration: one paragraph "What three caregivers told us", quoting
  nothing verbatim that could identify a person, stating the one surprise and the one change
  made (or honestly, "nothing changed, and here is why").
- `README.md` the same paragraph; the Devpost text and README must match (#204).
- If a conversation contradicts a claim in the text, the claim changes, not the paragraph.

## Splitting across subagents

- Subagent A (doc writer profile, low effort, now): writes `guide.md` from the list above and a
  `notes-template.md`. Gets this file and #219. Returns the two paths.
- Subagent B (doc writer, medium, after the founder's notes arrive): writes the paragraph into
  both files, one commit, one PR. Gets this file, the notes, `docs/DEVPOST_DRAFT.md` Inspiration
  and `README.md` opening.

## Review

The founder reads the paragraph before it is pasted; it speaks for real people.
