# Agent Factory, Phase 1: the Plugin

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Each task's implementer is a fresh Codex session (`codex exec -m gpt-6.1-sol -c model_reasoning_effort="xhigh"`),
> briefed by the manager. Implementers never commit: every "Manager:" step is the manager's.

**Goal:** Build phase 1 of the agent factory in this plugin, on branch `agent-factory`:
- ten job descriptions;
- the `consortium` command: Codex launcher, locks, brief check, crew checks, gate runner, run log, `explain` and `eval`;
- hooks for both apps;
- the manager's playbook, with the fix recipe;
- the old workflow off by default.

**Architecture:** The Codex package, `plugins/consortium/`, stays the one canonical tree, and Claude Code reads it
through root symlinks, as it already does for this plugin's skills. Job descriptions are Claude Code agent files in
`plugins/consortium/job-descriptions/`, and root `agents/` is a directory symlink to them. A Python 3.11 command,
`consortium`, does the work neither app does: layered settings, locks, crew sizing, the brief check, the Codex
launcher, the gate runner, the run log and evals. Hooks in both apps call it. A repo that uses the factory keeps its
overrides in its own `.consortium/` folder.

**Tech Stack:** Python ≥ 3.11 (stdlib + PyYAML, as a PEP 723 `uv run --script`), pytest through
`uv run --with pytest --with pyyaml`, the repo's existing bash tests, Claude Code 2.1.309 (`claude plugin validate`,
`claude plugin eval`, plugin hooks), Codex CLI 0.160.1 (`codex exec`, plugin hooks), tmux 3.7b, git worktrees.

**Spec:** the agent factory design doc. It stays private to the first repo that uses the factory, because it quotes
that repo's history; each implementer's brief gives its path on the owner's machine. This plan carries every decision
a task needs. Section names below ("Safety", "Briefs and the brief check") are the design's.

**Not in this plan:** the rollout on the owner's machine. That covers installing, the first host repo's settings and
its Makefile locks (Tasks 13 and 14), and the phase 1 exit gate (Task 17). It is planned in that repo, because it
names it.

## Global Constraints

- All work is on branch `agent-factory`, in worktrees under `.worktrees/` (already gitignored). Push only
  `agent-factory`. Never push to, or merge into, `main` during the test. No force push in any form.
- Implementers never run `git commit`, `git push`, `git tag`, `gh pr`, or a deploy. They stop before each task's
  "Manager:" step and report.
- The plugin never names the repos it is used in.
  - `tests/test_no_host_names.py` reads names from `${CONSORTIUM_HOST_NAMES_FILE:-~/.consortium/host-names}`. That
    file has one name per line, lives on the owner's machine, and is never committed.
  - It greps `plugins/consortium`, `.claude-plugin`, `.agents`, `skills`, `hooks` and `commands` for each name, case
    insensitive, untracked files included.
  - It skips when the file is missing.
- Python ≥ 3.11. Third-party packages: PyYAML only (pytest for tests). No `jsonschema`.
- Every `codex` flag is built in one function, `launcher.codex_argv`. Every Claude Code hook name and output shape
  lives in `hooks.py`.
- State lives under `$CONSORTIUM_HOME`, default `~/.consortium`. Tests point `CONSORTIUM_HOME` at a temp dir and never
  write to the real one.
- Tiers, from the design: deep = Opus 5.5 / gpt-6.1-sol at high / xhigh; standard = Sonnet 5.5 / gpt-6.1-sol at
  medium; cheap = Haiku 5.5 / gpt-6-luna at low.
- Thresholds: no reviewers under 200 changed lines without a risk flag; code-reviewer over 800 lines.
- Detached runs use the isolated tmux server `tmux -L consortium -f /dev/null`.
- Report statuses: `DONE`, `NEEDS_CONTEXT`, `BLOCKED`, `FAILED`.
- Output schemas are OpenAI-strict: every object has `additionalProperties: false` and lists every property in
  `required`; an optional value is a type list (`["string", "null"]`) or `anyOf` with `{"type": "null"}`.
- Lock names: `test-stack`, `ios-build`, `device:<id>`, `dev-stack`, `release`, `disk`.
- Existing tests keep passing: `bash scripts/codex-plugin.test.sh`, `bash scripts/effort.test.sh`,
  `bash scripts/app-mocks.test.sh` and `bash scripts/stage*.test.sh`, each updated only where a task says so.

## Review Focus

1. **The `.consortium/` folder seen from a worktree, or from a checkout whose folder is a symlink to another
   checkout's.** Both must read the same overrides. Pinned in Task 1 and Task 2.
2. **A lock whose holder died, and a lock taken again inside itself.** A make target holding `test-stack` calls
   another that takes `test-stack`; neither case may hang. Pinned in Task 3.
3. **A brief that passes because a section is missing rather than wrong**, such as a write agent's brief with no
   `## Tests` at all. Pinned in Task 5.
4. **The hooks in the manager's own session.** No `agent_id` and no `CONSORTIUM_RUN` must mean allow, silently, in
   well under 100 ms. Pinned in Task 8.
5. **The old workflow turned back on** with `/consortium:team-dev-effort experts-eval`. Its dispatches of
   `consortium:implementer` must get a warning from the brief check, not a refusal, so the rollback keeps working.
   Pinned in Task 8.

## Decisions in this plan (the owner's to overturn)

1. Canonical files live in the Codex package, and the root names are symlinks. So job descriptions are in
   `plugins/consortium/job-descriptions/`, and `agents/` links to that folder. Codex installs only the package. In
   Claude Code a symlinked agent *file* does not load, while a symlinked folder does (checked 23 Oct).
2. Four subcommands beyond the design's five:
   - `brief-check`, so a Codex manager and the tests can run the check;
   - `gate`, which runs the full test as a script, as ci-gate's card says;
   - `runs`, for history, the weekly summary, and kept or dropped verdicts;
   - `hook`, internal.
3. ci-gate's agent runs read-only, because it only reads a failed log; the owner's call is that log reads are
   read-only. The operating part is `consortium gate`.
4. Codex launcher runs also get PATH shims that refuse `git commit`/`push`, deploy make targets and `gh pr`. Codex
   plugin hooks need trusting again after every plugin update, and until then they are silently off.
5. The crew rules fire independently. A 200 to 800 line change with no risk flag, one implementer and no dictated
   value gets no reviewers; the manager still reads every diff.
6. Until each standard-tier agent passes its cases at standard, it runs at deep: a pin in the owner's
   `~/.consortium/config.yaml`. That way nothing on Codex drops below the owner's current setting (gpt-6.1-sol at
   xhigh) by accident.
7. The brief check refuses only while the old workflow is off; with it on, it warns.
8. Each eval case runs once (`runs: 1`) during bring-up, to save quota.
9. The sweep recipe waits for phase 2. The investigator's sweep mode ships now.

## How each task lands

- [ ] **Manager, once, before Task 1:**
  `git -C ~/projects/consortium fetch origin && git -C ~/projects/consortium worktree add .worktrees/agent-factory -b agent-factory origin/main`.
  This integration checkout only ever holds reviewed commits.
- [ ] **Manager, per task:**
  1. `git -C ~/projects/consortium worktree add .worktrees/af-<n> -b af/<n>-<slug> agent-factory`
  2. Brief the implementer with the task section, Global Constraints and the spec's absolute path. Launch it detached:
     `tmux -L afjobs -f /dev/null new-session -d -s af-<n> 'codex exec -m gpt-6.1-sol -c model_reasoning_effort="xhigh" -s danger-full-access -C <worktree> -o <scratch>/af-<n>.md - < <brief>'`.
     Once Tasks 7 and 10 have landed, launch through `consortium run-codex implementer <brief>` instead: the factory
     builds the rest of itself.
  3. Read the whole diff and rerun the task's test command yourself. Reject or fix.
  4. Commit in the task worktree, then from the integration checkout run
     `git merge --no-ff af/<n>-<slug> && scripts/test.sh && git push origin agent-factory`.
  5. `git -C ~/projects/consortium worktree remove .worktrees/af-<n>`.

Tasks 3, 4, 5 and 6 can run in parallel after Task 2. Task 10 can run beside Tasks 5 to 9.

## File map (Consortium, branch `agent-factory`)

```text
plugins/consortium/                       the canonical package; Codex installs only this folder
  .codex-plugin/plugin.json               + "hooks" (Task 8); version stays 0.1.0 unless the rollout finds Codex needs a bump
  bin/consortium                          the command (Task 1)
  lib/consortium/__init__.py cli.py paths.py            Task 1
  lib/consortium/config.py registry.py explain.py       Task 2
  lib/consortium/locks.py                               Task 3
  lib/consortium/schemas.py runlog.py                   Task 4
  lib/consortium/brief.py                               Task 5
  lib/consortium/crew.py                                Task 6
  lib/consortium/launcher.py shims/{git,make,gh}        Task 7
  lib/consortium/hooks.py                               Task 8
  lib/consortium/gate.py                                Task 9
  lib/consortium/evals.py                               Task 12
  defaults.yaml                           Task 2
  schemas/envelope.json schemas/<name>.v1.json          Task 4
  hooks/hooks.json hooks/guard.py         Task 8
  job-descriptions/<name>.md              Tasks 1 and 10
  skills/agent-recipes/SKILL.md (Codex form), references/   Task 11
  skills/team-dev-workflow/SKILL.md       description only (Task 11)
  scripts/effort.sh                       built-in tier becomes off (Task 11)
  evals/_fixtures/sample-repo/  evals/<agent>/<case>/       Tasks 5 and 12
agents   -> plugins/consortium/job-descriptions             root symlinks, for Claude Code
bin      -> plugins/consortium/bin
hooks    -> plugins/consortium/hooks
evals    -> plugins/consortium/evals
skills/agent-recipes/SKILL.md             Claude form (Task 11); references -> the package's
tests/                                    pytest, one file per module
scripts/test.sh                           pytest plus every scripts/*.test.sh
```

