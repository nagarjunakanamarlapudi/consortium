# Consortium workflows

Bundled dynamic-workflow scripts (the deterministic engine). They are **not** a first-class plugin component, so the `team-dev-workflow` skill invokes them explicitly via the Workflow tool:

```
Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/<name>.js", args: { ... } })
```

Each script is the **workflow-preferred** path for a checkpoint; the matching steps in the per-tier playbooks are the **subagent fallback** for when the Workflow feature (Claude Code v2.1.154+) is unavailable or disabled.

## Conventions
- **`args` arrives at the script as a JSON *string*** (runtime behavior, confirmed by testing) — so **every script must `JSON.parse` it first** (all our scripts do, in their opening lines). When *invoking*, pass the full real content (e.g. `{ plan: "…full text…" }`); the script parses whatever arrives. The script and its agents see *only* what you put in `args` (the runtime can't see your conversation) — never leave it empty or send a summary.
- Scripts **orchestrate only** — no filesystem/shell. The dispatched agents (`consortium:*`) do all reading/writing.
- Agents are called by **namespaced type**: `agent(prompt, { agentType: 'consortium:<agent>', schema })`.
- Avoid `Date.now()` / `Math.random()` (they throw in the workflow runtime); pass anything time-varying via `args`.
- Respect the runtime caps (≤16 concurrent, 1000 agents/run). Reference bundled files only via `${CLAUDE_PLUGIN_ROOT}` (no `../`).

## Scripts
- `plan-review.js` — fan out the plan reviewers (spec-clarity, domain-conventions) → structured findings. Backs the **plan checkpoint**.
- `build.js` — the **build phase as one workflow**: parallel implementation over disjoint files (`consortium:implementer`) → spec-compliance gate → advisory experts (and the bar-raiser when `args.barRaiser`) → fix loop. Backs the **build** of experts-eval / bar-raiser-eval, and is the **core of `vibe-coding`** (run with no plan gate). Args: `{ plan, chunks?, barRaiser?, maxRounds? }`.
- *(coming next: `debate.js`)*
