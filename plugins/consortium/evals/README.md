# Consortium agent evals

These nine cases exercise the phase-1 agents on the generic sample repository. device-qa has no case yet: it
needs a device. Each case is a native `claude plugin eval` case, with `schema_version: "1.0"`, an
`execution.prompt`, a case-local `context.scaffold_script`, graders, and `runs: 1`.

| Agent | Case | Expected behavior |
| --- | --- | --- |
| spec-gate | number-reversal | Find the reversal of the protected price thresholds |
| code-reviewer | swallowed-error | Flag a write failure hidden by `except Exception: pass` |
| security-reviewer | sql-string-format | Flag SQL injection through input interpolation |
| infra-reviewer | table-replacement | Explain table replacement and data loss |
| searcher | all-callers | List the definition and all six test files |
| implementer | small-fix | Fix the off-by-one and report passing checks |
| test-designer | rule-pairs | Give a positive and negative case for each rule |
| investigator | hardcoded-default | Reproduce the missing-origin bug before suggesting a fix |
| ci-gate | known-flake | Match the recorded failure to its known-flake signature |

## Running cases

From the plugin checkout, with the command on PATH:

```bash
export CONSORTIUM_HOME="$(mktemp -d)"
consortium eval spec-gate --app all
consortium eval searcher --case all-callers --app codex --runs 1
```

The default app comes from agent resolution for the current manager. With `app: all` and no manager, the first
of `apps` runs; `--app all` runs each app in `apps` order. `--runs` overrides the case's run count. Output is one
PASS/FAIL line per case and app, including failing grader names and reasons. Any failing case makes the command exit 1.

The native tool's format was checked with `claude plugin eval --help` and `claude plugin eval init --bare probe`
in a scratch plugin directory. The bare initializer writes `prompt.md` with execution front matter and
`graders/criteria.md` with `type: llm`; the native tool also accepts the equivalent `case.yaml` format used here.
Its exported JSON uses `cases[].arms.with[]`, `aggregates.score`, and grader `explanation` fields.

To run a case without Consortium's runner:

```bash
claude plugin eval . --eval-dir evals --case all-callers --runs 1 \
  --scaffold --trust-plugin --no-publish --ablation none --model haiku \
  --keep-temp --json /tmp/consortium-eval.json --output-dir /tmp/consortium-eval-output \
  --allow-tools Agent Read Glob Grep Bash Edit Write
```

The target is the Claude plugin root containing `.claude-plugin/plugin.json`, not the nested Codex package.
`--no-publish` is required here because the native command otherwise publishes its report when supported.

## Scaffolds and briefs

Each executable, two-line `scaffold.sh` invokes `_fixtures/make_case_repo.sh` relative to its own location,
passing its case folder and the harness working directory. The native harness executes this wrapper in place:
both bring-up cases reached their assigned repository and dispatched their agent. The shared builder has no
no-argument mode and builds only the selected case.

The builder copies the sample to `repos/<agent>/<case>/`, skipping `.venv`, `__pycache__`, and `.pytest_cache`
at every depth. It applies `setup.patch` before committing the sample baseline, then applies `change.patch`
without staging or committing it. Bugs and recorded failures therefore exist in HEAD; reviewed changes remain
the uncommitted diff. All six tests in the shared, unpatched sample still pass.

The brief stays outside the agent's repository. Codex's launcher reads the original case folder's `brief.md`.
Claude reads `briefs/<agent>/<case>/brief.md`; that copy adds the absolute assigned `worktree` to front matter.
The case's appended execution context names that external brief and its repository. The execution prompt itself
is always the dictated dispatch sentence, with only the agent name substituted.

The enclosing dispatch directory has its own Git metadata and the sample Makefile, so automatic language
checks in dispatch hooks resolve consistently. The reviewer briefs scope folders; they were written while the
brief check still asked read-only briefs for language checks, which it no longer does.

Codex uses `launcher.prepare_run` and foreground `launcher.execute`, passing the scaffold repository as
`worktree` for write agents. Its launcher enforces the report schema and checks write scope. Regex graders read
the last message or repository files; `file_exists` and `llm` graders are also supported. The LLM judge uses
`launcher.codex_argv`, the cheap Codex model and effort, a read-only sandbox, and its own strict
`{"pass": boolean, "reason": string}` schema in a temporary Git repository. Tool-use and tool-order graders are
reported as skipped on Codex. Codex regex flags support `g`, `i`, `m`, `s`, and `u`; unsupported JS-only flags
fail explicitly. Path graders accept both relative paths and native absolute paths.

Scaffolds, judge folders, native JSON/HTML output and native transcripts are retained in system temporary
folders. Run metadata stays under `CONSORTIUM_HOME`; the runner does not write a results folder in the checkout.
The ignored `evals/results/` location is reserved for native runs made by hand without an output override.

## Repo-local cases and installed plugins

Cases load from the shipped agent folder first, then from the repo's `.consortium/evals/<agent>/`, each in sorted
folder order. Names must be unique. Repo-local cases use the same layout and scaffold contract; copy the shared
`_fixtures/` alongside their agent folders when using these wrappers.

`--eval-dir` must remain below the plugin root. A direct `../outside` probe was rejected with
`--eval-dir must stay inside the plugin root (no ..)`. For a repo-local case outside the shipped suite, the Claude
adapter builds a temporary plugin folder of symlinks: the current plugin's components link back to this copy,
and `evals` links to the repo's `.consortium/evals`, including when that repo contains this plugin. The adapter's
paths and JSON handling are covered through
the fake native CLI; the authorized real bring-up used the shipped cases.

The installed `consortium@consortium` copy did not supply these agents. The eval harness creates a fresh HOME
and Claude configuration directory and loads the named plugin path. Both real JSON exports have exactly one
Consortium entry in `suite.plugins`, pointing at this worktree. Their trace initialization records
`source: consortium@inline` at that same path, alongside platform built-ins, and no installed Consortium entry.
The dispatched agent models were checked in their own subagent transcripts, not inferred from the dispatcher's
model or the case's `model` field.

## Bring-up: 24 October 2026

Each command below ran once after the per-case wrapper correction, with `CONSORTIUM_HOME` a temporary folder
(so no user settings: each agent at its own tier). No additional model runs followed the grader correction.

| Command | Codex | Claude | Command exit |
| --- | --- | --- | --- |
| `consortium eval spec-gate --app both` | PASS, gpt-6.1-sol / medium | Initial FAIL, pricing-finding grader | 1 |
| `consortium eval searcher --app both` | PASS, gpt-6-luna / low | PASS, all eight graders | 0 |

The spec-gate native run dispatched `consortium:spec-gate` with no model override. Its subagent transcript records
`claude-sonnet-5-5`, matching `model: sonnet` in its front matter; its dispatcher ran `claude-haiku-5-5`.
The searcher native run dispatched `consortium:searcher` with no model override. Both its dispatcher and its
subagent transcript record `claude-haiku-5-5`, matching the searcher's `model: haiku` front matter.

The initial spec-gate failure was a grader defect: the report correctly named the pricing file with an absolute
path, while the regex required a relative path. Path graders were corrected and tested with both forms. Regrading
the same preserved report now passes both spec-gate regex graders; the original native dispatch grader passed.
The preserved searcher report still passes all seven regex graders. These are recorded-output checks, not a
second live run, so the original command exit above remains 1.

The native spec-gate report also records an xcrun cache permission error when reading Git. It found the protected
value reversal by reading files, but could not verify the baseline diff. That is a bring-up finding; no agent was
changed to make it pass. The native engine's graders do not provide Codex's strict report-schema enforcement.
