# Plan: Self-judging retro (#205)

## Goal

A prediction on 10-29, a comparison with reality in December, and three changes for next time.

## Affected files

`docs/SELF_JUDGING.md` (score log rows, retro section), `docs/WORK_LOG.md` (winner study),
`CHANGELOG.md` Docs lines.

## Steps

1. 10-29, after the `v1.0.0` Release deploy and before the form is submitted: each maintainer
   opens the Space in a clean browser, watches the final video, reads the pasted text, and
   scores the four criteria 1 to 5 using the questions in `docs/SELF_JUDGING.md`. Each posts
   their row on #205 without reading the other's. Then both rows go into the file in one commit.
2. Same day: the founder adds the "founder call" row (the single highest-leverage fix, even if
   it is now too late) and the disagreement lines.
3. After results: append placement and feedback; write the retro section; one PR.
4. Winner study: for each public winning entry, one paragraph in `docs/WORK_LOG.md` under a
   dated entry; link the entries; no scores for them.
5. Turn each "change" into an issue or a ROADMAP stretch line.

## Tests

`python -m unittest discover tests -v` for the docs.

## Splitting across subagents

- Subagent A (step 1, optional third score): a subagent can score the frozen artefacts as a
  "stranger" and post a third row labelled as an assistant score; it must use the rubric
  questions verbatim and must not read the human rows first. It needs the Space URL, the video
  link and `docs/DEVPOST_SUBMISSION.md`.
- Subagent B (step 4): the winner study from public Devpost pages. Returns the paragraphs.
Steps 2, 3 and 5 are the maintainers'.

## Review

Not code. The founder reads the retro before it is committed.