---

### Task 1: Branch skeleton and the `consortium` entry point

**Files:**
- Modify: `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json` (top-level `name` only)
- Move: `agents/*.md` → `plugins/consortium/job-descriptions/` (`git mv`), then create the symlink `agents`
- Create: `plugins/consortium/bin/consortium`, the symlink `bin`, `plugins/consortium/lib/consortium/{__init__.py,cli.py,paths.py}`
- Create: `scripts/test.sh`, `tests/conftest.py`, `tests/test_layout.py`, `tests/test_cli.py`, `tests/test_no_host_names.py`
- Modify: `scripts/codex-plugin.test.sh` (expected root symlinks gain `agents` and `bin`)

**Interfaces:**
- Produces: `consortium.__version__ = "1.0.0-next"`. In `consortium.cli`: `main(argv: list[str] | None = None) -> int`,
  and the exit codes `EXIT_OK = 0`, `EXIT_FAIL = 1`, `EXIT_USAGE = 2`, `EXIT_WRONG_APP = 3`, `EXIT_LOCK_TIMEOUT = 4`,
  `EXIT_DISK = 5`.
- Each command module exposes `register(sub: argparse._SubParsersAction) -> None` and sets `func` on its parser.
  `cli.COMMAND_MODULES = ("explain", "locks", "brief", "crew", "launcher", "gate", "runlog", "hooks", "evals")`.
  `main` imports each with `importlib`, skipping a module only when `importlib.util.find_spec` says it doesn't exist
  yet, so a broken module still fails loudly.
- In `consortium.paths`: `package_root() -> Path` (the folder holding `defaults.yaml`, from this file's resolved
  path), `state_home() -> Path` (`$CONSORTIUM_HOME` or `~/.consortium`, created on first use),
  `repo_root(start: Path) -> Path | None`, `main_checkout(repo: Path) -> Path` (from
  `git rev-parse --path-format=absolute --git-common-dir`) and `repo_config_dir(repo: Path) -> Path`
  (`main_checkout(repo) / ".consortium"`, resolved through symlinks).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_layout.py
def test_agents_is_a_directory_symlink_to_job_descriptions(): ...   # os.path.realpath("agents") == ROOT/"plugins/consortium/job-descriptions"; all 11 existing agents reachable through it
def test_bin_links_into_the_package(): ...                          # realpath("bin/consortium") is the package's, and it is executable
def test_marketplaces_are_named_consortium_next_and_plugins_stay_consortium(): ...
def test_claude_plugin_validate_passes(): ...                       # `claude plugin validate .` exits 0; pytest.skip when claude is not on PATH
# tests/test_cli.py
def test_version(): ...                                             # `consortium version` prints "consortium 1.0.0-next"
def test_unknown_subcommand_is_usage_error(): ...                   # exit 2
def test_main_checkout_from_a_linked_worktree(tmp_path): ...        # temp repo + `git worktree add`: main_checkout(worktree) == main
def test_repo_config_dir_follows_a_symlinked_folder(tmp_path): ...  # copy B's .consortium -> A's .consortium; repo_config_dir(B worktree) == A/.consortium resolved
# tests/test_no_host_names.py
def test_the_plugin_never_names_its_host_repos(): ...               # no name from the host-names file in the shipped paths; skips without the file
```

- [ ] **Step 2: Run them and see them fail.** `uv run --with pytest --with pyyaml python -m pytest tests -q` fails
  with missing files.
- [ ] **Step 3: Write `plugins/consortium/bin/consortium`, exactly:**

```python
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from consortium.cli import main  # noqa: E402

sys.exit(main())
```

- [ ] **Step 4: Write `cli.py`, `paths.py` and `__init__.py`; do the `git mv` and the symlinks; rename both
  marketplaces to `consortium-next`.** `tests/conftest.py` puts `plugins/consortium/lib` on `sys.path` and gives a
  `run_cli(*args, env=None, cwd=None)` fixture that runs `bin/consortium` as a subprocess. `scripts/test.sh` runs
  pytest, then each `scripts/*.test.sh`, and exits non-zero if any fails.
- [ ] **Step 5: Run `scripts/test.sh`.** Expected: every test passes, the bash tests included.
- [ ] **Step 6: Prove the symlinked folder loads in Claude Code**, with the installed release switched off so
  only this tree can answer:
  `claude -p --settings '{"enabledPlugins":{"consortium@consortium":false}}' --plugin-dir "$PWD" --model haiku "List every subagent type you can dispatch whose name starts with consortium:, one per line, nothing else." < /dev/null`
  prints `consortium:spec-compliance-reviewer` among others.
- [ ] **Manager:** commit `feat(factory): branch skeleton and the consortium command`, then
  `git push -u origin agent-factory` from the integration checkout.

### Task 2: Settings, the agent registry and `consortium explain`

**Files:**
- Create: `plugins/consortium/defaults.yaml`, `lib/consortium/{config.py,registry.py,explain.py}`
- Create: `tests/test_config.py`, `tests/test_registry.py`, `tests/test_explain.py`, `tests/fixtures/jd/*.md`

**Interfaces:**
- Consumes: `paths.package_root`, `paths.state_home`, `paths.repo_config_dir`.
- Produces, in `config`: `ConfigError(Exception)`; a frozen `Settings(values: dict, sources: dict[str, str])` with
  `get(dotted: str, default=None)` and `source(dotted: str) -> str`; and
  `load_settings(repo: Path | None, brief: dict | None = None) -> Settings`. Sources read `default`, `user`, `repo`,
  `brief`, or two joined with `+` for an appended list.
- Produces, in `registry`: `parse_front_matter(text: str) -> tuple[dict, str]`, and a frozen
  `JobDescription(name, path, origin: Literal["plugin", "repo"], front: dict, meta: dict, body: str)` whose `ready`
  is true when `meta` (the `consortium:` block) validated. Also `load_registry(repo: Path | None) -> dict[str, JobDescription]`,
  and a frozen `AgentRun(name, version, app, tier, model, effort, mode, write_scope, sandbox, capabilities: tuple,
  locks: tuple, timeout_minutes, report, alt_reports: tuple, notes: tuple, sources: dict)`. Then
  `resolve_agent(name, settings, registry, brief: dict | None = None, manager_app: str | None = None) -> AgentRun`
  and `compose_prompt(job: JobDescription, run: AgentRun, brief_text: str) -> str`.
- Produces, in `config`: `glob_match(path: str, pattern: str) -> bool`, the one glob rule for every path list
  (`risk`, `test_paths`, `guard.deny_make` and Scope prefixes). `**` spans folders, a leading `**/` also matches at the
  repo root, and `*` stays inside one folder. Write a small translator; `fnmatch` alone gets both of those wrong.
- Produces, as a command: `consortium explain [AGENT] [--json] [--prompt] [--notes] [--brief FILE] [--repo DIR] [--manager claude|codex]`.

`defaults.yaml`, exactly as follows. Later tasks read these keys and add none of their own.

```yaml
# Consortium defaults: every setting has one here.
# Layers, a later one winning: this file < ~/.consortium/config.yaml < <repo>/.consortium/config.yaml < the brief.
# A list whose items all start with "+" adds to the list it overrides.
version: 1
app: either                 # claude | codex | either; either = the manager's own app
ceiling: normal             # lean | normal | full

tiers:
  deep:     {claude: {model: opus,   effort: high},   codex: {model: gpt-6.1-sol, effort: xhigh}}
  standard: {claude: {model: sonnet, effort: medium}, codex: {model: gpt-6.1-sol, effort: medium}}
  cheap:    {claude: {model: haiku,  effort: low},    codex: {model: gpt-6-luna,  effort: low}}

thresholds:
  reviewers_min_lines: 200
  code_reviewer_lines: 800

languages:
  python: [.py]
  dart: [.dart]
  javascript: [.js, .jsx, .ts, .tsx, .mjs, .cjs]
checks:                     # done-means commands per language; {tests} = the brief's test paths
  python: auto              # `make lint` if the Makefile has a lint target, else `ruff check .`; plus `pytest {tests}`
  dart: auto                # `flutter analyze` + `flutter test {tests}` if pubspec.yaml names flutter, else dart analyze/test
  javascript: auto          # `npm run lint` if package.json has it; `npm test -- {tests}`

risk:                       # flag -> path globs, matched against repo-relative paths
  auth:    ["**/auth/**", "**/authz/**", "**/authn/**", "**/login/**", "**/oauth/**"]
  crypto:  ["**/crypto/**", "**/*crypt*.*", "**/*signing*.*"]
  pii:     ["**/privacy/**", "**/*pii*.*"]
  input:   ["**/validators/**", "**/*sanitiz*.*", "**/parsers/**"]
  infra:   ["infra/**", "terraform/**", "**/*.tf", "cdk/**", "**/cdk.json", "**/Dockerfile*", "**/docker-compose*.y*ml", "k8s/**", "helm/**"]
  ci:      [".github/workflows/**", ".gitlab-ci.yml", ".circleci/**", "Jenkinsfile"]
  schema:  ["**/migrations/**", "**/schema/**/*.sql", "**/*schema*.sql", "**/*.prisma"]
  surface: ["**/models/**", "**/*_model.*", "**/*_models.*", "**/openapi*.y*ml", "**/*.proto"]
  ui:      ["**/screens/**", "**/widgets/**", "**/components/**", "**/pages/**", "**/views/**", "**/*.css", "**/*.scss", "**/*.html", "**/*.tsx", "**/*.jsx", "**/*.vue", "**/*.svelte"]
