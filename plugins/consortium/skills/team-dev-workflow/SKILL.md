---
name: team-dev-workflow
description: >-
  Use when the user asks to build, add, implement, change, refactor, fix, or ship
  code or another development artifact. Resolves the active Consortium tier and
  applies the matching Codex-native planning and review workflow. Skip trivial
  mechanical edits, pure read-only investigation, a complete patch supplied
  verbatim, and direct requests for interactive/clickable app mocks or
  prototypes; use app-interactive-mocks for those design deliverables.
---

# Consortium — Codex team-dev workflow

## Pre-route — hand direct interactive mocks to app-interactive-mocks

Before resolving the tier or printing the banner, inspect the requested
deliverable. If the user directly asks for **"design mocks"**, an
**"interactive/clickable prototype"**, a **"high-fi mockup"**, a
**"walkable flow"**, or a similar interactive app mock/prototype, stop this
skill and use `app-interactive-mocks`. Do not run the team-dev tier workflow for
the mock itself. Implementing application code from an already approved mock
still uses this team-dev workflow.

## 0. Resolve and announce the active tier

Before doing task work, run:

```bash
bash "$PLUGIN_ROOT/scripts/effort.sh" --resolve
```

Use its output as `TIER`, then print exactly one Markdown blockquote line:

```text
> 🎚️ Consortium: <TIER> · <summary> — change: $team-dev-effort off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding
```

Use the matching summary:

- `off` — workflow off; plain Codex
- `self-eval` — plan → build → self-review → PR
- `experts-eval` — plan + diff reviewed by expert subagents (advisory)
- `bar-raiser-eval` — experts + a blocking bar-raiser (verdict-gated, ≤N rounds)
- `debate` — rival approaches → judge (not in this build; running experts-eval)
- `vibe-coding` — autonomous: bar-raiser quality, no gates, opens a PR

The banner is required. Print it before any work governed by this skill.

## 1. Apply the common posture

- First classify genuinely trivial work: a rename, formatting, a docs/comment
  tweak, a version bump, or a one-line change with no behavior change. Make it
  directly and stop; the tier is a ceiling, not a quota.
- Read the repository instructions and relevant source before planning.
- Keep updates and the handoff terse. Summarize changes; do not reprint code.
- Escalate if the discovered work is materially larger or riskier than the
  selected tier.
- The controller performs implementation directly. Reviewer subagents are
  read-only. `vibe-coding` is the only route allowed to delegate writes; every
  other route keeps implementation in the controller.

## 2. Route by tier

### `off`

Say `workflow off — proceeding as plain Codex`, stop this workflow, and handle
the task normally.

### `self-eval`

1. Draft a grounded plan with files, approach, and acceptance checks.
2. Present the plan and wait for the user's explicit approval before editing.
3. Implement directly.
4. Re-read the diff against the plan, simplify it, run relevant tests, fix
   findings, then commit and open a PR when the repository workflow calls for
   one. Never merge unless asked.

### `experts-eval`

1. Draft a grounded, concrete plan.
2. Read [`references/codex-reviewers.md`](references/codex-reviewers.md), then
   dispatch native Codex subagents with its `spec-clarity` and
   `domain-conventions` prompts. They must remain read-only. Apply that file's
   Codex-native project-reviewer discovery policy too.
3. Resolve blocking and important plan findings. Present the vetted plan and
   wait for the user's explicit approval before editing.
4. Implement directly; do not delegate implementation to a write-capable
   subagent.
5. Dispatch the `spec-compliance` prompt as the first read-only diff gate. Once
   compliant, dispatch the `code-quality`, `domain-conventions`, and
   `simplifier` prompts. Select conditional and project-local reviewers using
   the Codex-native policy in `references/codex-reviewers.md`, and run
   independent reviews in parallel.
6. Fix blocking and important findings, rerun affected tests, and ask the
   relevant reviewers to re-check the revised diff. Synthesize results and
   ship as the repository workflow requires.

### `bar-raiser-eval`

Run `experts-eval` with two additions:

1. Before requesting plan approval, dispatch the read-only `bar-raiser` prompt
   on the plan. Apply rewrite mandates and repeat for at most the task's stated
   review limit, or three rounds when none is stated. Request the user's
   explicit approval only after it accepts with rigor ≥4.
2. After the advisory diff review, dispatch the read-only `bar-raiser` prompt
   on the diff. Do not ship while its verdict is `reject`; surface any mandates
   that remain after the review limit.

### `debate`

Say `debate isn't implemented in this build yet — running experts-eval`, then
run `experts-eval`.

### `vibe-coding`

Run autonomously on a fresh non-default branch, with no plan-approval gate:

1. Draft a grounded plan and resolve ambiguity with sensible, recorded
   assumptions.
2. Implement directly, or dispatch a native write-capable implementation
   subagent with a precise scope. Disjoint subagents must own disjoint files.
3. Run the `experts-eval` diff gates and the read-only `bar-raiser` prompt,
   fixing findings and re-reviewing within the review limit.
4. If accepted, open a PR. If rejected with only minor mandates, open the PR
   and list them. If any major mandate remains, do not open a PR; stop and ask
   the user how to proceed.

## 3. Reviewer dispatch boundary

Codex plugins do not package named subagents. Always create native subagents
for the current task and supply the appropriate prompt from
`references/codex-reviewers.md`. Every reviewer dispatch must explicitly say:

- review only; do not edit files, commit, push, or perform state-changing
  actions;
- do not spawn another subagent;
- return findings to the controller with file and line evidence.

The controller owns all fixes except for the explicit `vibe-coding`
implementation exception above.
