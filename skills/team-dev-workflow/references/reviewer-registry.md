# Reviewer registry

Single source of truth for which reviewers run, at which checkpoint, in which mode. The orchestrator reads this. **Add a reviewer = add an agent file + a row here.** A row may name any installed agent — this plugin's (`consortium:…`) or another plugin's (e.g. `pr-review-toolkit:silent-failure-hunter`).

## Always-on (experts-eval and above)

| reviewer | checkpoint | mode | focus |
|---|---|---|---|
| `consortium:spec-clarity-reviewer` | plan | advisory | is the plan concrete, complete, unambiguous? |
| `consortium:domain-conventions-reviewer` | plan + build | advisory | does it respect repo conventions & reuse? |
| `consortium:spec-compliance-reviewer` | build | **gate** | does the diff match the agreed plan? |
| `consortium:code-quality-reviewer` | build | advisory | bugs, error handling, naming, simplicity |
| `consortium:simplifier` | build | advisory | reuse / simplify / cut length & vagueness — quality only (the `/simplify` pass) |

## Gate (`bar-raiser-eval` only)

| reviewer | checkpoint | mode | focus |
|---|---|---|---|
| `consortium:bar-raiser` | plan + build | **gate (verdict, ≤N rounds)** | high-bar adversarial review; rewrite mandates |

## Conditional (by change-type)

*(Now available. The skill matches the change against these triggers and passes the matching **installed** reviewers to `build.js` as `args.extraReviewers`; it skips any whose agent isn't installed — never substituting another agent.)*

| trigger (changed paths / keywords) | reviewer | checkpoint | mode |
|---|---|---|---|
| auth / crypto / input / secrets | `consortium:security-reviewer` | build | advisory |
| CI/CD pipeline files | `consortium:cicd-reviewer` | build | advisory |
| IaC (Terraform/CDK/Pulumi/CFN) | `consortium:iac-change-reviewer` | build | advisory |
| logic / behavior changes | `consortium:test-coverage-reviewer` | build | advisory |

## Project reviewers (auto-discovered) — no config needed

The skill auto-wires a **repo's own** reviewer agents. At the plan/build checkpoint, the skill:

1. **Lists the repo's agents** — read `.claude/agents/*.md` frontmatter (`name`, `description`, `tools`).
2. **Classifies an agent as a reviewer** when it is **read-only** (no `Edit` / `Write` / `MultiEdit` in `tools`) **and** its `description` says it reviews/audits a plan, a diff, or code.
3. **Selects it only if the current change matches** its description's triggers (e.g. *"use when a PR touches `infra/**`"*) — the same judgment used to auto-invoke agents. Skips writers (implementers/deployers) and non-matching reviewers; don't over-dispatch.
4. **Dispatches it — key constraint — *itself*, via the Agent tool, NOT inside the workflow.** Dynamic workflows resolve `agentType` only against built-in + **installed-plugin** agents (`consortium:*`, `pr-review-toolkit:*`, …) — they do **not** see a repo's local `.claude/agents/`. So:
   - **Plugin reviewers** (namespaced) → passed to the workflow as `args.extraReviewers`.
   - **Project-local reviewers** (bare name, from `.claude/agents/`) → the **skill dispatches them** (Agent tool), in parallel, and folds their findings into the same synthesis + fix loop.
5. **Routes by stage** — plan/spec reviewer → plan checkpoint; diff/code reviewer → build checkpoint (after `build.js` produces the diff).

Example: a repo's read-only `cdk-change-reviewer` (*"…when a PR touches `infra/**`"*) — on infra changes the skill auto-dispatches it and merges its findings. No config.

*(Want to override the heuristic? An explicit project registry would be the only reason — not built yet; add it only if the heuristic mis-fires.)*

## Rules

- A **gate** reviewer must pass before advisory reviewers run and before ship.
- **advisory** reviewers surface findings; the orchestrator fixes blocking/important ones and re-reviews, but the author decides when they're adequately addressed.
- Reviewer count **scales to the change** (posture principle): a one-file tweak may need only one reviewer; a multi-surface change pulls in the full set.
