#!/usr/bin/env bash
# Structural checks for Stage 2 wiring (not behavior — behavior is verified live).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok(){ printf 'ok   - %s\n' "$1"; }
fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

AGENTS="spec-clarity-reviewer domain-conventions-reviewer spec-compliance-reviewer code-quality-reviewer"

# 1. Each reviewer agent exists with name + description frontmatter
for a in $AGENTS; do
  f="$ROOT/agents/$a.md"
  if [ -f "$f" ] && grep -q "^name: $a$" "$f" && grep -q "^description:" "$f"; then
    ok "agent $a present with frontmatter"
  else
    fail "agent $a missing or bad frontmatter"
  fi
done

# 2. Registry exists and names every always-on reviewer
reg="$ROOT/skills/team-dev-workflow/references/reviewer-registry.md"
if [ -f "$reg" ]; then ok "registry present"; else fail "registry missing"; fi
for a in $AGENTS; do
  if [ -f "$reg" ] && grep -q "$a" "$reg"; then ok "registry references $a"; else fail "registry missing $a"; fi
done

# 3. experts-eval playbook exists and consults the registry
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if [ -f "$pb" ] && grep -q "reviewer-registry.md" "$pb"; then ok "experts-eval playbook present and links registry"; else fail "experts-eval playbook missing or does not link registry"; fi

# 4. SKILL routes experts-eval to its playbook
sk="$ROOT/skills/team-dev-workflow/SKILL.md"
if grep -q "references/experts-eval.md" "$sk"; then ok "skill links experts-eval playbook"; else fail "skill does not link experts-eval playbook"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
