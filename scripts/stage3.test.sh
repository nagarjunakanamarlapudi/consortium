#!/usr/bin/env bash
# Structural checks for Stage 3 (bar-raiser-eval). Behavior is verified live.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok(){ printf 'ok   - %s\n' "$1"; }
fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

# 1. bar-raiser agent exists with name + description frontmatter
f="$ROOT/agents/bar-raiser.md"
if [ -f "$f" ] && grep -q "^name: bar-raiser$" "$f" && grep -q "^description:" "$f"; then ok "bar-raiser agent present with frontmatter"; else fail "bar-raiser agent missing or bad frontmatter"; fi

# 2. bar-raiser agent defines the structured verdict (accept/reject + mandates + severity)
if [ -f "$f" ] && grep -q "verdict" "$f" && grep -q "rewrite_mandates" "$f" && grep -q "severity" "$f"; then ok "bar-raiser verdict schema documented"; else fail "bar-raiser verdict schema incomplete"; fi

# 3. playbook exists, builds on experts-eval, and loops on the verdict
pb="$ROOT/skills/team-dev-workflow/references/bar-raiser-eval.md"
if [ -f "$pb" ] && grep -q "experts-eval.md" "$pb" && grep -qi "rounds" "$pb"; then ok "bar-raiser-eval playbook present (builds on experts-eval, loops)"; else fail "bar-raiser-eval playbook missing/incomplete"; fi

# 4. SKILL routes bar-raiser-eval to its playbook
sk="$ROOT/skills/team-dev-workflow/SKILL.md"
if grep -q "references/bar-raiser-eval.md" "$sk"; then ok "skill links bar-raiser-eval playbook"; else fail "skill does not link bar-raiser-eval playbook"; fi

# 5. registry lists the bar-raiser as the gate
reg="$ROOT/skills/team-dev-workflow/references/reviewer-registry.md"
if [ -f "$reg" ] && grep -q "bar-raiser" "$reg"; then ok "registry lists the bar-raiser"; else fail "registry missing the bar-raiser"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
