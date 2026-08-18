# Dual-host Consortium plugin implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Publish a self-contained Codex package from Consortium and make Aadhaa consume its immutable GitHub commit.

**Architecture:** plugins/consortium owns shared scripts, mock assets, and reviewer references. Claude-only commands, agents, and workflow instructions remain at the repository root; compatible root files symlink inward. Aadhaa declares the upstream Git subdirectory package at the exact pushed commit.

**Tech Stack:** Markdown, JSON, Bash, Git symlinks, Codex CLI, GitHub pull requests.

**Spec:** docs/superpowers/specs/2026-08-17-codex-dual-host-plugin-design.md

## Global Constraints

- The Codex manifest version is 0.1.0.
- No symlink inside plugins/consortium may resolve outside that package.
- Tier precedence is workspace override, CONSORTIUM_TIER, user default, then self-eval.
- Global state is ~/.consortium/default-tier. Git state uses Git metadata. Non-Git state is SHA-256 keyed below ~/.consortium/workspaces.
- Aadhaa uses the Consortium GitHub URL, path ./plugins/consortium, and the exact 40-character pushed commit ID.
- Every changed implementation file is independently reviewed; findings are fixed and re-reviewed before either pull request.
- No MCP server, lifecycle hook, or public plugin-directory submission is in scope.

## File Structure

### Consortium

- Create: plugins/consortium/.codex-plugin/plugin.json
- Create: .agents/plugins/marketplace.json
- Create: plugins/consortium/skills/team-dev-effort/SKILL.md
- Create: plugins/consortium/skills/team-dev-workflow/SKILL.md
- Create: plugins/consortium/skills/team-dev-workflow/references/codex-reviewers.md
- Create: scripts/codex-plugin.test.sh
- Move: scripts/effort.sh to plugins/consortium/scripts/effort.sh
- Move: skills/app-interactive-mocks/ to plugins/consortium/skills/app-interactive-mocks/
- Move: skills/team-dev-workflow/references/ to plugins/consortium/skills/team-dev-workflow/references/
- Replace root scripts/effort.sh, skills/app-interactive-mocks, and skills/team-dev-workflow/references with inward relative symlinks.
- Modify: scripts/effort.test.sh, commands/team-dev-effort.md, skills/team-dev-workflow/SKILL.md, README.md, and docs/specs/2026-06-04-consortium-design.md.

### Aadhaa

- Create: .agents/plugins/marketplace.json.
- Commit: existing .agents/ and .codex/ migration artifacts after validation.
- Modify: no application source.

## Interfaces

| Producer | Contract | Consumer |
|---|---|---|
| plugins/consortium/scripts/effort.sh | --resolve prints one valid tier plus newline | Claude and Codex workflow skills |
| plugins/consortium/scripts/effort.sh | TIER with optional --global persists a tier or exits non-zero | Claude command and Codex effort skill |
| plugins/consortium/.codex-plugin/plugin.json | skills is ./skills/ | Codex plugin discovery |
| Consortium branch | git rev-parse HEAD | Aadhaa marketplace source.sha |

---

### Task 1: Make effort state host-neutral

**Files:**
- Create: plugins/consortium/scripts/effort.sh
- Modify: scripts/effort.test.sh and commands/team-dev-effort.md
- Replace: scripts/effort.sh with a relative symlink

**Interfaces:** Produces the existing command interface with host-neutral persistence.

- [ ] **Step 1: Add failing state-contract tests**

Extend scripts/effort.test.sh with isolated HOME, Git worktree, and non-Git directory helpers. Assert Git workspace persistence, non-Git hashed state, environment precedence, user-default persistence, and that global assignment does not erase another worktree override.

~~~bash
check "environment beats user default" "experts-eval" "$(
  HOME="$TEST_HOME" CONSORTIUM_TIER="experts-eval" bash "$SCRIPT" --resolve
)"
check "other worktree retains override" "debate" "$(
  cd "$OTHER_WORKTREE" && HOME="$TEST_HOME" bash "$SCRIPT" --resolve
)"
~~~

- [ ] **Step 2: Run the test before implementation**

Run: bash scripts/effort.test.sh

Expected: non-zero because the current script writes Claude settings and has no host-neutral paths.

- [ ] **Step 3: Move and implement the script**

Use git mv to make plugins/consortium/scripts/effort.sh canonical, then create the root inward symlink.

~~~bash
STATE_HOME="$HOME/.consortium"
DEFAULT_TIER_FILE="$STATE_HOME/default-tier"

