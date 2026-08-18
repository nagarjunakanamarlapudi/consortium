#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGE="$ROOT/plugins/consortium"
fails=0

ok() { printf 'ok   - %s\n' "$1"; }
fail() { printf 'FAIL - %s\n' "$1"; fails=$((fails + 1)); }

require_file() {
  if [ -f "$ROOT/$1" ]; then
    ok "$1 exists"
  else
    fail "$1 is missing"
  fi
}

require_file "plugins/consortium/.codex-plugin/plugin.json"
require_file ".agents/plugins/marketplace.json"
require_file "plugins/consortium/scripts/effort.sh"
require_file "plugins/consortium/skills/team-dev-effort/SKILL.md"
require_file "plugins/consortium/skills/team-dev-workflow/SKILL.md"
require_file "plugins/consortium/skills/team-dev-workflow/references/codex-reviewers.md"
require_file "plugins/consortium/skills/app-interactive-mocks/SKILL.md"

if [ ! -d "$PACKAGE/agents" ]; then
  ok "package does not contain named subagents"
else
  fail "package must use reviewer prompts instead of named subagents"
fi

if python3 -m json.tool "$PACKAGE/.codex-plugin/plugin.json" >/dev/null 2>&1; then
  ok "plugin manifest is valid JSON"
else
  fail "plugin manifest is invalid JSON"
fi

if python3 -m json.tool "$ROOT/.agents/plugins/marketplace.json" >/dev/null 2>&1; then
  ok "marketplace is valid JSON"
else
  fail "marketplace is invalid JSON"
fi

if python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
try:
    manifest = json.loads((root / "plugins/consortium/.codex-plugin/plugin.json").read_text())
    marketplace = json.loads((root / ".agents/plugins/marketplace.json").read_text())
    plugin = next(item for item in marketplace["plugins"] if item["name"] == "consortium")
    assert manifest["name"] == "consortium"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["category"] == "Development"
    assert plugin["source"] == {"source": "local", "path": "./plugins/consortium"}
    assert plugin["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert plugin["category"] == "Development"
except (AssertionError, KeyError, StopIteration, OSError, json.JSONDecodeError):
    raise SystemExit(1)
PY
then
  ok "manifest and marketplace expose the Consortium package"
else
  fail "manifest or marketplace metadata is incomplete"
fi

if python3 - "$PACKAGE" <<'PY'
import os
import sys
from pathlib import Path

package = Path(sys.argv[1]).resolve()
for path in package.rglob("*"):
    if not path.is_symlink():
        continue
    target = Path(os.path.realpath(path))
    if not target.exists():
        print(f"broken symlink: {path.relative_to(package)} -> {os.readlink(path)}", file=sys.stderr)
        raise SystemExit(1)
    if target != package and package not in target.parents:
        print(f"escaping symlink: {path.relative_to(package)} -> {os.readlink(path)}", file=sys.stderr)
        raise SystemExit(1)
PY
then
  ok "package symlinks stay within the package root"
else
  fail "package contains an escaping symlink"
fi

if python3 - "$ROOT" <<'PY'
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
expected = {
    "scripts/effort.sh": "plugins/consortium/scripts/effort.sh",
    "skills/app-interactive-mocks": "plugins/consortium/skills/app-interactive-mocks",
    "skills/team-dev-workflow/references": "plugins/consortium/skills/team-dev-workflow/references",
}
for link_name, target_name in expected.items():
    link = root / link_name
    target = root / target_name
    if not link.is_symlink() or Path(os.path.realpath(link)) != target.resolve():
        raise SystemExit(1)
PY
then
  ok "Claude compatibility symlinks resolve inward"
else
  fail "Claude compatibility symlink is missing or misdirected"
fi

effort_skill="$PACKAGE/skills/team-dev-effort/SKILL.md"
workflow_skill="$PACKAGE/skills/team-dev-workflow/SKILL.md"
mock_skill="$PACKAGE/skills/app-interactive-mocks/SKILL.md"

if grep -q 'bash "$PLUGIN_ROOT/scripts/effort.sh" --resolve' "$effort_skill" 2>/dev/null; then
  ok "effort skill invokes the canonical package script"
else
  fail "effort skill does not invoke the canonical package script"
fi

if grep -q 'bash "$PLUGIN_ROOT/scripts/effort.sh" --resolve' "$workflow_skill" 2>/dev/null \
  && grep -q 'codex-reviewers.md' "$workflow_skill" 2>/dev/null \
  && grep -qi 'read-only' "$workflow_skill" 2>/dev/null \
  && grep -qi 'explicit approval' "$workflow_skill" 2>/dev/null \
  && grep -q 'vibe-coding' "$workflow_skill" 2>/dev/null; then
  ok "workflow skill carries the Codex tier and reviewer contract"
else
  fail "workflow skill is missing Codex tier or reviewer wiring"
fi

if ! grep -Eq 'CLAUDE_PLUGIN_ROOT|EnterPlanMode|ExitPlanMode|Workflow\(' "$effort_skill" "$workflow_skill" 2>/dev/null; then
  ok "Codex wrappers do not depend on Claude-only controls"
else
  fail "Codex wrapper contains a Claude-only control"
fi

if grep -q 'You are a read-only reviewer' "$PACKAGE/skills/team-dev-workflow/references/codex-reviewers.md" 2>/dev/null \
  && grep -q 'The only write-capable subagent' "$PACKAGE/skills/team-dev-workflow/references/codex-reviewers.md" 2>/dev/null; then
  ok "reviewer prompts enforce the Codex read-only boundary"
else
  fail "reviewer prompts do not enforce the Codex read-only boundary"
fi

if grep -q 'CONSORTIUM_PLUGIN_ROOT="$PLUGIN_ROOT"' "$mock_skill" 2>/dev/null \
  && grep -q 'CONSORTIUM_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"' "$mock_skill" 2>/dev/null; then
  ok "mock skill selects the active host package root"
else
  fail "mock skill is not portable across Codex and Claude"
fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
