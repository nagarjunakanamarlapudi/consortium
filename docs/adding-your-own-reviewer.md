# Adding your own reviewer

Consortium's reviewers are pluggable. There are two ways to add one — pick by **who owns the agent**.

## A) Drop a reviewer into your repo (auto-discovered — zero config)

The common case. Put a read-only reviewer agent in your repo's `.claude/agents/`, and the workflow auto-wires it — no registry edits.

For it to be picked up, the agent must be:
- **Read-only** — its `tools` include none of `Edit` / `Write` / `MultiEdit`.
- **Review-intent** — its `description` says it reviews/audits a plan, a diff, or code.
- **Self-describing triggers** — its `description` says *when* it applies (e.g. *"use when a PR touches `infra/**`"*), so the skill only fires it on matching changes.

Example (`.claude/agents/cdk-change-reviewer.md`):
```markdown
---
name: cdk-change-reviewer
description: Reviews AWS CDK infra changes for blast radius, resource replacement, and IAM scope. Use whenever a PR touches infra/stacks/, infra/config/, or infra/ssm-registry.yaml.
tools: Read, Grep, Glob, Bash
---
You review a CDK infrastructure change for deploy safety… (what to check, how to report)
```

On an infra change, the skill auto-discovers it, runs it, and folds its findings into the build review + fix loop. Writers (implementers, deployers) and non-matching reviewers are skipped.

**Dispatch note (why it's the skill, not the workflow):** dynamic workflows resolve `agentType` only against built-in + installed **plugin** agents — they do **not** see a repo's local `.claude/agents/`. So Consortium dispatches your project-local reviewers from the **skill** (the main loop, which *can* resolve them) and merges their findings with the workflow's. Nothing for you to configure — just know that's where they run.

## B) Ship a reviewer as a plugin (namespaced — rides the workflow)

If you want a reviewer shared across repos, package it as a plugin agent (namespaced, e.g. `your-plugin:foo-reviewer`) and add a row to `skills/team-dev-workflow/references/reviewer-registry.md`:

| trigger (changed paths / keywords) | reviewer | checkpoint | mode |
|---|---|---|---|
| your trigger | `your-plugin:foo-reviewer` | build | advisory |

Namespaced plugin reviewers *can* be dispatched inside the workflow, so the skill passes them as `args.extraReviewers` to `build.js` / `plan-review.js`.

## What a reviewer returns

Reviewers are dispatched with a findings schema; emit findings as `[blocking | important | minor]` with `file:line` + a concrete fix. `blocking`/`important` findings drive the fix loop; the diff is the record (no code re-prints).