keywords:                   # flag -> whole words in the diff's added lines, any case
  auth:   [password, jwt, oauth, authorize, authenticate]
  crypto: [encrypt, decrypt, hmac, private_key]
  pii:    [date_of_birth, passport]
  input:  [deserialize, pickle]
crew:                       # flag -> the check it adds
  auth: security-reviewer
  crypto: security-reviewer
  pii: security-reviewer
  input: security-reviewer
  infra: infra-reviewer
  ci: infra-reviewer
  surface: surface-reviewer
  ui: device-qa
  schema: bar-raiser
api_patterns:               # an added line matching one makes the change "a new API"
  - '@(app|router|api|bp)\.(get|post|put|patch|delete)\('
  - '\b(app|router)\.(get|post|put|patch|delete)\(\s*[''"]/'
module_markers: [__init__.py, package.json, pubspec.yaml, go.mod, Cargo.toml, pyproject.toml]

modes:
  read-only:
    bash_allow:             # regexes; every command in a read-only agent's Bash call must match one
      - '^(cd|cat|head|tail|wc|ls|find|stat|file|sort|uniq|cut|tr|jq|diff|cmp|rg|grep|echo|pwd|which|tree|true)\b'
      - '^sed -n\b'
      - '^git (status|diff|log|show|blame|grep|ls-files|rev-parse|merge-base|cat-file|branch --show-current)\b'
      - '^consortium (explain|checks|brief-check|runs)\b'
capabilities:
  device:
    bash_allow: ['^(adb|idb|maestro|emulator)\b', '^xcrun simctl\b']
guard:
  deny:                     # regexes refused in any agent's command, in any repository
    - '\bgit\s+(?:(?:-C|-c)\s+\S+\s+|--?[\w-]+(?:=\S+)?\s+)*push(?![\w.=-])'   # after any global options; not stash push or a push.* config key
    - '\bgh\s+(pr\s+(create|merge)|release)\b'
    - '--no-verify\b'
  deny_in_repo:             # regexes refused when the command acts on the run's own repository; a scratch repository is fine
    - '\bgit\s+(?:(?:-C|-c)\s+\S+\s+|--?[\w-]+(?:=\S+)?\s+)*(commit|tag|merge|rebase)(?![\w.=-])'   # the subcommand, after any global options; not merge-base or a commit.* config key
  deny_make: []             # make target globs refused inside agents; a repo lists its deploy targets
test_paths: ["**/test/**", "**/tests/**", "**/__tests__/**", "**/*_test.*", "**/test_*.py", "**/*.test.*", "**/*.spec.*", "e2e/**"]

brief:
  sections:
    read-only:      [Task, Scope, Report]
    worktree-write: [Task, Context, Scope, Do not change, Premises, Tests, Done means, Forbidden, Stop when, Report]
    operate:        [Task, Context, Scope, Do not change, Done means, Forbidden, Stop when, Report]
  search_commands: ['^(rg|git grep|grep -r[a-zA-Z]*)\b']   # "found by:" commands the check may rerun
  raw_commands: []          # regexes a brief may not use; a repo lists the raw commands its locking make targets wrap
  word_numbers: [one, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve]

locks:
  disk_floor_gb: 0          # 0 = no floor
  wait_seconds: 3600

worktree:
  dir: .worktrees           # --new-worktree puts worktrees here, relative to the main checkout
  setup: []                 # commands run in a new worktree, under the disk lock

gate:
  command: auto             # auto: `make test` if the Makefile has it, else `npm test`, else `pytest`
  before: []
  after: []
  locks: []
  flakes_file: null         # a Markdown list of known flakes, read by the ci-gate agent

runs:
  quota_patterns: ['(?i)usage limit', '(?i)rate limit', '(?i)\bquota\b', '\b429\b']
  secret_patterns:
    - 'AKIA[0-9A-Z]{16}'
    - '-----BEGIN [A-Z ]*PRIVATE KEY-----'
    - 'gh[pousr]_[A-Za-z0-9]{36,}'
    - 'sk-[A-Za-z0-9_-]{20,}'
    - 'xox[baprs]-[A-Za-z0-9-]{10,}'

agents: {}                  # per-agent patches: agents.<name>.{app, tier, model, effort, timeout_minutes, locks, notes, done_means, forbidden, triggers, knowledge}
```

A job description's front matter is Claude Code's (`name`, `description`, `tools`, `model`, `effort`) plus one
`consortium:` block. Allowed keys, and only these:
- `version` (int ≥ 1), `station` (investigate, design, build, check, verify, ship, record or operate)
- `mode` (read-only, worktree-write or operate) and `write_scope` (all or tests; default all)
- `capabilities`: a subset of read, search, shell, edit, toolchain, device, dev-stack, cloud and web
- `tier` (deep, standard or cheap), `app` (claude, codex or either; default either), `timeout_minutes` (default 60)
- `locks`, `report` (a schema name or `none`) and `alt_reports`
- `inputs`, `done_means`, `stop_when`, `forbidden`, `knowledge` and `triggers`

Resolution order for each agent field, later winning:
1. `defaults.yaml` (the global `app` only)
2. The job description
3. The user's global `app`
4. The user's `agents.<name>`
5. The repo's global `app`
6. The repo's `agents.<name>`
7. The brief's front matter (`app`, `tier`, `model`, `effort`, `timeout_minutes`, and `report` from `alt_reports`)

`model` and `effort` come from `tiers.<tier>.<app>` unless a later layer sets them. `either` becomes `manager_app`
when given. Codex sandbox: `read-only` when the mode is read-only and the capabilities are a subset of {read, search};
otherwise `danger-full-access`.

A repo or user patch to `mode`, `report`, `station`, `version` or the body raises `ConfigError` with the message
"a repo can't rewrite a generic agent; make a repo-only agent under its own name". So does a repo agent in
`<repo>/.consortium/agents/` whose name is already a plugin agent.

`compose_prompt` builds five parts, in this order:
1. `# You are the <name> agent (job description v<version>)`, then one line: "Do this brief yourself. Dispatching
   agents, and the agent-recipes and team-dev-workflow skills, are the manager's: never use them unless your brief
   says to." A Codex agent sees the same plugin skills as its manager.
2. The body
3. `## Notes from this repo`, with one bullet per note, only when there are notes
4. `## Your brief`, then the brief's text
5. `## Your report`: end with one fenced `json` block holding a single object that matches `<report>`, with status,
   summary, decisions, evidence, changes, checks, questions and payload.

- [ ] **Step 1: Write the failing tests**

```python
def test_later_layer_wins(tmp_path): ...            # app: default "either"; user "codex" -> codex, source "user"; repo "claude" -> claude; brief "codex" -> codex, source "brief"
def test_plus_list_appends(tmp_path): ...           # repo risk.auth: ["+x/**"] -> default list + "x/**"; source "default+repo"
def test_plain_list_replaces(tmp_path): ...
def test_mixed_plus_list_is_an_error(tmp_path): ... # ["+a", "b"] -> ConfigError naming risk.auth
def test_type_mismatch_is_an_error(tmp_path): ...
def test_repo_layer_found_from_worktree_and_symlinked_copy(tmp_path): ...   # Review Focus 1
def test_registry_reads_plugin_and_repo_agents(tmp_path): ...
def test_repo_agent_cannot_shadow_a_plugin_agent(tmp_path): ...
def test_old_format_agent_is_not_ready(): ...       # every file moved in Task 1 has ready == False
def test_unknown_consortium_key_is_an_error(): ...
def test_resolve_agent_precedence(tmp_path): ...    # job tier standard + user agents.x.tier deep + app codex -> gpt-6.1-sol / xhigh, tier source "user"; brief model overrides
def test_repo_cannot_patch_mode_or_prompt(tmp_path): ...
def test_sandbox_derivation(): ...                  # read-only+[read,search] -> read-only; read-only+[read,device] -> danger-full-access; worktree-write -> danger-full-access
def test_glob_match(): ...                          # "**/auth/**" matches "auth/x.py" and "a/auth/b/c.py"; "infra/**" not "src/infra.py"; "deploy-*" matches "deploy-apps-stg"
def test_either_becomes_the_manager_app(): ...
def test_compose_prompt_parts_in_order(): ...
def test_explain_text_names_each_source(run_cli, tmp_path): ...   # lines like "tier: deep  <- you (~/.consortium/config.yaml: agents.x.tier)"
def test_explain_json_has_every_agentrun_field(run_cli, tmp_path): ...
```

- [ ] **Step 2: Run them and see them fail** (`ModuleNotFoundError: consortium.config`).
- [ ] **Step 3: Implement `config.py`, `registry.py`, `explain.py` and `defaults.yaml`** to the interfaces above.
  `explain` with no agent prints the merged global settings with sources. `--prompt` prints `compose_prompt` for an
  empty brief, and `--notes` prints only the repo notes block (the Claude playbook prepends it to briefs).
- [ ] **Step 4: Run `scripts/test.sh`.** Everything passes.
- [ ] **Manager:** commit `feat(factory): layered settings, agent registry, consortium explain`.

### Task 3: Locks

**Files:** Create `lib/consortium/locks.py`, `tests/test_locks.py`.

**Interfaces:**
- Consumes: `paths.state_home`, `paths.main_checkout`, `config.load_settings`.
- Produces: `LockTimeout(Exception)`, `DiskFloor(Exception)`, and `lock_path(name: str) -> Path`
  (`$CONSORTIUM_HOME/locks/<name with ':' and '/' as '_'>.lock`). A context manager,
  `hold(names: list[str], wait_seconds: float, owner: dict)`, takes `fcntl.flock(LOCK_EX | LOCK_NB)` on each file in
  sorted order, polling every 0.5 s. It skips names already in `CONSORTIUM_LOCKS_HELD`, and after taking a lock it
  writes the owner JSON (pid, command, cwd, run id, started) into the file. Also
  `run_locked(names: list[str], cmd: list[str], wait_seconds: float, repo: Path | None) -> int`,
  `list_locks() -> list[dict]` and `free_gb(path: Path) -> float`.
