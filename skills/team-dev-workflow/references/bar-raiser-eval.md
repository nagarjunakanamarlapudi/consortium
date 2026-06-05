# bar-raiser-eval playbook

Everything [`experts-eval.md`](experts-eval.md) does, **plus a blocking bar-raiser** — enabled on the build workflow. The bar-raiser (`consortium:bar-raiser`) is a single authoritative gatekeeper; its verdict gates inside the build workflow's fix loop.

## Plan checkpoint
Same as experts-eval (run `plan-review.js`, revise), **then dispatch `consortium:bar-raiser` on the plan** — it must clear the bar (rigor ≥ 4; apply its rewrite mandates and re-dispatch, ≤N rounds) — *before* the plan-mode approval gate. So the user approves a bar-raised plan.

## Build (one workflow, bar-raiser enabled)
Run the build workflow with `barRaiser: true`:

`Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/build.js", args: { plan: "…the approved plan…", barRaiser: true } })`

It runs **implement → spec-compliance gate → advisory experts → bar-raiser verdict → fix loop** (≤N rounds, applying the bar-raiser's rewrite mandates each round), returning `{ gate, reviews, barRaiser, rounds }`.

## Finish
- If the returned `barRaiser.verdict` is `accept` → synthesize, present, ship.
- If it's still `reject` after the workflow's N rounds → **stop and surface to the user** the remaining mandates; don't ship under the bar.

Everything else (synthesis & presentation, grounding, the human plan-approval gate, terse output, ship-as-PR) is as in experts-eval / the skill.
