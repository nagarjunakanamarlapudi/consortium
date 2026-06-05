---
name: team-dev-workflow
description: Use whenever the user asks to build, add, implement, change, refactor, design, fix, or ship something in this repo. Reads the active Consortium evaluation tier (off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding) and runs the matching amount of multi-agent review, announcing it first. Trigger phrases include "build X", "add Y", "implement Z", "refactor", "fix this", "let's ship". Skip for trivial mechanical edits (a rename, formatting, a docs/comment tweak, a version bump, or a one-liner with no behavior change), pure read-only investigation (use the Explore agent), or a complete patch the user pasted to apply verbatim.
---

# Consortium — team-dev workflow

## Step 0 — Resolve the active tier and announce it (ALWAYS, before anything else)

Resolve the tier:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/effort.sh" --resolve
```

Take the printed value as `TIER`, then **print the banner as a single Markdown blockquote line** before doing any work. The leading `> ` makes Claude Code render it **dimmed/muted** so it stays unobtrusive. Emit exactly this shape (one line, starting with `> `):

```
> 🎚️ Consortium: <TIER> · <summary> — change: /consortium:team-dev-effort off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding
```

Use the matching `<summary>`:
- `off` — workflow off; plain Claude
- `self-eval` — plan → build → self-review → PR
- `experts-eval` — plan + diff reviewed by expert subagents (advisory)
- `bar-raiser-eval` — experts + a blocking bar-raiser (verdict-gated, ≤N rounds)
- `debate` — rival approaches → judge (not in this build; running experts-eval)
- `vibe-coding` — autonomous: bar-raiser quality, no gates, opens a PR

The banner is load-bearing: if you didn't print it, you didn't run this skill.

## Step 1 — Route by tier

- **Trivial change first (any tier):** if the change is genuinely trivial — a variable rename, formatting, a docs/comment edit, a version bump, or a one-liner with **no behavior change** — just make the edit directly and stop. No plan, no reviewers, no gate, no review loop. A tier is a **ceiling, not a floor**. (Even `vibe-coding` just does trivial work directly.)
- `off` → say "workflow off — proceeding as plain Claude", then STOP using this skill and handle the request normally (other skills still apply).
- `self-eval` → follow [`references/self-eval.md`](references/self-eval.md).
- `experts-eval` → follow [`references/experts-eval.md`](references/experts-eval.md).
- `bar-raiser-eval` → follow [`references/bar-raiser-eval.md`](references/bar-raiser-eval.md).
- `debate` → say "debate isn't implemented in this build yet — running experts-eval", then follow [`references/experts-eval.md`](references/experts-eval.md).
- `vibe-coding` → follow [`references/vibe-coding.md`](references/vibe-coding.md). (Autonomous — no plan-approval gate; see that playbook.)

## Human plan-approval gate (every tier except `vibe-coding`)

The gate uses Claude Code's **native plan mode**. Draft and vet the plan first (the playbook's reviewers / `plan-review.js` run here), then — **before editing any files** — present it for approval: call **`EnterPlanMode`**, then **`ExitPlanMode`** with the plan. Build only after the user approves; if they request changes, revise and `ExitPlanMode` again. The gate does no tool work itself (reviewers already ran), so it's unaffected by any plan-mode tool restrictions. This is the **human** gate — distinct from the bar-raiser's automated *quality* gate.

- **Trivial changes never reach this gate** — they short-circuit the whole workflow (see *Trivial change first* in Step 1).
- **`vibe-coding` never gates** — it runs autonomously (never enters plan mode); its only human touchpoint is at the very end if a *major* concern is unresolved.

## Posture (applies at every tier)

- A tier is a **ceiling, not a quota — and not a floor**: scale the process to the change, and skip it entirely for trivial edits (Step 1).
- Stay **grounded**: read the real files and `CLAUDE.md`/conventions before changing anything; cite `file:line` when you reason about code.
- **Be terse — never re-print code.** The diff/edits already show the code; do **not** paste it again in any wrap-up or summary — not the full file, not the changed function, not a snippet. Summarize in words (what changed; the findings that *matter*), citing `file:line` if needed. Skip step-by-step narration. Concise by default; the user can ask for more.
- **Escalate, don't silently inflate**: if the task turns out much larger or riskier than the tier assumes, say so and suggest dialing the tier up — don't quietly do more process than was asked.
