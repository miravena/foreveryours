#!/bin/sh
# check_attribution.sh <msgfile> [author_email]
#
# Shared advisory attribution checks, called by both .githooks/commit-msg (per
# local commit) and .github/workflows/attribution.yml (per pushed/PR commit),
# so the tests in tests/test_attribution_hook.py cover exactly what CI runs.
#
# Prints one "WARNING: ..." line per problem found on stderr. ALWAYS exits 0 —
# this is advisory only, never a blocking gate (ADR-007 and its amendments).
#
# Checks:
#   1. author email that GitHub cannot credit
#   2. an AI Co-Authored-By trailer, vendor email, or AI Signed-off-by
#      (we use Assisted-by/Reviewed-by instead; kernel rule: no AI sign-off)
#   3. a session link in the message (the repo is public)
#   4. an Assisted-by/Reviewed-by line with no ":<model>" (the kernel
#      AGENT_NAME:MODEL_VERSION shape — see CONTRIBUTING.md -> "Recording
#      which model did what")
#   5. an Assisted-by/Reviewed-by line with no Assisted-meta line
#   6. an Assisted-by/Reviewed-by line with no Cost-estimate line
#
# See CONTRIBUTING.md -> "Commit attribution", "Recording which model did
# what", "Recording what it cost"; ADR-007 (docs/decisions/ADR-007-attribution.md)
# and its 2026-10-12 amendment.

msgfile="$1"
email="${2:-${GIT_AUTHOR_EMAIL:-$(git config user.email 2>/dev/null)}}"

warn() {
  printf '\nWARNING: %s\n' "$1" >&2
}

case "$email" in
  "") ;; # no email to check (e.g. CI invocation with none passed) -- skip silently
  *@users.noreply.github.com) ;;                              # linked by construction
  elevenbaselab@gmail.com|mathewgc007@gmail.com) ;;           # verified on a GitHub account
  *)
    warn "author email '$email' is not a known GitHub-linked address. Commits with an unlinked author email do not appear under your account in the Contributors graph (they credit nobody). Expected something ending in @users.noreply.github.com -- see CONTRIBUTING.md -> \"Commit attribution\"."
    ;;
esac

[ -n "$msgfile" ] && [ -f "$msgfile" ] || exit 0
body=$(grep -v '^#' "$msgfile")

if printf '%s\n' "$body" | grep -qiE '^Co-Authored-By:.*(anthropic|claude|gemini|copilot|codex|openai|cursor)'; then
  warn "AI Co-Authored-By trailer. Remove it and use \`Assisted-by: <harness>:<model id> [tools]\` (CONTRIBUTING.md -> \"Commit attribution\", ADR-007)."
fi

if printf '%s\n' "$body" | grep -qiE '^Claude-Session:|claude\.ai/code'; then
  warn "session link in the commit message. This repo is public; remove it."
fi

if printf '%s\n' "$body" | grep -qiE '^Signed-off-by:.*(anthropic|claude|gemini|copilot|codex|openai|cursor|chatgpt)'; then
  warn "AI Signed-off-by trailer. The kernel convention reserves Signed-off-by for the human; use Assisted-by/Reviewed-by instead."
fi

assisted_lines=$(printf '%s\n' "$body" | grep -E '^(Assisted-by|Reviewed-by):')

if [ -n "$assisted_lines" ]; then
  if printf '%s\n' "$assisted_lines" | sed -E 's/^(Assisted-by|Reviewed-by): *//' | awk '{print $1}' | grep -vq ':'; then
    warn "Assisted-by/Reviewed-by with no ':<model>'. Format is \`Assisted-by: <harness>:<model id> [tools]\` (CONTRIBUTING.md -> \"Recording which model did what\")."
  fi

  if ! printf '%s\n' "$body" | grep -qE '^Assisted-meta:'; then
    warn "no Assisted-meta line. Add \`Assisted-meta: provider=<Anthropic|OpenAI|Google|...> effort=<low|medium|high|xhigh|max|unknown>\` (CONTRIBUTING.md -> \"Recording which model did what\")."
  fi

  if ! printf '%s\n' "$body" | grep -qE '^Cost-estimate:'; then
    warn "no Cost-estimate line. Add \`Cost-estimate: \$X.XX (approximate[; in N, out N tokens])\` or \`Cost-estimate: unknown\` (CONTRIBUTING.md -> \"Recording what it cost\")."
  fi
fi

exit 0
