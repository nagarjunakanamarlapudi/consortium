#!/usr/bin/env bash
# Each case wrapper supplies its own directory and the harness working directory.
set -euo pipefail
FIXTURES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

make_repo() {
  local case_dir="$1" target="$2" agent name repo briefs
  agent="$(basename "$(dirname "$case_dir")")"
  name="$(basename "$case_dir")"
  repo="$target/repos/$agent/$name"
  briefs="$target/briefs/$agent/$name"
  # Automatic language checks resolve against the dispatching session's repo.
  git init -q "$target"
  cp "$FIXTURES/sample-repo/Makefile" "$target/Makefile"
  mkdir -p "$repo" "$briefs"
  python3 - "$FIXTURES/sample-repo" "$repo" <<'PY'
import shutil
import sys
shutil.copytree(sys.argv[1], sys.argv[2], dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"))
PY
  # Native dispatch checks run in the session's wrapper repo. Supply the
  # absolute worktree in its external brief so both the hook and agent agree.
  python3 - "$case_dir/brief.md" "$briefs/brief.md" "$repo" <<'PY'
import json
from pathlib import Path
import sys
source, target, repo = map(Path, sys.argv[1:])
text = source.read_text()
field = "worktree: " + json.dumps(str(repo.resolve())) + "\n"
target.write_text(text.replace("---\n", "---\n" + field, 1))
PY
  git -C "$repo" init -q
  if [[ -f "$case_dir/setup.patch" ]]; then
    git -C "$repo" apply "$case_dir/setup.patch"
  fi
  git -C "$repo" add .
  git -C "$repo" -c user.name='Consortium Eval' -c user.email=eval@example.invalid commit -qm 'Sample case baseline'
  if [[ -f "$case_dir/change.patch" ]]; then
    git -C "$repo" apply "$case_dir/change.patch"
  fi
}

if [[ $# -ne 2 ]]; then
  echo 'usage: make_case_repo.sh CASE_DIR DESTINATION' >&2
  exit 2
fi
make_repo "$1" "$2"
