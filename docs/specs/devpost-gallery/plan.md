# Plan: four captioned screenshots for the Devpost gallery (#218)

## Goal

Four 1080p images a judge sees above the submission text, each showing one true thing from the
live Space, with a one-line caption. Taken after the deploy that carries #214 and #215, so the
footer and labels match the video.

## Images

1. The split screen at the fall moment: senior side with "I fell down earlier and I'm scared" and
   the reply; caregiver side with the flag and "✅ Dad was told". Caption: "He is told first. In
   the same moment, she sees the flag."
2. The briefed memory: three Permanent items and the Temporary groceries line. Caption: "Briefed
   once by the family. What lasts is kept; today's errand expires."
3. The crisis turn: the 988 line on the senior side, the crisis flag on the caregiver side.
   Caption: "A crisis gets a referral, not a pep talk, and the flag is disclosed."
4. The stack, as plain text on a white page (the same three lines as the video's 2:13-2:30
   card). Caption: "NVIDIA Nemotron 3 Nano on Nebius Token Factory; hearing and voice on the app's
   own server."

## Affected files

- `scripts/gallery_shots.py` (new, committed): Playwright script that opens the Space URL,
  waits for the pre-briefed household, types each line into "Type (as the senior)", presses
  Send, waits for the caregiver column to show the flag (poll the page text for "Dad was told",
  up to 60 s), and screenshots 1920x1080 at 110 % zoom. Image 4 is rendered from a local HTML
  string. Output directory is an argument and defaults to `../gallery/` outside the repo.
- Images are **not committed** (`AGENTS.md`: media stays out of the repo). They are handed to
  the Representative for the Devpost upload and the four file names are listed on #218.

## Steps

1. Script, run against the live Space after the deploy's `Build:` line shows the #215 commit.
2. Eyeball each image at phone size; "Dad was told" must be legible.
3. Post the four captions and file names on #218; hand the files over.

## Splitting across subagents

One subagent (general worker, medium) after the deploy; it gets this file, #218, the Space URL,
the Playwright gotchas (Chromium path `~/.cache/ms-playwright/chromium-*/chrome-linux/chrome`,
`wait_until="load"`), and the `video/` README for the stack-card wording. It returns the four
paths and a contact sheet. No key is needed: the Space holds its own.

## Review

None required for images; the script gets the usual Codex pass with its PR.
