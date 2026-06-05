# Reviewer registry

Single source of truth for which reviewers run, at which checkpoint, in which mode. The orchestrator reads this. **Add a reviewer = add an agent file + a row here.** A row may name any installed agent — this plugin's (`consortium:…`) or another plugin's (e.g. `pr-review-toolkit:silent-failure-hunter`).

## Always-on (experts-eval and above)

| reviewer | checkpoint | mode | focus |
|---|---|---|---|
| `consortium:spec-clarity-reviewer` | plan | advisory | is the plan concrete, complete, unambiguous? |
| `consortium:domain-conventions-reviewer` | plan + build | advisory | does it respect repo conventions & reuse? |
| `consortium:spec-compliance-reviewer` | build | **gate** | does the diff match the agreed plan? |
| `consortium:code-quality-reviewer` | build | advisory | bugs, error handling, naming, simplicity |

## Conditional (by change-type)

*(These reviewers land in Stage 5. Until a reviewer's agent is installed, the orchestrator **skips its row** — it does not substitute another agent.)*

| trigger (changed paths / keywords) | reviewer | checkpoint | mode |
|---|---|---|---|
| auth / crypto / input / secrets | `consortium:security-reviewer` | build | advisory |
| CI/CD pipeline files | `consortium:cicd-reviewer` | build | advisory |
| IaC (Terraform/CDK/Pulumi/CFN) | `consortium:iac-change-reviewer` | build | advisory |
| logic / behavior changes | `consortium:test-coverage-reviewer` | build | advisory |

## Rules

- A **gate** reviewer must pass before advisory reviewers run and before ship.
- **advisory** reviewers surface findings; the orchestrator fixes blocking/important ones and re-reviews, but the author decides when they're adequately addressed.
- Reviewer count **scales to the change** (posture principle): a one-file tweak may need only one reviewer; a multi-surface change pulls in the full set.
