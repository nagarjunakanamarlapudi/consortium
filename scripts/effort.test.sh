#!/usr/bin/env bash
# Tests for effort.sh. Runs it in an isolated temp state dir with a controlled env.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/effort.sh"
fails=0
check() { # check "desc" "expected substring" "actual"
  if printf '%s' "$3" | grep -qF "$2"; then
    printf 'ok   - %s\n' "$1"
  else
    printf 'FAIL - %s\n      expected to contain: %s\n      got: %s\n' "$1" "$2" "$3"; fails=$((fails+1))
  fi
}
run() { # run with a fresh temp state dir and no global env
  CONSORTIUM_TIER="" CLAUDE_PLUGIN_DATA="$(mktemp -d)" bash "$SCRIPT" "$@" 2>&1
}
run_with_global() {
  local g="$1"; shift
  CONSORTIUM_TIER="$g" CLAUDE_PLUGIN_DATA="$(mktemp -d)" bash "$SCRIPT" "$@" 2>&1
}

# 1. No state, no global -> built-in default
check "resolve defaults to self-eval" "self-eval" "$(run --resolve)"

# 2. Global env is honored when no override
check "resolve uses global default" "bar-raiser-eval" "$(run_with_global bar-raiser-eval --resolve)"

# 3. Setting a tier writes a per-workspace override that --resolve then returns
DIR="$(mktemp -d)"
CONSORTIUM_TIER="" CLAUDE_PLUGIN_DATA="$DIR" bash "$SCRIPT" experts-eval >/dev/null 2>&1
check "override persists for resolve" "experts-eval" "$(CONSORTIUM_TIER="" CLAUDE_PLUGIN_DATA="$DIR" bash "$SCRIPT" --resolve)"

# 4. Override beats global default
check "override beats global" "debate" "$(CONSORTIUM_TIER="self-eval" CLAUDE_PLUGIN_DATA="$DIR" bash "$SCRIPT" debate >/dev/null 2>&1; CONSORTIUM_TIER="self-eval" CLAUDE_PLUGIN_DATA="$DIR" bash "$SCRIPT" --resolve)"

# 5. Invalid tier is rejected (non-zero exit + message)
out="$(run bogus-tier)"; rc=$?
check "invalid tier rejected" "Invalid tier" "$out"
if [ "$rc" -ne 0 ]; then printf 'ok   - invalid tier exits non-zero (rc=%s)\n' "$rc"; else printf 'FAIL - invalid tier should exit non-zero (rc=%s)\n' "$rc"; fails=$((fails+1)); fi

# 6. Show (no args) reports tier and source
check "show reports source" "built-in default" "$(run)"

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
