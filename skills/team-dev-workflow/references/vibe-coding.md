# vibe-coding playbook

**Autonomous.** This is [`bar-raiser-eval.md`](bar-raiser-eval.md) run with **no human gates** — you do not stop to present the plan or ask for approval. You plan, build, and run the bar-raiser gate end-to-end yourself, then hand back finished work. Use the bar-raiser-eval pipeline as the body; this playbook changes only the **posture** and the **finish**.

## Posture (how vibe differs)
- **No plan-approval gate, no mock approval** — proceed without stopping for the user (the human plan-approval gate explicitly excludes vibe-coding).
- **Resolve ambiguity yourself** — when something is underspecified, pick the sensible default and **record the assumption** for your final report; do not stop to ask.
- **Fresh branch only** — create a new branch and work there; never commit to the default branch, never auto-merge. Permission prompts still gate destructive ops, and the budget/concurrency caps still apply.
- Still **grounded**, still **terse**; trivial edits still **short-circuit** (handled upstream).

## Run (autonomous)
1. Plan (grounded); decompose into disjoint-file waves.
2. Build (max-parallel over disjoint files).
3. Bar-raiser-eval build checkpoint: spec-compliance gate → advisory experts → **bar-raiser verdict**, with the rewrite-mandate loop (≤ N rounds, default 3).

## Severity-gated finish (the ONE human seam — at the end, never mid-run)
After the loop settles, branch on the bar-raiser's remaining concerns:
- **`accept`** → open a PR. Done.
- **`reject`, remaining concerns all `minor`** → open the PR anyway; list the minor concerns in the PR body.
- **`reject` with any `major` concern** → **do NOT open a PR. Stop, report what's blocking, and ask the user how to proceed.** This is the only time vibe-coding returns to the human.

## Output
A short report only (no code dumps): what you built, the key **assumptions** you made, the bar-raiser outcome, and either the PR link or the blocking concern + your question.