workspace_override_path() {
  if git_path="$(git rev-parse --git-path consortium/tier 2>/dev/null)"; then
    printf '%s\n' "$git_path"
    return
  fi
  workspace_hash="$(pwd -P | shasum -a 256 | awk '{print $1}')"
  printf '%s/workspaces/sha256-%s/tier\n' "$STATE_HOME" "$workspace_hash"
}
~~~

Resolve override, then CONSORTIUM_TIER, then default-tier, then self-eval. Global assignment writes only default-tier and removes only the active override.

- [ ] **Step 4: Update, verify, review, and commit**

Describe --global as a Consortium user default. Run bash scripts/effort.test.sh and verify no isolated HOME/.claude/settings.json appears.

Dispatch a read-only shell reviewer with the spec precedence and task diff. Fix all blocking or important findings, rerun the test, obtain re-review, then commit:

~~~bash
git add plugins/consortium/scripts/effort.sh scripts/effort.sh scripts/effort.test.sh commands/team-dev-effort.md
git commit -m "feat: share Consortium effort state across hosts"
~~~

### Task 2: Build the self-contained Codex package

**Files:**
- Create: manifest, marketplace, two Codex-native SKILL.md files, codex-reviewers.md, and scripts/codex-plugin.test.sh.
- Move: app-interactive-mocks and team-workflow references into plugins/consortium.
- Replace: matching Claude root paths with inward symlinks.
- Modify: app-mock skill copy commands.

**Interfaces:** Produces an installable package whose manifest exposes ./skills/.

- [ ] **Step 1: Write a failing structural package test**

Create scripts/codex-plugin.test.sh. Require the manifest, marketplace, effort script, two Codex wrappers, and mock skill. Parse JSON and reject a symlink in plugins/consortium that escapes its root.

~~~bash
python3 -m json.tool plugins/consortium/.codex-plugin/plugin.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
test -f plugins/consortium/skills/team-dev-effort/SKILL.md
test -f plugins/consortium/scripts/effort.sh
~~~

Run: bash scripts/codex-plugin.test.sh

Expected: non-zero before package files exist.

- [ ] **Step 2: Add manifest, marketplace, and content**

Create the 0.1.0 manifest with Consortium metadata, skills set to ./skills/, and Development interface metadata. Create the Consortium marketplace entry with local path ./plugins/consortium, AVAILABLE installation, and ON_INSTALL authentication.

Move shared mock assets and reviewer references into the package. Only root Claude paths may symlink, and each must target a canonical package file.

- [ ] **Step 3: Write Codex wrappers and reviewer prompts**

The effort wrapper runs the canonical script. The workflow wrapper resolves a tier, prints the existing Consortium banner, uses explicit Codex plan approval, and dispatches native read-only reviewers directed by codex-reviewers.md. Only vibe-coding may use a write-capable implementation subagent.

~~~bash
bash "$PLUGIN_ROOT/scripts/effort.sh" --resolve
bash "$PLUGIN_ROOT/scripts/effort.sh" experts-eval --global
~~~

For app mocks, select the available host root explicitly:

~~~bash
CONSORTIUM_PLUGIN_ROOT="$PLUGIN_ROOT"
if [ -z "$CONSORTIUM_PLUGIN_ROOT" ]; then
  CONSORTIUM_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"
fi
cp "$CONSORTIUM_PLUGIN_ROOT/skills/app-interactive-mocks/framework/"* design/_framework/
~~~

- [ ] **Step 4: Validate, review, and commit**

Run:

~~~bash
bash scripts/codex-plugin.test.sh
bash scripts/effort.test.sh
bash scripts/app-mocks.test.sh
bash scripts/stage2.test.sh
bash scripts/stage2b.test.sh
bash scripts/stage3.test.sh
bash scripts/stage4.test.sh
bash scripts/stage6.test.sh
bash scripts/stage7.test.sh
python3 /Users/nagarjuna/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/consortium
~~~

Dispatch independent packaging/symlink and workflow-parity reviewers. Fix all blocking or important findings, rerun relevant tests, obtain re-review, then commit:

~~~bash
git add .agents/plugins/marketplace.json plugins scripts skills
git commit -m "feat: package Consortium for Codex"
~~~

### Task 3: Document and publish the reviewed upstream branch

**Files:** Modify README.md, docs/specs/2026-06-04-consortium-design.md, and scripts/codex-plugin.test.sh.

- [ ] **Step 1: Add documentation assertions and update copy**

Require both Codex commands and Claude Code guidance:

~~~bash
rg -q 'codex plugin marketplace add nagarjunakanamarlapudi/consortium --ref v0.1.0' README.md
rg -q 'codex plugin add consortium@consortium' README.md
rg -q 'Claude Code' README.md
~~~

Document two host install paths, the new-session requirement, and effort locations/precedence. Add a June-design supersession note that points packaging and state readers to the August spec.

- [ ] **Step 2: Final upstream review and push**

Run all Task 2 checks and git diff --check. Dispatch three read-only reviewers in parallel for supply-chain integrity, Bash/symlink correctness, and Claude-versus-Codex workflow parity. Fix all blocking or important findings, rerun affected checks, then push:

~~~bash
git push -u origin codex/consortium-codex-plugin
git rev-parse HEAD
~~~

Record the 40-character result. Do not tag v0.1.0 until after the pull request merges.

### Task 4: Add Aadhaa’s immutable GitHub dependency

**Files:** Create /Users/nagarjuna/Desktop/Aadhaa_2/Aadhaa/.agents/plugins/marketplace.json and commit existing Aadhaa .agents/ and .codex/ migration artifacts.

- [ ] **Step 1: Branch and add the remote marketplace entry**

~~~bash
git -C /Users/nagarjuna/Desktop/Aadhaa_2/Aadhaa switch develop
git -C /Users/nagarjuna/Desktop/Aadhaa_2/Aadhaa switch -c codex/consortium-github-plugin
~~~

Create aadhaa-plugins with only consortium: git-subdir, URL https://github.com/nagarjunakanamarlapudi/consortium.git, path ./plugins/consortium, exact Task 3 SHA, AVAILABLE, ON_INSTALL, Development.

- [ ] **Step 2: Validate configuration and remote installation**

~~~bash
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
if rg -n '/Users/nagarjuna/projects/consortium|"source": "local"' .agents/plugins/marketplace.json; then exit 1; fi
python3 -m py_compile .codex/hooks/*.py
codex execpolicy check --rules .codex/rules/default.rules -- git push --force
~~~

Parse every .codex/agents TOML with Python tomllib and resolve AGENTS.md plus .agents/skills symlinks. Add the pushed GitHub marketplace in Codex, inspect it, install consortium@consortium, and confirm cached manifest version 0.1.0.

- [ ] **Step 3: Review and commit**

Dispatch separate read-only reviewers for Aadhaa Codex migration correctness and Git dependency provenance. Fix all blocking or important findings, obtain re-review, then commit:

~~~bash
git add AGENTS.md .agents .codex
git commit -m "chore: add Codex Consortium GitHub plugin"
~~~

### Task 5: Final review and pull requests

- [ ] **Step 1: Re-review every changed implementation file**

Dispatch final read-only reviewers for all Consortium and Aadhaa files. Reviews explicitly cover every changed script, manifest, skill, symlink, hook, rule, and configuration file. Fix blocking and important findings, rerun checks, and request re-review for changed files.

- [ ] **Step 2: Run final verification**

Run the full Consortium Bash and manifest suite, Aadhaa JSON/TOML/Python/symlink/exec-policy checks, and git diff --check in both repositories.

Expected: every command exits zero.

- [ ] **Step 3: Push and open linked pull requests**

~~~bash
git -C /Users/nagarjuna/projects/consortium push -u origin codex/consortium-codex-plugin
gh pr create --repo nagarjunakanamarlapudi/consortium --base main --head codex/consortium-codex-plugin --title "feat: package Consortium for Codex" --fill
git -C /Users/nagarjuna/Desktop/Aadhaa_2/Aadhaa push -u origin codex/consortium-github-plugin
gh pr create --repo nagarjunakanamarlapudi/Aadhaa --base develop --head codex/consortium-github-plugin --title "chore: add Codex Consortium plugin" --fill
~~~

State in Aadhaa’s pull request that it depends on Consortium and include the exact pinned commit. State in Consortium’s pull request that merge is followed by tag v0.1.0.

## Plan Self-Review

- **Spec coverage:** Tasks 1 and 2 implement shared state, safe symlinks, self-contained package, and host-specific workflow handling. Task 3 documents and publishes the source. Task 4 pins the GitHub dependency. Task 5 applies reviewer and pull-request gates.
- **Placeholder scan:** All paths, branches, repositories, commands, and manifest fields are exact. The only runtime value is generated by git rev-parse HEAD and used directly as Aadhaa’s immutable SHA.
- **Type consistency:** effort.sh --resolve, effort.sh TIER with optional --global, plugins/consortium, consortium@consortium, and the two branch names are consistent.

