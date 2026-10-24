#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

TEST_STATE_HOME="$(mktemp -d)" || exit 1
trap 'rm -rf "$TEST_STATE_HOME"' EXIT
export CONSORTIUM_HOME="$TEST_STATE_HOME"
export PYTHONDONTWRITEBYTECODE=1
status=0

printf '==> pytest\n'
if ! uv run --with pytest --with pyyaml python -m pytest tests -q -p no:cacheprovider; then
  status=1
fi

for test_script in "$ROOT"/scripts/*.test.sh; do
  printf '\n==> %s\n' "${test_script##*/}"
  if ! bash "$test_script"; then
    status=1
  fi
done

exit "$status"
