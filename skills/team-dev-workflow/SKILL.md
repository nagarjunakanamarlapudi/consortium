---
name: team-dev-workflow
description: Use whenever the user asks to build, add, implement, change, refactor, design, fix, or ship something in this repo. Reads the active Consortium evaluation tier (off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding) and runs the matching amount of multi-agent review, announcing it first. Trigger phrases include "build X", "add Y", "implement Z", "refactor", "fix this", "let's ship". Skip only for trivial one-line mechanical edits, pure read-only investigation (use the Explore agent), or a complete patch the user pasted to apply verbatim.
---

# Consortium — team-dev workflow

## Step 0 — Resolve the active tier and announce it (ALWAYS, before anything else)

Resolve the tier:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/effort.sh" --resolve
```

Take the printed value as `TIER`, then print this one-line banner before doing any work:

`🎚️ Consortium: <TIER> · <summary> — change: /consortium:team-dev-effort off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding`

Use the matching `<summary>`:
- `off` — workflow off; plain Claude
- `self-eval` — plan → build → self-review → PR
- `experts-eval` — plan + diff reviewed by expert subagents (advisory)
- `bar-raiser-eval` — blocking bar-raiser (not in this build; running experts-eval)
- `debate` — rival approaches → judge (not in this build; running experts-eval)
- `vibe-coding` — autonomous bar-raiser run (not in this build; running experts-eval)

The banner is load-bearing: if you didn't print it, you didn't run this skill.

## Step 1 — Route by tier

- `off` → say "workflow off — proceeding as plain Claude", then STOP using this skill and handle the request normally (other skills still apply).
- `self-eval` → follow [`references/self-eval.md`](references/self-eval.md).
- `experts-eval` → follow [`references/experts-eval.md`](references/experts-eval.md).
- `bar-raiser-eval` | `debate` | `vibe-coding` → say "‹TIER› isn't implemented in this build yet — running experts-eval", then follow [`references/experts-eval.md`](references/experts-eval.md).

## Posture (applies at every tier)

- A tier is a **ceiling, not a quota** — a trivial edit stays trivial even at a high tier.
- Stay **grounded**: read the real files and `CLAUDE.md`/conventions before changing anything; cite `file:line` when you reason about code.
- **Be terse.** Don't re-print code that's already shown in the diff/edits — **no full-file dumps** — and skip step-by-step narration. Report the outcome plus the review findings that *matter* (blocking/important); concise by default, the user can ask for more.
- **Escalate, don't silently inflate**: if the task turns out much larger or riskier than the tier assumes, say so and suggest dialing the tier up — don't quietly do more process than was asked.
