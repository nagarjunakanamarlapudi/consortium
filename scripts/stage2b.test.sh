#!/usr/bin/env bash
# Structural + syntax checks for the workflow engine (Stage 2b). Behavior verified live (installed session).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0; ok(){ printf 'ok   - %s\n' "$1"; }; fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

js="$ROOT/workflows/plan-review.js"
# 1. script present with meta + reviewer agentTypes + schema + parallel
if [ -f "$js" ] && grep -q "export const meta" "$js" && grep -q "consortium:spec-clarity-reviewer" "$js" && grep -q "consortium:domain-conventions-reviewer" "$js" && grep -q "schema" "$js" && grep -q "parallel" "$js"; then ok "plan-review.js present (meta, reviewer agentTypes, schema, parallel)"; else fail "plan-review.js missing/incomplete"; fi

# 2. JS syntax valid (node --check does not run the script, so workflow globals are fine)
if command -v node >/dev/null 2>&1; then
  if node --check "$js" 2>/dev/null; then ok "plan-review.js passes node --check"; else fail "plan-review.js has a syntax error"; fi
else
  ok "node unavailable — syntax check skipped"
fi

# 3. README documents invocation (${CLAUDE_PLUGIN_ROOT}) + fallback
r="$ROOT/workflows/README.md"
if [ -f "$r" ] && grep -q "CLAUDE_PLUGIN_ROOT" "$r" && grep -qi "fallback" "$r"; then ok "workflows/README documents invocation + fallback"; else fail "workflows/README missing/incomplete"; fi

# 4. experts-eval playbook prefers the workflow with an explicit fallback
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if grep -q "plan-review.js" "$pb" && grep -qi "fallback" "$pb"; then ok "experts-eval prefers the workflow with fallback"; else fail "experts-eval not wired to the workflow"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