- Produces, as a command: `consortium lock NAME [NAME...] [--wait SECONDS] -- CMD...` and `consortium lock --list`.

Behaviour the tests pin:
- The child runs with `CONSORTIUM_LOCKS_HELD` extended, so a nested `consortium lock` of a held name runs straight
  through.
- `SIGINT` and `SIGTERM` are forwarded to the child. The exit code is the child's (128 + signal for a signal).
- While waiting, stderr says once: "waiting for <name>: held by pid <pid> (<command>) since <time>".
- `disk` also checks `free_gb(main checkout) >= locks.disk_floor_gb` while holding the lock. Below the floor it exits
  `EXIT_DISK` without running the command, and lists the five largest folders under `worktree.dir`.

- [ ] **Step 1: Write the failing tests**

```python
def test_runs_the_command_and_returns_its_exit_code(run_cli): ...     # -- sh -c 'exit 7' -> 7
def test_second_holder_waits_then_runs(run_cli): ...                  # A: sleep 1 holding test-stack; B starts after A ends
def test_wait_timeout_exits_4_and_names_the_holder(run_cli): ...
def test_lock_freed_when_the_holder_is_killed(run_cli): ...           # kill -9 A; B gets it within 1 s
def test_nested_same_lock_does_not_deadlock(run_cli): ...             # lock test-stack -- consortium lock test-stack -- true: exit 0 in < 2 s
def test_two_names_taken_in_sorted_order(run_cli): ...
def test_device_lock_name_is_file_safe(): ...                         # "device:emulator-5554" -> "device_emulator-5554.lock"
def test_disk_floor_refuses_without_running(run_cli, monkeypatch): ... # free 10 GB, floor 40 -> exit 5, marker file not created
def test_list_shows_holder(run_cli): ...
```

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Manager:** commit `feat(factory): one-at-a-time locks`.

### Task 4: Report schemas and the run log

**Files:**
- Create: `plugins/consortium/schemas/envelope.json` and `schemas/{case,sweep,findings,qa-lane,test-cases,gate,locations}.v1.json`
- Create: `lib/consortium/{schemas.py,runlog.py}`, `tests/test_schemas.py`, `tests/test_runlog.py`
- Create: `tests/fixtures/codex_events.jsonl`, captured from a real run in Step 3

**Interfaces:**
- Produces, in `schemas`: `load_schema(name: str) -> dict`, which composes the envelope with the payload file; for
  `none` the payload is `{"type": "null"}`. Also `validate(instance, schema: dict) -> list[str]`, a validator for
  exactly `type` (string or list), `enum`, `const`, `required`, `properties`, `additionalProperties: false`, `items`
  and `anyOf`, whose errors carry JSON paths. Also `extract_report(text: str) -> dict | None` (the last fenced `json`
  block, else the whole text if it parses) and `redact(text: str, patterns: list[str]) -> tuple[str, int]`.
- Produces, in `runlog`: `new_run_id(agent: str) -> str` (`20261024-031502-implementer-3fa2`),
  `run_dir(run_id) -> Path` (`$CONSORTIUM_HOME/runs/<id>`) and `append(record: dict) -> None`, which writes one line
  to `runs.jsonl` under an `fcntl` lock. `record_run(**fields) -> dict` is idempotent per id: a second call for the
  same id does nothing. Also `record_verdict(run_id: str, kept: bool, note: str | None)`,
  `read_records(days: int | None = None) -> list[dict]` and `summary(records, days: int) -> list[dict]` (rows by
  agent and tier: runs, kept, dropped, minutes, tokens_in, tokens_out). Plus
  `tokens_from_codex_events(lines) -> dict | None` and
  `tokens_from_claude_transcript(path: Path) -> tuple[dict | None, str | None]` (tokens and model).
- Produces, as a command: `consortium runs [--last N] [--json]`, `--summary [--days 7]`,
  `--verdict ID kept|dropped [--note TEXT]` and `--wait ID [--timeout MIN]`.

The envelope holds:
- `schema` (const), `status` (enum), `summary` and `payload`
- `decisions`: `{decision, why}`
- `evidence`: `{claim, kind: command|file|screenshot|url|query|log, ref, result}`
- `changes` (strings)
- `checks`: `{command, exit_code: integer}`
- `questions` (strings)

The payloads (spec, "Reports, gates and evidence"):
- `case.v1`: `symptom`, `repro_steps[]`, `reproduced: boolean`, `root_cause: {file, line: integer, explanation} | null`,
  `other_callers[]: {file, line, note}`, `failing_test: {file, name, command, exit_code} | null`,
  `fix_options[]: {option, tradeoffs}`, `recommendation`.
- `sweep.v1`: `bug_class`, `instances[]: {file, line, note}`, `proposed_check: {kind, where, rule}`,
  `exceptions[]: {file, line, why}`.
- `findings.v1`: `verdict: compliant|not_compliant|pass|rewrite|null`, and
  `findings[]: {severity: critical|high|medium|low, file, line: integer|null, problem, fix}`.
- `qa-lane.v1`: `platform: android|ios|web`, `persona`, `build`, `device`,
  `flows[]: {name, result: pass|fail|blocked, notes}`, and
  `defects[]: {title, steps[], expected, actual, screenshot: string|null}`.
- `test-cases.v1`: `mode: design|trace`, and `cases[]: {id, kind: positive|negative, rule, setup, steps[], expected,
  test: {file, name} | null, reason: string|null}`.
- `gate.v1`: `commit`, `command`, `exit_code`, `failed_step: string|null`,
  `failure_class: real|known_flake|infra|null`, `flake: string|null`, `reruns: integer`,
  `cleanup[]: {step, exit_code}`, `log`.
- `locations.v1`: `searches[]: {name, command, matches[]: {file, line, text, kind: defines|calls|tests|configures|other}}`
  and `too_common[]`.

A run-log line has every one of these fields, with `null` where unknown:
- `v: 1`, `type: "run"`, `id`, `agent`, `jd_version`, `app`, `model`, `effort`, `tier`
- `repo`, `worktree`, `branch`, `started`, `ended`, `minutes`, `status`, `error`
- `locks`, `tokens` (`{input, cached_input, output}`), `report` (a path), `scope_ok`, `manager`

A verdict line is `{v: 1, type: "verdict", id, kept, note, at}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_every_schema_is_openai_strict(): ...          # every object: additionalProperties false, required == set(properties)
def test_load_schema_composes_envelope_and_payload(): ...
def test_none_schema_has_null_payload(): ...
def test_validate_reports_errors_with_paths(): ...     # missing field, bad enum, extra property -> three errors naming $.payload.verdict etc.
def test_extract_report_takes_the_last_json_block(): ...
def test_redact_masks_secret_patterns(): ...           # an AKIA key and a ghp_ token -> [REDACTED], count 2
def test_append_is_one_line_per_record_under_concurrency(tmp_path): ...   # 10 processes -> 10 valid lines
def test_record_run_is_idempotent_per_id(tmp_path): ...
def test_summary_groups_by_agent_and_tier_with_verdicts(tmp_path): ...
def test_tokens_from_codex_events(): ...               # tests/fixtures/codex_events.jsonl -> totals equal the sum of its usage blocks
def test_tokens_from_claude_transcript(tmp_path): ...  # two assistant lines with message.usage and message.model
def test_runs_cli_summary_and_verdict(run_cli, tmp_path): ...
```

- [ ] **Step 2: Run, see them fail.**
- [ ] **Step 3: Capture a real Codex event stream for the fixture.** Do not guess its shape:
  `codex exec --json -m gpt-6-luna -c model_reasoning_effort="low" -s read-only "Reply with OK." < /dev/null > tests/fixtures/codex_events.jsonl`.
  `tokens_from_codex_events` sums every `usage` object it finds in events whose `type` ends in `completed`; check
  that against the fixture.
- [ ] **Step 4: Implement, and write the eight schema files. Step 5: `scripts/test.sh` passes.**
- [ ] **Manager:** commit `feat(factory): report schemas and the run log`.

### Task 5: The brief check

**Files:**
- Create: `lib/consortium/brief.py`, `tests/test_brief.py`, `tests/fixtures/briefs/*.md`
- Create: `plugins/consortium/evals/_fixtures/sample-repo/`, a small tree Task 12 reuses:
  - `Makefile` with `lint` and `test`, and `pyproject.toml`
  - `shop/{__init__,distance,pricing,auth}.py`, where `distance.py` defines `distance_km`
  - six test files that use `distance_km`: `tests/test_{distance,store_card,search,feed,share,notify}.py`
  - `web/screens/store_card.tsx`, `infra/table.py` and `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `config.Settings`, `registry.JobDescription`, `registry.resolve_agent`.
- Produces: a `Brief(front: dict, sections: dict[str, str], text: str)`, where section keys are the `## ` headings
  folded to lower case without a trailing colon. `parse_brief(text: str) -> Brief`, and a
  `Finding(rule: str, message: str)`. Then
  `check_brief(brief: Brief, job: JobDescription, mode: str, repo: Path, settings: Settings) -> list[Finding]`.
- Produces, as a command: `consortium brief-check FILE|- [--agent NAME] [--repo DIR] [--json]`. The agent comes from
  `--agent` or the brief's `agent:`. The command prints one `rule: message` per finding and exits 1 if there are any.

The rules, each named for the incident in the spec's table:

