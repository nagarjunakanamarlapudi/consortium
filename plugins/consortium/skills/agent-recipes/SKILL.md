---
name: agent-recipes
description: >-
  Use when a request should go to agents rather than be done in this chat: a bug to reproduce and fix, a change
  across several files, or anything that needs the full test run, a device or a release. Routes the job, sizes the
  crew with consortium checks, writes checked briefs, dispatches Consortium agents in Claude Code or Codex, and stops
  at the gates. Skip questions, debates and small edits; do those yourself.
---

Read-only agents go through `consortium run-codex`, not `spawn_agent`, until a probe shows Codex can hold a spawned agent to read-only.

# Agent recipes

First resolve the old workflow's tier:

```bash
bash "$PLUGIN_ROOT/scripts/effort.sh" --resolve
```

If it prints anything other than `off`, invoke `team-dev-workflow` and stop
this playbook. If resolution fails, report the error before dispatching.

Read [the manager's playbook](references/manager.md). Route the request by
its table; handle questions and small edits yourself. For a bug, follow
[the fix recipe](references/fix-recipe.md).

Before a write brief, send searcher through the launcher to find every
affected test. Use [the brief template](references/brief-template.md), put
the searcher's run id or exact command on `found by:`, and run
`consortium brief-check <brief>`. Size the crew with
`consortium checks --files <path>... --lines <estimate>` before building;
stop at every gate it names.

For each dispatch, run
`consortium explain <agent> --json --manager codex --brief <brief>`.
Use the resolved app, model, effort, mode and locks:

- App `codex`, mode `read-only`: use
  `consortium run-codex <agent> <brief>`. The launcher enforces the
  resolved sandbox, including device agents' capability requirements.
- App `codex`, write or operate mode: use `spawn_agent` with the explained
  `model` and `effort`. Build its prompt from
  `consortium explain <agent> --prompt --manager codex` output followed by
  the complete checked brief, including its front matter. Assign the
  stated worktree and locks, and validate the returned report against the
  explained report schema.
- App `claude`: dispatch the named agent through Claude Code's
  `claude -p --agent consortium:<agent>` with the explained model and
  effort and the repo notes prepended to the checked brief, as described
  in the shared playbook. Keep long jobs detached.

Apply the playbook's bounded quota and tier retries. Recompute the crew
in the changed worktree with `consortium checks --diff <base>` and run its
named checks, then `consortium gate --worktree <worktree> --wait`.

At the owner's gate, ask in chat and wait for the decision. At the
manager's gate, read the complete diff, decisions and evidence. Only the
manager commits, pushes, opens a PR or updates the tracker, after the
recipe's gates pass. Record corrections with tests as the playbook requires.
