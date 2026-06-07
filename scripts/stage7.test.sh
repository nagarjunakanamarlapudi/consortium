#!/usr/bin/env bash
# Structural checks for project-reviewer auto-discovery. Behavior (bare-name dispatch) verified live.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0; ok(){ printf 'ok   - %s\n' "$1"; }; fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

# 1. plan-review.js accepts extraReviewers (parity with build.js)
js="$ROOT/workflows/plan-review.js"
if grep -q "extraReviewers" "$js"; then ok "plan-review.js handles extraReviewers"; else fail "plan-review.js missing extraReviewers"; fi
if command -v node >/dev/null 2>&1; then node --check "$js" 2>/dev/null && ok "plan-review.js passes node --check" || fail "plan-review.js syntax error"; else ok "node unavailable — skipped"; fi

# 2. registry documents the auto-discovery contract + the read-only heuristic
reg="$ROOT/skills/team-dev-workflow/references/reviewer-registry.md"
if grep -qi "auto-discover" "$reg" && grep -q "Project reviewers" "$reg"; then ok "registry documents project-reviewer auto-discovery"; else fail "registry missing auto-discovery section"; fi
if grep -qi "read-only" "$reg"; then ok "registry states the read-only reviewer heuristic"; else fail "registry missing read-only heuristic"; fi

# 3. experts-eval wires auto-discovery into the checkpoints
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if grep -qi "auto-discover" "$pb"; then ok "experts-eval wires auto-discovery"; else fail "experts-eval missing auto-discovery wiring"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