| Rule id | Refuses | Incident |
| --- | --- | --- |
| `structure` | A section in `brief.sections.<mode>` missing or empty; `## Report` not naming the agent's `report` or an `alt_reports` entry | Review Focus 3 |
| `paths-exist` | A path in the brief that does not exist | 29 Sep |
| `premises-cited` | A `## Premises` bullet that cites no `path:line` that exists with the line in range, and is not exactly `none` | 10 Sep |
| `no-exact-count-stop` | A line with an exact count (`exactly`, `expect`, `must be`, digits or `brief.word_numbers`) and a stop word (`stop`, `halt`, `abort`, `different number`), with no `about`, `~`, `roughly` or `approximately` | 16 Sep |
| `checks-per-language` | A language in Scope (by `languages`) whose `checks.<lang>` commands are not all in `## Done means` (`{tests}` matches any argument); only for modes whose briefs have a Done means, so not read-only | 22 Sep |
| `tests-complete` | `## Tests` without a `found by:` line (an exact `none — <reason>` is allowed); or a `found by:` command matching `brief.search_commands` that, rerun in the worktree for at most 10 s, lists a file the brief does not | 23 Oct |
| `dictated-verbatim` | A value in the front matter's `dictated:` list that is not word for word under `## Do not change` | June |
| `forbidden-and-stop` | For worktree-write and operate: `## Forbidden` not naming commit and push, or `## Stop when` not naming `NEEDS_CONTEXT` | Standing rule |
| `locks-and-devices` | A `brief.raw_commands` match anywhere in the brief, or an agent with the `device` capability whose brief has no `device:` | July to October |

How the checks read a brief:
- **Path candidates:** backticked spans with no spaces that contain `/`, or end in one of `.py .dart .ts .tsx .js .sql .yaml .yml .json .md .sh .swift .kt .gradle .toml`.
  An optional `:N` or `:N-M` suffix is the line range.
- **Not paths:** spans starting with `http`, `~`, `$` or `-`, or containing any of `* ? { } < > | ;`. Lines starting
  with `create:` or `gone:` after their list marker are exempt.
- **Where paths resolve:** under the front matter's `worktree:`, else the repo root.
- **What `auto` checks mean:** `checks: auto` resolves against the repo as `defaults.yaml` describes.

- [ ] **Step 1: Write the failing tests**, one fixture per rule. Each fixture uses sample-repo paths and copies the
  incident's shape; the 29 Sep one names two test files that don't exist.

```python
@pytest.mark.parametrize("fixture,rule", [
    ("missing_test_files.md", "paths-exist"),
    ("premise_without_citation.md", "premises-cited"),
    ("exact_count_stop.md", "no-exact-count-stop"),          # "expect exactly three failures — STOP and report if you get a different number"
    ("python_without_lint.md", "checks-per-language"),
    ("tests_missing_sixth_file.md", "tests-complete"),       # lists 5 of 6; found by: `rg -l distance_km tests`
    ("dictated_not_verbatim.md", "dictated-verbatim"),
    ("no_forbidden_list.md", "forbidden-and-stop"),
    ("device_without_phone.md", "locks-and-devices"),
    ("write_brief_without_tests_section.md", "structure"),   # Review Focus 3
])
def test_each_incident_is_refused(fixture, rule): ...        # exactly the expected rule fires, and only it
def test_good_briefs_pass_for_each_mode(): ...               # good_read_only.md, good_worktree_write.md, good_operate.md: no findings
def test_create_lines_are_exempt_from_paths_exist(): ...
def test_about_n_is_not_an_exact_count(): ...                # "expect about 6, report the real number" passes
def test_found_by_rerun_times_out_quietly(): ...             # a hung command -> finding "could not rerun", not a hang
def test_cli_exit_codes(run_cli): ...                        # good -> 0; bad -> 1 and "paths-exist:" on stdout
```

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Manager:** commit `feat(factory): the brief check, one rule per past incident`.

### Task 6: Crew sizing, `consortium checks`

**Files:** Create `lib/consortium/crew.py`, `tests/test_crew.py`.

**Interfaces:**
- Consumes: `config.Settings`, `registry.load_registry` (an agent counts as available only when `ready`).
- Produces: a `Change(files: list[str], added_lines: dict[str, list[str]], lines_changed: int, new_files: list[str])`,
  built by `change_from_diff(repo: Path, rng: str) -> Change` (from `git diff --numstat`, `-U0` and
  `--diff-filter=A`) or `change_from_files(files: list[str], lines: int | None) -> Change`. Then
  `CrewItem(agent: str, why: str)` and `Crew(ceiling, lines, flags: list[tuple[str, str]], always: list[CrewItem],
  crew: list[CrewItem], gates: list[CrewItem], capped: list[CrewItem])`.
- Produces: `size_crew(change, settings, registry, *, implementers=1, dictated=False, hard_to_undo=False,
  new_api=False, ceiling=None) -> Crew`, and the command
  `consortium checks (--diff RANGE | --files PATH... [--lines N]) [--implementers N] [--dictated] [--hard-to-undo] [--new-api] [--ceiling lean|normal|full] [--repo DIR] [--json]`.

The rules, from the crew widget. Each fires on its own:
- `always` is the implementer's own tests, and ci-gate.
- A dictated value, or `implementers >= 2`, adds spec-gate.
- Each risk flag adds `crew.<flag>`. A flag comes from `risk.<flag>` globs on changed files, or `keywords.<flag>` in
  added lines.
- More than `thresholds.code_reviewer_lines`, a new module (a new file named in `module_markers`), a new API
  (`api_patterns` in added lines) or `--new-api` adds code-reviewer.
- `--hard-to-undo` or the `schema` flag adds bar-raiser.
- A check whose agent is not available goes to `gates` with the reason "manager gate: <agent> is not available yet".
  It is never dropped.
- Ceiling `lean` keeps only spec-gate among the reviewers and moves the rest to `capped`, each with its reason.
  `full` adds code-reviewer to every diff.

- [ ] **Step 1: Write the failing tests**

```python
def test_small_tooling_change_gets_no_reviewers(): ...       # 1 Oct: ~100 lines in scripts/tool.py -> crew == []
def test_dictated_value_adds_spec_gate(): ...
def test_two_implementers_add_spec_gate(): ...
def test_auth_path_adds_security_reviewer(): ...
def test_auth_keyword_adds_security_reviewer(): ...
def test_ci_file_adds_infra_reviewer(): ...
def test_ui_file_adds_device_qa(): ...
def test_over_800_lines_adds_code_reviewer(): ...
def test_new_module_adds_code_reviewer(): ...
def test_new_route_adds_code_reviewer(): ...
def test_schema_change_stops_at_a_manager_gate(): ...        # bar-raiser is not available in phase 1
def test_surface_change_stops_at_a_manager_gate(): ...
def test_lean_lists_capped_checks(): ...
def test_full_adds_code_reviewer(): ...
def test_repo_plus_globs_extend_a_flag(tmp_path): ...        # repo risk.auth: ["+src/shared/authz/**"]
def test_from_a_real_diff(tmp_path): ...                     # its own temp repo (not Task 5's fixture): commit a change, checks --diff HEAD~1..HEAD
def test_json_output_shape(run_cli): ...
```

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Manager:** commit `feat(factory): consortium checks sizes the crew from the change`.

### Task 7: The Codex launcher, `consortium run-codex`, and the guard shims

**Files:**
- Create: `lib/consortium/launcher.py`, `lib/consortium/shims/{git,make,gh}` (stdlib Python, executable)
- Create: `tests/test_launcher.py`, `tests/fixtures/fake_codex.py`

**Interfaces:**
- Consumes: `brief.parse_brief` and `brief.check_brief`, `registry.resolve_agent` and `registry.compose_prompt`,
  `schemas.load_schema`, `schemas.extract_report`, `schemas.validate` and `schemas.redact`, all of `runlog`, and
  `locks.hold`.
- Produces: `CODEX_BIN` (`$CONSORTIUM_CODEX` or `codex`) and `TMUX_SOCKET` (`$CONSORTIUM_TMUX_SOCKET` or
  `consortium`). Then `codex_argv(run: AgentRun, cwd: Path, rd: Path) -> list[str]` and
  `prepare_run(agent, brief_path, repo, *, worktree=None, new_worktree=None, base=None, overrides=None) -> str`, which
  checks, resolves, writes the run folder and returns the run id. Also `start(run_id: str, detach: bool) -> None`,
  `execute(run_id: str) -> int` (the body of the internal `consortium _run ID`),
  `finalize(run_id: str, exit_code: int) -> dict`, `list_running() -> list[dict]`,
  `show_log(run_id: str, tail: int) -> str` and `wait(run_id: str, timeout_min: float) -> dict`. Task 9 reuses
  `prepare_run`, `execute` and `finalize`.
- Produces, as a command:
  `consortium run-codex AGENT BRIEF [--worktree DIR | --new-worktree NAME [--base REF]] [--tier T] [--model M] [--effort E] [--wait] [--repo DIR]`,
  plus `--list` and `--log ID [--tail N]`.

`codex_argv` returns exactly:
`[CODEX_BIN, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", 'approval_policy="never"', "-c", 'shell_environment_policy.inherit="all"', "-c", "allow_login_shell=false", "-s", sandbox, "-C", cwd, "--json", "--output-schema", rd/"schema.json", "-o", rd/"last.md", "-"]`.
The prompt (`rd/prompt.md`) goes on stdin.

What a run does:
1. **Refusals.** It refuses with exit 1, writing no run folder and starting no Codex, on any brief-check finding. It
   refuses with exit 3 when the agent resolves to `app: claude`, with the message "<agent> runs on Claude Code here;
   dispatch consortium:<agent>".
2. **Worktree.** A worktree-write agent needs `--worktree`, `--new-worktree`, or the brief's `worktree:`.
   `--new-worktree` runs `git worktree add -b <name> <main>/<worktree.dir>/<name> <base or HEAD>`, then
   `worktree.setup` under the `disk` lock.
3. **Run folder.** It writes `brief.md`, `prompt.md`, `schema.json`, `meta.json` and
   `status.json = {"status": "running"}`.
