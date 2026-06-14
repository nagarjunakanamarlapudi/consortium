#!/usr/bin/env bash
# Assertion suite for the app-interactive-mocks skill.
# Greps skill files for required content and shells out to `node` for pure JS logic.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/app-interactive-mocks"
FW="$SKILL/framework"
fails=0

check() { # check "desc" "expected substring" "actual"
  if printf '%s' "$3" | grep -qF -- "$2"; then printf 'ok   - %s\n' "$1"
  else printf 'FAIL - %s\n      expected to contain: %s\n      got: %s\n' "$1" "$2" "$3"; fails=$((fails+1)); fi
}
checkge() { # checkge "desc" min actual  -> actual >= min (numeric)
  if [ "$3" -ge "$2" ] 2>/dev/null; then printf 'ok   - %s (%s >= %s)\n' "$1" "$3" "$2"
  else printf 'FAIL - %s: got %s, want >= %s\n' "$1" "$3" "$2"; fails=$((fails+1)); fi
}
jeval() { node -e "$1" 2>&1; }  # run a node expression, capture stdout+stderr

# ---- Task 1: skeleton ----
check "skill dir exists" "app-interactive-mocks" "$(ls "$ROOT/skills")"
[ -d "$FW" ] && echo "ok   - framework dir exists" || { echo "FAIL - framework dir missing"; fails=$((fails+1)); }

# (Later tasks append their assertion blocks below this line.)

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
