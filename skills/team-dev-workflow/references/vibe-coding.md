# vibe-coding playbook

**Autonomous.** The build workflow run with **no human gates** — you don't present the plan or ask for approval. You draft a plan, run the build workflow (which implements + reviews + bar-raises + fixes), and hand back finished work. Use [`bar-raiser-eval.md`](bar-raiser-eval.md) for the body; this playbook changes only the **posture** and the **finish**.

## Posture
- **No plan-approval gate, no mock approval** — proceed without stopping (the human gate explicitly excludes vibe-coding; never enter plan mode).
- **Resolve ambiguity yourself** — pick the sensible default and **record the assumption** for the final report; don't stall.
- **Fresh branch only** — never the default branch, never auto-merge. Permission prompts still gate destructive ops; budget/concurrency caps apply.
- Still **grounded**, still **terse**; trivial edits still short-circuit.

## Run (autonomous)
1. Plan (grounded); for multi-file work, decompose into disjoint-file `chunks`.
2. Run the build workflow with the bar-raiser, **no gate before it**:

   `Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/build.js", args: { plan: "…", chunks: [ … ], barRaiser: true, extraReviewers: [ … ] } })`  (set `extraReviewers` by change-type + auto-discovered repo reviewers)

   It implements (parallel) → spec-compliance gate → advisory experts → **bar-raiser verdict** → fix loop (≤N rounds), returning `{ gate, reviews, barRaiser, rounds }`.

## Severity-gated finish (the ONE human seam — at the end, never mid-run)
From the returned `barRaiser`:
- **`accept`** → open a PR. Done.
- **`reject`, remaining mandates all `minor`** → open the PR anyway; list the minor concerns in the body.
- **`reject` with any `major` mandate** → **do NOT open a PR. Stop, report what's blocking, and ask the user how to proceed.**

## Output
A short report only (no code dumps): what you built, the key **assumptions** you made, the bar-raiser outcome, and either the PR link or the blocking concern + your question.
