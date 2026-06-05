#!/usr/bin/env bash
# Structural checks for Stage 4 (vibe-coding). Behavior is verified live.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok(){ printf 'ok   - %s\n' "$1"; }
fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

pb="$ROOT/skills/team-dev-workflow/references/vibe-coding.md"

# 1. playbook exists and builds on bar-raiser-eval
if [ -f "$pb" ] && grep -q "bar-raiser-eval.md" "$pb"; then ok "vibe-coding playbook present (builds on bar-raiser-eval)"; else fail "vibe-coding playbook missing or doesn't build on bar-raiser-eval"; fi

# 2. documents autonomy (no gate) + PR + fresh branch
if [ -f "$pb" ] && grep -qi "autonomous" "$pb" && grep -qi "no human gate\|no gate\|without stopping\|no plan-approval gate" "$pb" && grep -qi "PR" "$pb" && grep -qi "branch" "$pb"; then ok "playbook documents autonomous + PR + branch"; else fail "playbook missing autonomy/PR/branch language"; fi

# 3. documents the severity-gated finish (minor ships, major stops + asks)
if [ -f "$pb" ] && grep -qi "minor" "$pb" && grep -qi "major" "$pb" && grep -qi "stop" "$pb"; then ok "playbook documents severity-gated finish"; else fail "playbook missing severity-gated finish"; fi

# 4. SKILL routes vibe-coding to its playbook
sk="$ROOT/skills/team-dev-workflow/SKILL.md"
if grep -q "references/vibe-coding.md" "$sk"; then ok "skill links vibe-coding playbook"; else fail "skill does not link vibe-coding playbook"; fi

# 5. the human-gate section still excludes vibe-coding (regression guard)
if grep -q "vibe-coding\` never gates" "$sk"; then ok "skill still exempts vibe-coding from the human gate"; else fail "skill no longer exempts vibe-coding from the gate"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