4. **Child environment.** `CONSORTIUM_RUN`, `CONSORTIUM_AGENT`, `CONSORTIUM_MODE`, `CONSORTIUM_WRITE_SCOPE` and
   `CONSORTIUM_WORKTREE`. `CONSORTIUM_GUARD` holds `guard.deny`, `guard.deny_in_repo`, `guard.deny_make` and the
   mode's allowlists, as JSON. `PATH` starts with `<package>/lib/consortium/shims`. The environment is never written
   to disk. The shim refuses a `guard.deny_in_repo` match only when the command's repository is the run's own: it
   compares `git rev-parse --git-common-dir` for the command, with its global options, and for `CONSORTIUM_WORKTREE`,
   and refuses when either cannot be resolved.
5. **Detached by default.** `tmux -L $TMUX_SOCKET -f /dev/null new-session -d -s <id> -c <cwd> -e PATH=... -e CONSORTIUM_...=... -- <package>/bin/consortium _run <id>`.
   It prints the run id at once; `--wait` blocks until `status.json` is final. `CONSORTIUM_NO_TMUX=1` runs in the
   foreground, for tests.
6. **`execute`.**
   - Holds the agent's locks, plus `device:<brief device>`.
   - Runs Codex in its own process group, with stdout to `events.jsonl` and stderr to `stderr.log`.
   - Kills the group after `timeout_minutes`.
7. **`finalize`.**
   - Reads `last.md` with `extract_report`, validates it, redacts it and writes `report.json`.
   - Statuses: no valid report means `FAILED` with error `malformed_report`; a quota pattern means `FAILED` / `quota`;
     a timeout means `FAILED` / `timeout`.
   - Records `git status --porcelain` of the main checkout before and after, and the worktree's changed files against
     Scope (with `write_scope: tests`, only test paths count). It writes `scope.json` and sets `scope_ok`.
   - Writes `status.json` and the run-log line.
8. **Shims.** Each reads `CONSORTIUM_GUARD`. On a match it prints
   "consortium: <command> is not allowed inside an agent run; the manager commits, pushes and deploys" and exits 126.
   Otherwise it runs the next real binary on PATH, after its own folder.

- [ ] **Step 1: Write the failing tests.** `fake_codex.py` records its argv, stdin and environment to
  `$FAKE_CODEX_RECORD`. It replays `tests/fixtures/codex_events.jsonl` to stdout, writes `$FAKE_CODEX_REPORT` to its
  `-o` file, and behaves per `FAKE_CODEX_MODE` (`ok`, `malformed`, `quota`, `sleep` or `write-main`).

```python
def test_bad_brief_is_refused_before_codex_starts(run_cli): ...     # 29 Sep shape: exit 1, no run folder, fake never called
def test_claude_agent_exits_3(run_cli): ...
def test_argv_for_a_read_only_reviewer(): ...                       # -s read-only, model/effort from the tier, approval never, schema and -o paths
def test_argv_for_a_device_agent_is_full_access(): ...
def test_run_records_report_tokens_and_one_log_line(run_cli): ...   # foreground; report.json valid; tokens == fixture totals
def test_malformed_report_marks_failed(run_cli): ...
def test_quota_error_is_classified(run_cli): ...
def test_timeout_kills_the_run(run_cli): ...                        # timeout_minutes 0.02
def test_scope_violation_is_recorded(run_cli): ...                  # write-main mode -> scope_ok false, path listed
def test_shims_refuse_push_and_allow_status(tmp_path): ...
def test_detached_run_in_a_private_tmux_server(run_cli): ...        # CONSORTIUM_TMUX_SOCKET=consortium-test-<pid>; --wait -> DONE; kill-server after
def test_list_and_log(run_cli): ...
def test_new_worktree_runs_setup_under_the_disk_lock(run_cli, tmp_path): ...
```

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Step 5: One real run, on the cheap tier.** Use a scratch searcher job description in `tests/fixtures/jd/`,
  and a brief asking it to run `command -v git; echo $CONSORTIUM_RUN` in the sample repo:
  `CONSORTIUM_HOME=$(mktemp -d) consortium run-codex searcher <brief> --repo <sample copy> --wait`.
  Expected: status `DONE`, a run-log line with tokens, and the report's evidence showing the shim's path for `git`
  and the run id. If `git` resolves past the shim, switch the commit and push guard to
  `GIT_CONFIG_COUNT`/`core.hooksPath` hooks that refuse when `CONSORTIUM_RUN` is set, and report that you did.
- [ ] **Manager:** commit `feat(factory): consortium run-codex, the Codex launcher`. From here on, implementers are
  launched with it.

### Task 8: Hooks for both apps

**Files:**
- Create: `plugins/consortium/hooks/hooks.json`, `plugins/consortium/hooks/guard.py`, the symlink `hooks`
- Create: `lib/consortium/hooks.py`, `tests/test_hooks.py`
- Modify: `plugins/consortium/.codex-plugin/plugin.json` (add `"hooks": "./hooks/hooks.json"`)

**Interfaces:**
- Consumes: `brief.check_brief`, `registry`, `runlog.record_run`, `runlog.tokens_from_claude_transcript` and
  `schemas`.
- Produces: `handle(event: str, payload: dict, env: Mapping[str, str]) -> dict | None`, a pure function returning the
  JSON to print, or `None` to allow silently. It is reached through `consortium hook EVENT` (the payload on stdin),
  with EVENT one of `pre-agent`, `pre-bash`, `pre-write`, `subagent-start` and `subagent-stop`.

