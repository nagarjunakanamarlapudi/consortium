#!/usr/bin/env bash
# Consortium tier state. Single source of truth for the active evaluation tier.
#   effort.sh --resolve       -> print the bare resolved tier (used by skills)
#   effort.sh                 -> show the resolved tier and where it came from
#   effort.sh <tier>          -> set a persistent per-workspace override
#   effort.sh <tier> --global -> write a persistent Consortium user default
set -euo pipefail

STATE_HOME="$HOME/.consortium"
DEFAULT_TIER_FILE="$STATE_HOME/default-tier"
VALID="off self-eval experts-eval bar-raiser-eval debate vibe-coding"
DEFAULT="self-eval"

workspace_override_path() {
  local git_path workspace_hash

  if git_path="$(git rev-parse --git-path consortium/tier 2>/dev/null)"; then
    printf '%s\n' "$git_path"
    return
  fi

  workspace_hash="$(pwd -P | shasum -a 256 | awk '{print $1}')"
  printf '%s/workspaces/sha256-%s/tier\n' "$STATE_HOME" "$workspace_hash"
}

OVERRIDE="$(workspace_override_path)"

resolve_tier() {
  if [ -f "$OVERRIDE" ]; then cat "$OVERRIDE"
  elif [ -n "${CONSORTIUM_TIER:-}" ]; then printf '%s' "$CONSORTIUM_TIER"
  elif [ -f "$DEFAULT_TIER_FILE" ]; then cat "$DEFAULT_TIER_FILE"
  else printf '%s' "$DEFAULT"; fi
}
resolve_source() {
  if [ -f "$OVERRIDE" ]; then printf 'workspace override'
  elif [ -n "${CONSORTIUM_TIER:-}" ]; then printf 'environment override'
  elif [ -f "$DEFAULT_TIER_FILE" ]; then printf 'user default'
  else printf 'built-in default'; fi
}
is_valid() { case " $VALID " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

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
  mkdir -p "$STATE_HOME"
  printf '%s\n' "$TIER" > "$DEFAULT_TIER_FILE"
  rm -f "$OVERRIDE"
  printf 'Consortium user default = %s (workspace override cleared).\n' "$TIER"
else
  mkdir -p "$(dirname "$OVERRIDE")"
  printf '%s\n' "$TIER" > "$OVERRIDE"
  printf 'Consortium tier = %s (this workspace).\n' "$TIER"
fi
