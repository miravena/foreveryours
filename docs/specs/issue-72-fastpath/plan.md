# Plan: Issue 72 (Fast-Path Misses)

## The Bugs
1. `"I'm lying on the floor and it hurts"` is missed because the regex specifically requires the word `hurt` inside the group: `\\b(on|hit)\\s+the\\s+floor\\b.*\\b(can(?:'?t|not)\\s+(move|get up)|stuck|hurt|help)\\b`.
2. `"  help  "` is missed because the exact plea regex is anchored with `^help[!.?\\s]*$`, which expects `help` to be the very first character of the string. Surrounding whitespace breaks the `^` anchor.

## The Fix
1. **Modify `hurt` to `hurts?`**: Change the floor regex rules to allow both "hurt" and "hurts".
   - Current: `\\b(can(?:'?t|not)\\s+(move|get up)|stuck|hurt|help)\\b`
   - New: `\\b(can(?:'?t|not)\\s+(move|get up)|stuck|hurts?|help)\\b`
2. **Modify the `^help` anchor**: Allow leading whitespace in the regex.
   - Current: `^help[!.?\\s]*$`
   - New: `^\\s*help[!.?\\s]*$` (also do this for the other anchored one: `^\\s*(can\\s+someone\\s+)?help\\s+me[!.?\\s]*$`)

## Verification
- Run Benchmark 2 to ensure we didn't increase the false positive rate.
- We will add tests for `"I'm lying on the floor and it hurts"` and `"  help  "` directly into the fast-path unit tests.

## Review
- Write `docs/specs/issue-72-fastpath/review.md`.