`hooks.json`, with Claude Code's shape; Codex also expands `${CLAUDE_PLUGIN_ROOT}`:

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Agent|Task", "hooks": [{"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/consortium\" hook pre-agent", "timeout": 30}]},
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/guard.py\" pre-bash", "timeout": 15}]},
      {"matcher": "Edit|Write|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/guard.py\" pre-write", "timeout": 15}]}
    ],
    "SubagentStart": [{"hooks": [{"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/consortium\" hook subagent-start", "timeout": 15}]}],
    "SubagentStop": [{"hooks": [{"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/consortium\" hook subagent-stop", "timeout": 30}]}]
  }
}
```

`guard.py` is stdlib only. With no `agent_id` in the payload and no `CONSORTIUM_RUN` in the environment, it exits 0
and prints nothing. Otherwise it runs `<its folder>/../bin/consortium hook <event>` on the same stdin and passes its
output through.

What `handle` does for each event:
- **`pre-agent`**
  - Only for a `subagent_type` that starts with `consortium:` and whose job description is `ready`.
  - It checks `tool_input.prompt` as the brief. On findings it denies:
    `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "<the findings, one per line>"}}`.
  - Exception: while `scripts/effort.sh --resolve`, run in the payload's `cwd`, prints anything but `off`, it allows
    and returns the findings as `additionalContext` (my call 7).
- **`pre-bash`**
  - It splits the command into segments on `&&`, `||`, `;`, `|` and newlines, and also looks inside `bash -c` and
    `sh -c`.
  - It denies a `guard.deny` or `guard.deny_in_repo` match anywhere, or `make <target>` matching `guard.deny_make`,
    for any subagent or launcher run, because it sees the command an agent typed rather than the repository it
    lands in, and a test's own subprocesses never reach it.
  - For a `consortium:` read-only agent, every segment must also match `modes.read-only.bash_allow`, plus the
    `bash_allow` of its capabilities.
  - The agent's type is the payload's `agent_type`, else the file `subagent-start` wrote, else `CONSORTIUM_AGENT`.
- **`pre-write`**: it denies a read-only agent. With `write_scope: tests`, the path must match `test_paths`. With
  `CONSORTIUM_WORKTREE` set, the path must be inside it.
- **`subagent-start`**: writes `$CONSORTIUM_HOME/agents/<agent_id>.json` with `agent_type`, `session_id` and
  `started`.
- **`subagent-stop`**: only for a `consortium:` agent that is `ready`.
  - It extracts the report from `last_assistant_message` and validates it.
  - If the report is invalid and `stop_hook_active` is false, it returns
    `{"decision": "block", "reason": "Your report does not match <schema>: <errors>. End with one json block that matches it."}`.
  - Otherwise it records the run with app `claude`, model and tokens from `agent_transcript_path`, and status from
    the report (or `FAILED`/`malformed_report`). It saves the report to the run folder and removes the start file.

- [ ] **Step 1: Write the failing tests**

```python
def test_guard_allows_the_managers_commands_fast(): ...     # Review Focus 4: 20 calls of guard.py with no agent_id, median < 100 ms, no output
def test_pre_agent_denies_a_bad_brief(tmp_path): ...
def test_pre_agent_ignores_old_format_and_other_agents(): ...
def test_pre_agent_warns_when_the_old_tier_is_on(tmp_path): ...   # Review Focus 5: effort.sh resolves experts-eval -> additionalContext, no deny
def test_pre_bash_denies_commit_push_and_deploy_targets(): ...    # "git -C x commit", "bash -c 'git push'", "make deploy-x" with deny_make ["deploy-*"]; "git diff -- push.py" and "git log --grep=commit" allowed
def test_pre_bash_read_only_agent_allowlist(): ...                # "git diff" ok; "rm -rf x" denied; device agent: "adb shell" ok
def test_pre_write_respects_mode_and_scope(): ...
def test_subagent_stop_blocks_once_on_a_bad_report(tmp_path): ...
def test_subagent_stop_records_the_run(tmp_path): ...             # tokens and model from a fixture transcript; idempotent on a second call
```

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Step 5: Live check in Claude Code, on haiku.** Run
  `claude -p --settings '{"enabledPlugins":{"consortium@consortium":false}}' --plugin-dir "$PWD" --model haiku` with
  the prompt "Dispatch the consortium:searcher agent with exactly this prompt: Find distance_km." `< /dev/null`.
  Expected output names the `structure` finding (no Scope or Report). Task 15 checks the Codex side.
- [ ] **Manager:** commit `feat(factory): hooks for the brief check, the guard and the run log`.

### Task 9: The gate runner, `consortium gate`

**Files:** Create `lib/consortium/gate.py`, `tests/test_gate.py`.

**Interfaces:**
- Consumes: `launcher.prepare_run`, `launcher.execute`, `launcher.finalize`, `locks.hold`, `runlog` and `config`.
- Produces: `resolve_gate_command(repo: Path, settings) -> str`,
  `run_gate(repo: Path, *, worktree: Path | None, commit: str | None, detach: bool) -> str` (a run id, agent
  `ci-gate`), and the command `consortium gate [--worktree DIR] [--commit SHA] [--wait] [--repo DIR]`.

Inside the run (the run's `_run`, detached by default, since the gate takes longer than the 30-minute limit on
background shells):
1. Refuse if `--commit` is not the worktree's `HEAD`.
2. Hold `gate.locks`, and the `disk` floor when it is set.
3. Run each `gate.before` command; a failure is class `infra`.
4. Run the gate command as `bash -o pipefail -c '<command>'`, logging to `gate.log` in the run folder, and keep its
   exit code.
5. Always run each `gate.after` command, recording its exit code under `cleanup`.
6. On a non-zero exit, start the ci-gate agent synchronously, through `prepare_run` with a generated brief: the last
   400 lines of `gate.log` and the text of `gate.flakes_file`. On Codex it runs through the launcher (cheap tier,
   read-only). On Claude it runs through `claude -p --agent consortium:ci-gate --model <model> --json-schema <schema> --output-format json`.
   Check the flags with `claude --help` before relying on them.
7. On `known_flake`, with no rerun yet, run steps 3 to 5 once more and set `reruns` to 1.
8. Write the `gate.v1` report, the status and the run-log line.

- [ ] **Step 1: Write the failing tests** (gate commands are small shell scripts; the ci-gate agent is the fake codex)

```python
def test_green_gate_reports_exit_0_and_cleans_up(run_cli, tmp_path): ...
def test_after_steps_run_even_when_the_gate_fails(run_cli, tmp_path): ...
def test_pipefail_exit_code_is_the_gates_not_tees(run_cli, tmp_path): ...   # command "false | cat" -> exit 1
def test_known_flake_reruns_once(run_cli, tmp_path): ...                      # fails, then passes; reruns 1; final exit 0
def test_real_failure_is_not_rerun(run_cli, tmp_path): ...
def test_commit_mismatch_is_refused(run_cli, tmp_path): ...
def test_gate_holds_its_locks(run_cli, tmp_path): ...
```

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Manager:** commit `feat(factory): consortium gate runs the full test detached`.

### Task 10: The ten job descriptions

**Files:**
- Create in `plugins/consortium/job-descriptions/`: `investigator.md`, `searcher.md`, `spec-gate.md`,
  `test-designer.md`, `ci-gate.md`, `device-qa.md`, `code-reviewer.md`, `infra-reviewer.md`
- Rewrite in place: `implementer.md`, `security-reviewer.md`
- Create: `tests/test_job_descriptions.py`

Front matter for each. `model` and `effort` are the tier's Claude values. Read-only agents have
`tools: Read, Grep, Glob, Bash`; write agents add `Edit, Write`.

| Agent | station | mode | write_scope | capabilities | tier | timeout | report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| investigator | investigate | worktree-write | tests | read, search, shell, edit, toolchain, device, dev-stack | deep | 45 | case.v1; alt sweep.v1 |
| searcher | investigate | read-only | – | read, search | cheap | 15 | locations.v1 |
| implementer | build | worktree-write | all | read, search, shell, edit, toolchain | deep | 90 | none |
| spec-gate | check | read-only | – | read, search | standard | 30 | findings.v1 |
| test-designer | design | read-only | – | read, search | standard | 30 | test-cases.v1 |
| ci-gate | verify | read-only | – | read | cheap | 20 | gate.v1 |
| device-qa | verify | read-only | – | read, device, dev-stack | standard | 60 | qa-lane.v1 |
| code-reviewer | check | read-only | – | read, search | standard | 30 | findings.v1 |
| security-reviewer | check | read-only | – | read, search | deep | 30 | findings.v1 |
| infra-reviewer | check | read-only | – | read, search | deep | 30 | findings.v1 |

Each body has these sections: Purpose; When you are called; Method (numbered); Quality bar; Evidence you must show;
Stop and ask; Report. Each is under 120 lines and written from the agent's card: its Job, Done means, Stops when and
Why, behaviour only, with no repo facts.

What each body must carry:
- **investigator:** reproduce before theorizing; a failing test before any fix idea; search every caller with the
  commands shown; write only test files; hand the worktree to the implementer. Sweep mode returns `sweep.v1` with one
  proposed enforced check.
- **searcher:** each name searched in code, tests, SQL and config, with the commands it ran, so the list can be rerun.
  No judgment. "Too common" names go back with a narrower suggestion.
- **implementer:** build exactly the brief; tests beside the change; every done-means command shown with its exit
  code; every decision the brief didn't make listed; `NEEDS_CONTEXT` on a false premise; never commit; nothing outside
  Scope.
- **spec-gate:** every brief item mapped to diff lines, and every do-not-change value checked word for word. Its
  method is ported from `spec-compliance-reviewer.md`.
- **test-designer:** design mode gives a positive and a negative case for each rule, from the design alone. Trace mode
  gives a passing test for each case, or a stated reason; it reads ci-gate's log and runs no tests.
- **ci-gate:** class `real`, `known_flake` or `infra` against the flakes file, quoting the failing lines. Rerun is
  only ever recommended; the gate runner reruns.
- **device-qa:** one lane, platform by persona by flows, on the brief's `device:`. Each defect carries steps,
  expected, actual and a screenshot. Every screenshot is scanned for text and QR codes before it is reported, because
  a notification shade can show personal accounts. Never touch code.
- **code-reviewer:** correctness bugs, missing error handling, silent failures and needless complexity, ranked by
  severity, each with a concrete fix. Ported from `code-quality-reviewer.md` and `simplifier.md`.
- **security-reviewer:** authentication and authorization, input handling and injection, secrets, crypto, and data
  exposure.
- **infra-reviewer:** blast radius, resource replacement and data loss, IAM scope, config drift, CI pipeline security,
  and every allowlist or route registry the repo's notes name. Ported from `iac-change-reviewer.md` and
  `cicd-reviewer.md`.

- [ ] **Step 1: Write the failing test**

```python
NEW = ["investigator", "searcher", "implementer", "spec-gate", "test-designer", "ci-gate",
       "device-qa", "code-reviewer", "security-reviewer", "infra-reviewer"]
def test_each_new_job_description_is_ready_and_matches_its_row(): ...   # mode, tier, report, timeout, capabilities as in the table
def test_claude_model_and_effort_follow_the_tier(): ...
def test_read_only_agents_have_no_edit_tools(): ...
def test_body_has_the_seven_sections_and_names_its_report(): ...
def test_descriptions_fit_routing(): ...                                 # under 1024 characters; first sentence says when to use it
def test_old_reviewers_are_still_there_for_the_old_workflow(): ...      # until Task 16
```

- [ ] **Step 2: Run, see it fail. Step 3: write the ten files. Step 4: `scripts/test.sh` and `claude plugin validate .` pass.**
- [ ] **Manager:** commit `feat(factory): ten phase-1 job descriptions`.

### Task 11: The manager's playbook, and the old workflow off

**Files:**
- Create: `skills/agent-recipes/SKILL.md` (Claude form)
- Create: `plugins/consortium/skills/agent-recipes/SKILL.md` (Codex form)
- Create: `plugins/consortium/skills/agent-recipes/references/{manager.md,brief-template.md,fix-recipe.md}` and the
  symlink `skills/agent-recipes/references`
- Modify: `plugins/consortium/scripts/effort.sh` (`DEFAULT="off"`), and both `team-dev-workflow/SKILL.md` front matters
- Modify: `scripts/effort.test.sh`, `scripts/codex-plugin.test.sh`, `README.md`
- Create: `tests/test_playbook.py`

The front matter, in both forms:

```yaml
name: agent-recipes
description: >-
  Use when a request should go to agents rather than be done in this chat: a bug to reproduce and fix, a change
  across several files, or anything that needs the full test run, a device or a release. Routes the job, sizes the
  crew with consortium checks, writes checked briefs, dispatches Consortium agents in Claude Code or Codex, and stops
  at the gates. Skip questions, debates and small edits; do those yourself.
