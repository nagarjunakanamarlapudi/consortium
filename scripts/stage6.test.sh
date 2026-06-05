#!/usr/bin/env bash
# Structural checks for Stage 6 (specialized reviewers + change-type plumbing). Behavior verified live.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0; ok(){ printf 'ok   - %s\n' "$1"; }; fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

AGENTS="security-reviewer cicd-reviewer iac-change-reviewer test-coverage-reviewer"

# 1. each specialized agent exists with frontmatter
for a in $AGENTS; do
  f="$ROOT/agents/$a.md"
  if [ -f "$f" ] && grep -q "^name: $a$" "$f" && grep -q "^description:" "$f"; then ok "agent $a present"; else fail "agent $a missing/bad frontmatter"; fi
done

# 2. registry lists each as a conditional reviewer
reg="$ROOT/skills/team-dev-workflow/references/reviewer-registry.md"
for a in $AGENTS; do
  if grep -q "$a" "$reg"; then ok "registry lists $a"; else fail "registry missing $a"; fi
done

# 3. build.js accepts extraReviewers (conditional reviewers passed in by the skill)
js="$ROOT/workflows/build.js"
if grep -q "extraReviewers" "$js"; then ok "build.js handles extraReviewers"; else fail "build.js does not handle extraReviewers"; fi
if command -v node >/dev/null 2>&1; then node --check "$js" 2>/dev/null && ok "build.js passes node --check" || fail "build.js syntax error"; else ok "node unavailable — skipped"; fi

# 4. the playbook does change-type detection -> extraReviewers
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if grep -q "extraReviewers" "$pb"; then ok "experts-eval wires change-type -> extraReviewers"; else fail "experts-eval missing change-type/extraReviewers wiring"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
