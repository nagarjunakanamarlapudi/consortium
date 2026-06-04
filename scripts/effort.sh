#!/usr/bin/env bash
# Consortium tier state. Single source of truth for the active evaluation tier.
#   effort.sh --resolve       -> print the bare resolved tier (used by the skill)
#   effort.sh                 -> show the resolved tier and where it came from
#   effort.sh <tier>          -> set a per-workspace override
#   effort.sh <tier> --global -> write the user-wide default into ~/.claude/settings.json
set -euo pipefail

STATE_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.consortium}"
OVERRIDE="$STATE_DIR/tier"
SETTINGS="$HOME/.claude/settings.json"
VALID="off self-eval experts-eval bar-raiser-eval debate vibe-coding"
DEFAULT="self-eval"

resolve_tier() {
  if [ -f "$OVERRIDE" ]; then cat "$OVERRIDE"
  elif [ -n "${CONSORTIUM_TIER:-}" ]; then printf '%s' "$CONSORTIUM_TIER"
  else printf '%s' "$DEFAULT"; fi
}
resolve_source() {
  if [ -f "$OVERRIDE" ]; then printf 'session override'
  elif [ -n "${CONSORTIUM_TIER:-}" ]; then printf 'global default'
  else printf 'built-in default'; fi
}
is_valid() { case " $VALID " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

mkdir -p "$STATE_DIR"

if [ "${1:-}" = "--resolve" ]; then resolve_tier; printf '\n'; exit 0; fi

if [ "$#" -eq 0 ]; then
  printf 'Consortium tier: %s (%s)\n' "$(resolve_tier)" "$(resolve_source)"
  printf 'Set: team-dev-effort <%s> [--global]\n' "$(printf '%s' "$VALID" | tr ' ' '|')"
  exit 0
fi

TIER="$1"; shift || true
GLOBAL=""
for a in "$@"; do [ "$a" = "--global" ] && GLOBAL=1; done

if ! is_valid "$TIER"; then
  printf 'Invalid tier: %s\nValid: %s\n' "$TIER" "$VALID" >&2
  exit 1
fi

if [ -n "$GLOBAL" ]; then
  mkdir -p "$HOME/.claude"
  [ -f "$SETTINGS" ] || printf '{}\n' > "$SETTINGS"
  if command -v jq >/dev/null 2>&1; then
    tmp="$(mktemp)"
    jq --arg t "$TIER" '.env = (.env // {}) | .env.CONSORTIUM_TIER = $t' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"
    rm -f "$OVERRIDE"
    printf 'Global default = %s (written to %s; workspace override cleared).\n' "$TIER" "$SETTINGS"
  else
    printf 'jq not found. Add manually to %s:\n  "env": { "CONSORTIUM_TIER": "%s" }\n' "$SETTINGS" "$TIER" >&2
    exit 1
  fi
else
  printf '%s' "$TIER" > "$OVERRIDE"
  printf 'Consortium tier = %s (this workspace).\n' "$TIER"
fi
