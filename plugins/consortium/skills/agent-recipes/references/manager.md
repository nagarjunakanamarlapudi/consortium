# The manager's playbook

Use the installed `agent-recipes` skill's host-specific tier command first.
If `bash "<plugin>/scripts/effort.sh" --resolve` prints anything but `off`,
invoke `team-dev-workflow` instead of this playbook. Its dispatches receive
brief-check warnings while a tier is on; with the old workflow off, a
defective brief is refused. Do not enable a tier to bypass a failed check.

## Routing

| Request shape | Recipe or agent |
| --- | --- |
| A bug to reproduce | [Fix recipe](fix-recipe.md): investigator, owner choice, implementer, checks and verification. |
| A change across several files | Searcher, then implementer with the crew from `consortium checks`; parallel implementers get disjoint files and worktrees. |
| A question or debate | Do it yourself. |
| A small edit | Do it yourself. |
| A review | Code-reviewer, plus the checks selected by `consortium checks --diff <base>`. |
| A release | Release recipe: `consortium gate`, device-qa for visible flows, then the owner's release gate; no phase-1 agent performs a release, so the manager holds the operating step. |
| A device check | Device-qa, one assigned device and lane per brief. |
| A full test run | `consortium gate`; ci-gate reads a failed log. |

If writing the brief would take longer than doing the work, do it yourself.
The owner's explicit "just do it yourself" and "hand it off" override that
rule of thumb. An override does not remove a required gate.

## Prepare the brief and crew

Before writing a write agent's brief, dispatch searcher with a read-only
brief naming the changed symbols and search scope. Have it list every test
that touches them, including callers and contracts. Read its locations
report; list the tests in the write brief and put its run id or exact
search command on `found by:`. Do not guess test paths or counts.

Fill [the brief template](brief-template.md) with verified paths, premises
cited at file and line, the repo's instructions, every affected test and
the required language checks. Copy dictated values word for word under
Do not change. Use `create:` for new paths, `gone:` for removals, and
`none — <reason>` in Tests only when there are no applicable tests. Device
work needs `device:` and its `device:<id>` lock. Commands must use the
repo's locking wrappers, never the raw commands those wrappers protect.

Before building, run
`consortium checks --files <path>... --lines <estimate> --implementers <n>`.
Pass `--dictated`, `--hard-to-undo` and `--new-api` when applicable. Read
`always`, `crew`, `gates` and `capped`, including the reasons. Every named
gate stops the job; an unavailable agent becomes a manager gate, never a
silently dropped check. The manager reads every diff even when the crew
needs no reviewers.

Run `consortium brief-check <brief>` before dispatch. Fix findings before
starting the agent. Read-only briefs need Task, Scope and Report; operate
briefs use their configured sections. The write template's ten sections
are for worktree-write agents.

## Dispatch

1. Run `consortium explain <agent> --json --manager <this app>` before each
   dispatch. Add `--brief <brief>` to include its overrides. Use the
   resolved app, model, effort, mode, capabilities, locks and report;
   do not infer them from the job description's tier alone.
2. App `claude`: in Claude Code, use the Agent tool with
   `subagent_type: consortium:<agent>` and the explained `model` and
   `effort`. Prepend `consortium explain <agent> --notes` output (with the
   same manager and brief arguments) to the checked brief. Use background
   execution for long jobs. From a Codex manager, use Claude Code's
   `claude -p --agent consortium:<agent>` with `--model <model>` and
   `--effort <effort>`, the same notes and brief on stdin, and detached
   execution for long jobs.
3. App `codex`: `consortium run-codex <agent> <brief>` starts a detached run
   and prints its id. A write agent needs `--worktree <worktree>`,
   `--new-worktree <name> [--base <ref>]`, or the brief's `worktree:`.
   Inspect `consortium run-codex --list` and
   `consortium run-codex --log <id> --tail <n>`; use `--wait` when waiting
   synchronously. The launcher uses `tmux -L consortium -f /dev/null`.
   In a Codex manager, the skill's native `spawn_agent` instructions apply
   to write and operate modes. Read-only agents stay on the launcher:
   a spawned agent keeps the manager's permissions, whatever its role sets.
4. On a quota error, rerun once in the other app. Preserve task, scope,
   worktree and evidence, change the retry brief's `app`, and explain it
   again so model and effort resolve for that app. If the retry fails,
   return the failure to the owner; do not loop between apps.

Accept a report only after checking its schema, status, scope and evidence.
`NEEDS_CONTEXT` needs the missing decision; `BLOCKED` needs the unavailable
prerequisite; `FAILED` needs investigation. None permits the next dependent
step. Investigation and implementation start at deep. For mechanical work
(searcher, ci-gate), a malformed report or failed check gets one rerun a
tier up: cheap to standard, standard to deep. Re-explain after the tier
override; for launcher runs use `--tier <tier>`. If already deep, or the
retry fails, stop and report. Do not promote an ordinary investigation or
implementation failure into an unbounded retry loop.

## Verification and gates

After the build, run `consortium checks --diff <base>` in its worktree to
include the uncommitted edits, then run every check it names. Reconcile
the actual files and risk flags with the predicted crew. A range such as
`<base>..<head>` is appropriate only for an already committed change.

Run `consortium gate --worktree <worktree> --wait` for the full test. For a
pinned committed tree, add `--commit <sha>`; it must equal that worktree's
HEAD. The gate runs the configured command with its locks and cleanup;
ci-gate classifies a failure and a known flake may rerun once. Read the
gate report and cleanup results. A real or infrastructure failure blocks
progress. Any subsequent code change requires checks on the changed tree.

At the owner's gate, ask in chat and wait for the product choice,
production-write approval or hard-to-undo plan approval. In Claude Code,
also send a `PushNotification`; a Codex manager uses chat. The manager's
gate is a full read of the diff, the decisions list and the evidence.
Resolve unsupported decisions and claims before shipping.

Only the manager commits, pushes, opens PRs, updates the tracker or deploys.
Agents leave their work uncommitted in the assigned worktree. After a
green gate on the exact tree of an overnight job, the manager may commit,
push the branch and open a draft PR, and owns responsibility for it.
The owner's gates still apply; nothing merges without the owner.

## Evidence

- A UI claim needs a screenshot from the running app, scanned for text and
  QR codes before publication. Withhold unsafe or unscannable captures.
- A data claim needs the exact query and its result.
- "Fixed" needs a test that failed before the change and passes after it,
  with both commands, relevant output and exit codes.
- An outside-API claim needs the provider's page, opened, with its URL.

## Lessons

A correction becomes a change to a job description, the brief check or
CLAUDE.md the same day, with a test case. Keep generic lessons in the
plugin and repo-specific instructions in that repo. After changing a job
description, run its cases in both apps:
`consortium eval <agent> --app both`. Record the result; a prose reminder
without a tested change does not close the correction.