```

Both `team-dev-workflow` descriptions become: "The old Consortium review board, off by default. Use only when the
agent-recipes playbook routes here because a Consortium tier other than off is set (/consortium:team-dev-effort)."

`manager.md` holds these, from the spec:
- **Routing:** the prompt table and the rule of thumb. If writing the brief would take longer than doing the work, do
  it yourself; "just do it yourself" and "hand it off" override.
- **Dispatch:**
  1. Run `consortium explain <agent> --json --manager <this app>`.
  2. App `claude`: the Agent tool with `subagent_type: consortium:<agent>` and the explained `model` and `effort`,
     with `consortium explain <agent> --notes` prepended to the brief, in the background for long jobs.
  3. App `codex`: `consortium run-codex <agent> <brief file>`.
  4. On a quota error, rerun once in the other app.
- **Searcher first:** before a write brief, the searcher lists the tests; its run id or command goes on the
  `found by:` line.
- **Crew:** `consortium checks` on the predicted files before the build, and on `--diff` after it. Each gate it names
  stops the job.
- **Gates:** at the owner's gate, ask in chat. In Claude Code, also send a `PushNotification`. The manager's gate:
  read the diff, the decisions and the evidence.
- **Commit and push:** only the manager. After a green gate on an overnight job, the manager may commit, push and
  open a draft PR, and holds responsibility for it.
- **Old workflow:** if `bash "<plugin>/scripts/effort.sh" --resolve` prints anything but `off`, invoke
  team-dev-workflow instead.
- **Stepping up:** a malformed report or a failed check on mechanical work (searcher, ci-gate) reruns once, a tier up
  (`--tier`). Investigation and implementation start at deep.
- **Evidence:**
  - A UI claim needs a screenshot from the running app, scanned before it is published.
  - A data claim needs the query and its result.
  - "Fixed" needs a test that failed before the change and passes after it.
  - An outside-API claim needs the provider's page, opened.
- **Lessons:** a correction becomes, the same day, a change to a job description, the brief check or CLAUDE.md, with
  a test case. After changing a job description, run its cases in both apps (`consortium eval <agent> --app both`).

`brief-template.md` is the brief format Task 5 checks: front matter (`agent`, `worktree`, `device`, `dictated`,
optional `app`, `tier`, `model`, `effort`, `timeout_minutes`, `report`), then the ten sections in the order of
`brief.sections.worktree-write`, each with a one-line example.

`fix-recipe.md` runs in this order:
1. investigator (case)
2. **the owner picks the fix** (the owner's gate)
3. implementer, in the investigator's worktree
4. `consortium checks --diff` and the checks it names
5. `consortium gate`
6. device-qa, when a user can see the change
7. **manager review**
8. commit, push, PR, and the tracker updated by the manager (scribe arrives in phase 2)

The Codex form dispatches with `spawn_agent`, using the explained model and effort, and the prompt from
`consortium explain <agent> --prompt` plus the brief. Its first line says the launcher replaces `spawn_agent` for
read-only agents until Task 15's probe says otherwise. It has no `PushNotification`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_playbook.py`: both forms parse, with name `agent-recipes`;
  the references exist; the Claude form names `consortium explain`, `run-codex`, `checks`, `gate` and
  `PushNotification`; the Codex form names `spawn_agent` and `run-codex`; `fix-recipe.md` lists the eight steps in
  order. Update `scripts/effort.test.sh` so a fresh workspace resolves to `off`. Update `scripts/codex-plugin.test.sh`:
  both team-dev-workflow front matters contain "Use only when the agent-recipes playbook routes here", and neither
  contains "build, add, implement".
- [ ] **Step 2: Run, see them fail. Step 3: implement.** In the README, add a "Requirements" line (uv, Python 3.11+,
  tmux) and a "Turning the old workflow back on" paragraph.
- [ ] **Step 4: `scripts/test.sh` passes.**
- [ ] **Manager:** commit `feat(factory): the manager's playbook; the old workflow is off by default`.

### Task 12: Test cases and `consortium eval`

**Files:**
- Create: `plugins/consortium/evals/<agent>/<case>/case.yaml` and `brief.md`, plus `change.patch` for a case that
  reviews a diff; `plugins/consortium/evals/_fixtures/make_case_repo.sh`; the symlink `evals`
- Create: `lib/consortium/evals.py`, `tests/test_evals.py`, `plugins/consortium/evals/README.md`

**Interfaces:**
- Consumes: `launcher.prepare_run`, `launcher.execute`, `launcher.finalize`, and `schemas`.
- Produces: `load_cases(agent: str, repo: Path | None) -> list[Case]`, which reads plugin cases and, after them, the
  repo's `.consortium/evals/<agent>/`. `run_case_codex(case) -> CaseResult` and
  `run_cases_claude(agent, cases, runs) -> int`. The command is
  `consortium eval AGENT [--case NAME] [--app claude|codex|both] [--runs N] [--repo DIR]`.

A case is a `claude plugin eval` case and nothing more:
- **`case.yaml`:** `schema_version: "1.0"`, `name`, `runs: 1`, `context.scaffold_script: scaffold.sh`, and graders.
  `claude plugin eval` refuses a scaffold path outside the case folder, so each case has a two-line `scaffold.sh`
  that runs the shared `_fixtures/make_case_repo.sh` with its own folder. The builder copies the sample repo,
  applies and commits `setup.patch` when present, then applies `change.patch` uncommitted. Found at bring-up, 24 Oct.
- **The prompt:** "Dispatch the consortium:<agent> agent with the whole text of brief.md as its prompt. Then print its
  final report verbatim and nothing else."
- **Codex side:** `consortium eval` runs the same scaffold, sends `brief.md` through the launcher, and applies the
  graders to the report. It implements `regex` (on `last_message` and `files`), `file_exists` and `llm` (graded by a
  read-only gpt-6-luna run at low effort). It reports `tool_used` and `tool_order` as skipped, because they are
  Claude-only.

Cases, generic, on the sample repo:

| Agent | Case | Passes when |
| --- | --- | --- |
| spec-gate | `number-reversal`: the brief dictates `[5, 10, 15, 20]`; the diff ships `[5, 10, 20, 15]` | verdict `not_compliant`, a finding on `shop/pricing.py` |
| code-reviewer | `swallowed-error`: `except Exception: pass` around a write | a high finding naming the silent failure |
| security-reviewer | `sql-string-format`: a query built with an f-string from input | a critical or high injection finding |
| infra-reviewer | `table-replacement`: a renamed logical id on a stateful table | a finding naming replacement and data loss |
| searcher | `all-callers`: find `distance_km` | all six test files and `shop/distance.py` listed |
| implementer | `small-fix`: an off-by-one with a failing test named in the brief | status `DONE`, the test's command with exit 0 under checks |
| test-designer | `rule-pairs`: a three-rule design note | a positive and a negative case per rule |
| investigator | `hardcoded-default`: a distance measured from a hard-coded origin when the caller has none | `root_cause.file` is `shop/distance.py` and `failing_test` is set |
| ci-gate | `known-flake`: a log and a flakes file naming its signature | `failure_class: known_flake` |

- [ ] **Step 1: Write the failing tests.** In `tests/test_evals.py`: cases load in order, plugin cases first; the
  scaffold builds a repo with the patch applied; the Codex-side grader of each type works against a recorded report;
  `--app codex` with the fake codex runs a case end to end and prints pass or fail.
- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `scripts/test.sh` passes.**
- [ ] **Step 5: Bring-up runs, real and once each.**
  - `consortium eval spec-gate --app both` and `consortium eval searcher --app both`.
  - Run `claude plugin eval --help` first and use its flags (`--case`, `--eval-dir`, `--trust-plugin`).
  - Record both apps' results in `evals/README.md`.
  - Also record whether `claude plugin eval` can reach a repo's `.consortium/evals/` (`--eval-dir` must sit below the
    plugin). If it can't, `consortium eval --app claude` builds a temporary plugin folder of symlinks with `evals/`
    pointing at the repo's cases; say so in the README.
- [ ] **Manager:** commit `feat(factory): eval cases for the ten agents and consortium eval`.

### Task 15: Codex as the manager: two probes, then the playbook's Codex form (manager)

- [ ] **Probe 1: can an agent that Codex starts itself be held to read-only?** In a scratch copy of the sample repo,
  run a Codex session with the plugin. Have the playbook spawn searcher natively with a brief asking it to run
  `touch probe-$RANDOM`.
  - The probe passes if the file is not created.
  - If it fails, the Codex form keeps the launcher for every read-only agent.
- [ ] **Probe 2: do Codex hooks fire for its own agents?** Point the plugin's hooks at a logging hook in the scratch
  setup, spawn a native agent that runs one command, and read the logged payloads for `agent_type` and transcript
  fields.
  - The probe passes if PreToolUse carries enough to guard, and SubagentStop enough to write the run log.
  - Also check whether Codex reads `"hooks": "./hooks/hooks.json"`. If it doesn't, put the same hooks inline in
    `.codex-plugin/plugin.json` with `${PLUGIN_ROOT}`. Check that it doesn't run them twice.
- [ ] **Step 3:** Update the Codex form of `agent-recipes` to the probes' results. Record both results under
  "Probe results" at the end of this plan; the owner's design doc gets them too.
- [ ] **Step 4:** One small real job with Codex as the manager: the fix recipe's investigator on a known issue in a host repo. Its
  run-log line and report appear.
- [ ] **Manager:** commit the playbook change, `feat(factory): the playbook's Codex form, after the probes`.

### Task 16: Retire the old reviewers (manager)

- [ ] **Step 1: Cases first.** Run each phase-1 agent's cases in both apps (`consortium eval <agent> --app both`).
  Each standard-tier agent that passes at standard loses its deep pin in the owner's `~/.consortium/config.yaml`.
- [ ] **Step 2: Then the old reviewers go, in one commit.**
  - Delete `spec-compliance-reviewer`, `code-quality-reviewer`, `simplifier`, `iac-change-reviewer`, `cicd-reviewer`,
    `spec-clarity-reviewer`, `domain-conventions-reviewer` and `test-coverage-reviewer`.
  - Point the old workflow's references at the new names: `workflows/build.js`, `reviewer-registry.md`,
    `codex-reviewers.md` and `experts-eval.md`. `bar-raiser` stays.
  - Update `scripts/stage*.test.sh`, and Task 10's `test_old_reviewers_are_still_there_for_the_old_workflow`, to the
    new names.
- [ ] **Step 3:** `scripts/test.sh` passes.
- [ ] **Manager:** commit `refactor(factory): retire the reviewers the new agents replace`.

## Publishing

Publishing is the owner's call at the exit gate, and is not one of this plan's tasks:
- merge `agent-factory` into `main`, with both marketplace sources named `consortium` again;
- tag `v1.0.0`, a major version, because the old workflow no longer starts by itself;
- add a README note on turning the old workflow back on.

## Probe results

Filled in by Task 15.
