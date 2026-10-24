---
name: agent-recipes
description: >-
  Use when a request should go to agents rather than be done in this chat: a bug to reproduce and fix, a change
  across several files, or anything that needs the full test run, a device or a release. Routes the job, sizes the
  crew with consortium checks, writes checked briefs, dispatches Consortium agents in Claude Code or Codex, and stops
  at the gates. Skip questions, debates and small edits; do those yourself.
---

# Agent recipes

First resolve the old workflow's tier:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/effort.sh" --resolve
```

If it prints anything other than `off`, invoke `team-dev-workflow` and stop
this playbook. If resolution fails, report the error before dispatching.

Read [the manager's playbook](references/manager.md). Route the request by
its table; handle questions and small edits yourself. For a bug, follow
[the fix recipe](references/fix-recipe.md).

Before a write brief, dispatch searcher to find every affected test. Use
[the brief template](references/brief-template.md), keep the searcher's run
id or exact command on `found by:`, and run `consortium brief-check <brief>`.
Size the crew with `consortium checks --files <path>... --lines <estimate>`
before building; stop at every gate it names.

For each dispatch, run
`consortium explain <agent> --json --manager claude --brief <brief>`.
Use the resolved app, model, effort, mode and locks:

- App `claude`: use the Agent tool with `subagent_type: consortium:<agent>`
  and the explained `model` and `effort`. Prepend
  `consortium explain <agent> --notes --manager claude --brief <brief>`
  output to the checked brief. Run long jobs in the background.
- App `codex`: run `consortium run-codex <agent> <brief>`, passing the
  assigned `--worktree <worktree>` for a write agent. The launcher detaches
  by default and returns a run id.

Apply the playbook's bounded quota and tier retries. Validate the report
and its evidence before continuing. Recompute the crew in the changed
worktree with `consortium checks --diff <base>` and run its named checks,
then `consortium gate --worktree <worktree> --wait`.

At the owner's gate, ask in chat, also send a `PushNotification`, and wait
for the decision. At the manager's gate, read the complete diff, decisions
and evidence. Only the manager commits, pushes, opens a PR or updates the
tracker, after the recipe's gates pass. Record corrections with tests as
the playbook requires.
