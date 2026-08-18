#!/usr/bin/env bash
# State-contract tests for effort.sh. Each case uses an isolated user home.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/effort.sh"
TEST_ROOT="$(mktemp -d)"
TEST_HOME="$TEST_ROOT/home"
TEST_REPO="$TEST_ROOT/repo"
WORKSPACE="$TEST_REPO"
OTHER_WORKTREE="$TEST_ROOT/other-worktree"
NON_GIT_WORKSPACE="$TEST_ROOT/non-git"
fails=0

cleanup() { rm -rf "$TEST_ROOT"; }
trap cleanup EXIT

check() { # check "description" "expected" "actual"
  if [ "$3" = "$2" ]; then
    printf 'ok   - %s\n' "$1"
  else
    printf 'FAIL - %s\n      expected: %s\n      got: %s\n' "$1" "$2" "$3"
    fails=$((fails + 1))
  fi
}

check_contains() { # check_contains "description" "expected substring" "actual"
  if printf '%s' "$3" | grep -qF "$2"; then
    printf 'ok   - %s\n' "$1"
  else
    printf 'FAIL - %s\n      expected to contain: %s\n      got: %s\n' "$1" "$2" "$3"
    fails=$((fails + 1))
  fi
}

check_absent() { # check_absent "description" "path"
  if [ ! -e "$2" ]; then
    printf 'ok   - %s\n' "$1"
  else
    printf 'FAIL - %s\n      unexpected path: %s\n' "$1" "$2"
    fails=$((fails + 1))
  fi
}

run_in() { # run_in "workspace" "CONSORTIUM_TIER" [effort args...]
  local workspace="$1"
  local tier="$2"
  shift 2
  (
    cd "$workspace" || exit 1
    HOME="$TEST_HOME" CONSORTIUM_TIER="$tier" bash "$SCRIPT" "$@"
  )
}

mkdir -p "$TEST_HOME" "$NON_GIT_WORKSPACE"
git init -q "$TEST_REPO"
git -C "$TEST_REPO" config user.email effort-test@example.com
git -C "$TEST_REPO" config user.name 'Effort test'
touch "$TEST_REPO/README"
git -C "$TEST_REPO" add README
git -C "$TEST_REPO" commit -qm 'test fixture'
git -C "$TEST_REPO" worktree add -q "$OTHER_WORKTREE" -b other-worktree

# A Git worktree override persists in Git metadata and is private to that worktree.
run_in "$WORKSPACE" "" debate >/dev/null
check "Git workspace override persists" "debate" "$(run_in "$WORKSPACE" "" --resolve)"
check "workspace override beats environment" "debate" "$(run_in "$WORKSPACE" "experts-eval" --resolve)"
check "other Git worktree starts without this override" "self-eval" "$(run_in "$OTHER_WORKTREE" "" --resolve)"

# A non-Git override uses the canonical directory hash under Consortium-owned state.
run_in "$NON_GIT_WORKSPACE" "" off >/dev/null
non_git_hash="$(cd "$NON_GIT_WORKSPACE" && pwd -P | shasum -a 256 | awk '{print $1}')"
check "non-Git hashed state persists" "off" "$(run_in "$NON_GIT_WORKSPACE" "" --resolve)"
check "non-Git state is stored under its hash" "off" "$(cat "$TEST_HOME/.consortium/workspaces/sha256-$non_git_hash/tier")"

# A global assignment creates a user default and clears only the active override.
run_in "$OTHER_WORKTREE" "" debate >/dev/null
run_in "$WORKSPACE" "" bar-raiser-eval --global >/dev/null
check "user default persists" "bar-raiser-eval" "$(run_in "$WORKSPACE" "" --resolve)"
check "other worktree retains override" "debate" "$(run_in "$OTHER_WORKTREE" "" --resolve)"
check_absent "Claude settings stays absent" "$TEST_HOME/.claude/settings.json"
check_absent "Codex state stays absent" "$TEST_HOME/.codex"

# An explicit environment value overrides the user default when no workspace override exists.
check "environment beats user default" "experts-eval" "$(run_in "$WORKSPACE" "experts-eval" --resolve)"

# The existing CLI still rejects invalid tiers and reports the active tier.
invalid_output="$(run_in "$WORKSPACE" "" bogus-tier 2>&1)"
invalid_rc=$?
if [ "$invalid_rc" -ne 0 ] && printf '%s' "$invalid_output" | grep -qF 'Invalid tier'; then
  printf 'ok   - invalid tier is rejected\n'
else
  printf 'FAIL - invalid tier is rejected\n'
  fails=$((fails + 1))
fi
check_contains "show reports active tier" "Consortium tier: bar-raiser-eval (user default)" "$(run_in "$WORKSPACE" "")"

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
