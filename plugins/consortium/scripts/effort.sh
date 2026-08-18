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

is_valid() { case " $VALID " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
is_sha256() { [[ "$1" =~ ^[[:xdigit:]]{64}$ ]]; }

workspace_hash() {
  local workspace_path hash=""

  workspace_path="$(pwd -P)" || {
    printf 'Unable to determine the canonical workspace path.\n' >&2
    return 1
  }

  if command -v sha256sum >/dev/null 2>&1; then
    hash="$(printf '%s\n' "$workspace_path" | sha256sum 2>/dev/null | awk '{print $1}' || true)"
  fi
  if ! is_sha256 "$hash" && command -v shasum >/dev/null 2>&1; then
    hash="$(printf '%s\n' "$workspace_path" | shasum -a 256 2>/dev/null | awk '{print $1}' || true)"
  fi
  if ! is_sha256 "$hash" && command -v openssl >/dev/null 2>&1; then
    hash="$(printf '%s\n' "$workspace_path" | openssl dgst -sha256 2>/dev/null | awk '{print $NF}' || true)"
  fi

  if ! is_sha256 "$hash"; then
    printf 'Unable to calculate a SHA-256 workspace state key.\n' >&2
    return 1
  fi
  printf '%s\n' "$hash"
}

workspace_override_path() {
  local git_path workspace_hash

  if git_path="$(git rev-parse --git-path consortium/tier 2>/dev/null)"; then
    printf '%s\n' "$git_path"
    return
  fi

  workspace_hash="$(workspace_hash)" || return 1
  printf '%s/workspaces/sha256-%s/tier\n' "$STATE_HOME" "$workspace_hash"
}

OVERRIDE="$(workspace_override_path)"

resolve_tier() {
  local candidate source

  if [ -f "$OVERRIDE" ]; then
    candidate="$(cat "$OVERRIDE")"
    source="workspace override"
  elif [ -n "${CONSORTIUM_TIER:-}" ]; then
    candidate="$CONSORTIUM_TIER"
    source="environment override"
  elif [ -f "$DEFAULT_TIER_FILE" ]; then
    candidate="$(cat "$DEFAULT_TIER_FILE")"
    source="user default"
  else
    candidate="$DEFAULT"
    source="built-in default"
  fi

  if ! is_valid "$candidate"; then
    printf 'Invalid tier from %s: %s\nValid: %s\n' "$source" "$candidate" "$VALID" >&2
    return 1
  fi
  printf '%s' "$candidate"
}
resolve_source() {
  if [ -f "$OVERRIDE" ]; then printf 'workspace override'
  elif [ -n "${CONSORTIUM_TIER:-}" ]; then printf 'environment override'
  elif [ -f "$DEFAULT_TIER_FILE" ]; then printf 'user default'
  else printf 'built-in default'; fi
}
if [ "${1:-}" = "--resolve" ]; then
  resolve_tier || exit 1
  printf '\n'
  exit 0
fi

if [ "$#" -eq 0 ]; then
  if ! tier="$(resolve_tier)"; then exit 1; fi
  printf 'Consortium tier: %s (%s)\n' "$tier" "$(resolve_source)"
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
