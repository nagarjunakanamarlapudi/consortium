# Consortium Stage 3 (bar-raiser-eval) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `bar-raiser-eval` real: everything `experts-eval` does, plus a single authoritative **bar-raiser** that reviews the plan and the diff against a high bar, issues **rewrite mandates** (not patches) with a structured verdict, and **gates** — work doesn't ship until it accepts or the user overrides.

**Architecture:** A `bar-raiser` agent (adversarial gatekeeper, verdict = `accept|reject` + `rigor_score` + `rewrite_mandates[]` each tagged `severity`). A `bar-raiser-eval.md` playbook that builds on `experts-eval.md` and adds the bar-raiser at both checkpoints plus the verdict loop (≤ N rounds). `SKILL.md` routes `bar-raiser-eval` to it. The human plan-approval gate and trivial short-circuit (Stage 2) apply unchanged. Subagent-dispatch path; the `bar-raiser-gate.js` workflow is a later follow-on.

**Tech Stack:** Markdown (agent + playbook), Bash (structural test). Behavior verified live.

**Spec:** `docs/specs/2026-06-04-consortium-design.md` §3.3 (bar-raiser), §3.4 (advisory vs gated), §5.3 (verdict gate + severity), §3.7 (human gate).

---

## File structure (this plan)

- `scripts/stage3.test.sh` — structural test: bar-raiser agent exists, playbook exists + builds on experts-eval, skill routes it.
- `agents/bar-raiser.md` — the bar-raiser gatekeeper agent.
- `skills/team-dev-workflow/references/bar-raiser-eval.md` — the playbook.
- `skills/team-dev-workflow/references/reviewer-registry.md` — *modified* to list the bar-raiser as the tier's gate.
- `skills/team-dev-workflow/SKILL.md` — *modified* to route `bar-raiser-eval` (and re-point the remaining not-yet tiers).

---

## Task 1: Structural test (red first)

**Files:**
- Create: `scripts/stage3.test.sh`

- [ ] **Step 1: Write `scripts/stage3.test.sh`**

```bash
#!/usr/bin/env bash
# Structural checks for Stage 3 (bar-raiser-eval). Behavior is verified live.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok(){ printf 'ok   - %s\n' "$1"; }
fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

# 1. bar-raiser agent exists with name + description frontmatter
f="$ROOT/agents/bar-raiser.md"
if [ -f "$f" ] && grep -q "^name: bar-raiser$" "$f" && grep -q "^description:" "$f"; then ok "bar-raiser agent present with frontmatter"; else fail "bar-raiser agent missing or bad frontmatter"; fi

# 2. bar-raiser agent defines the structured verdict (accept/reject + mandates + severity)
if [ -f "$f" ] && grep -q "verdict" "$f" && grep -q "rewrite_mandates" "$f" && grep -q "severity" "$f"; then ok "bar-raiser verdict schema documented"; else fail "bar-raiser verdict schema incomplete"; fi

# 3. playbook exists, builds on experts-eval, and loops on the verdict
pb="$ROOT/skills/team-dev-workflow/references/bar-raiser-eval.md"
if [ -f "$pb" ] && grep -q "experts-eval.md" "$pb" && grep -qi "rounds" "$pb"; then ok "bar-raiser-eval playbook present (builds on experts-eval, loops)"; else fail "bar-raiser-eval playbook missing/incomplete"; fi

# 4. SKILL routes bar-raiser-eval to its playbook
sk="$ROOT/skills/team-dev-workflow/SKILL.md"
if grep -q "references/bar-raiser-eval.md" "$sk"; then ok "skill links bar-raiser-eval playbook"; else fail "skill does not link bar-raiser-eval playbook"; fi

# 5. registry lists the bar-raiser as the gate
reg="$ROOT/skills/team-dev-workflow/references/reviewer-registry.md"
if [ -f "$reg" ] && grep -q "bar-raiser" "$reg"; then ok "registry lists the bar-raiser"; else fail "registry missing the bar-raiser"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
```

- [ ] **Step 2: Make executable and run (expect red)**

Run: `chmod +x scripts/stage3.test.sh && bash scripts/stage3.test.sh; echo "exit=$?"`
Expected: `FAIL` lines (agent/playbook absent), non-zero exit.

- [ ] **Step 3: Commit**

```bash
git add scripts/stage3.test.sh
git commit -m "test: structural test for Stage 3 bar-raiser-eval" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: The `bar-raiser` agent

**Files:**
- Create: `agents/bar-raiser.md`

- [ ] **Step 1: Write `agents/bar-raiser.md`**

```markdown
---
name: bar-raiser
description: The bar-raiser — a single authoritative gatekeeper (distinct from the author and the advisory experts) that reviews a plan or a diff against a high bar and returns a structured verdict. Demands rewrite mandates (redesign weak sections), not patches. Dispatched at bar-raiser-eval; its verdict gates the work.
tools: Read, Grep, Glob, Bash
---

You are the **bar-raiser**: a demanding senior reviewer with authority to block. You are not the author and not one of the advisory experts — you are the final bar. The question is not "is this good enough?" but "does this reflect real, context-specific thinking, and does it hold up?"

## What you receive
A plan or a diff (use `git diff` / read files). For a diff, the spec-compliance gate has already passed and the advisory experts have already run — assume the basics are covered; you set the higher bar.

## What makes you REJECT
- **Textbook / generic** — reads like a default answer, not reasoned for *this* problem; choices unjustified for the actual constraints.
- **Missing "why not"** — a major decision isn't defended against a concrete alternative.
- **Failure-mode blindness** — the top realistic failure modes aren't handled or acknowledged.
- **Hidden risk** — a correctness / security / data-loss / performance issue the advisory pass didn't escalate.
- **Incoherence** — parts contradict each other or the repo's direction.

## How to report (structured)
1. **rigor_score**: 1–5 (5 = exceptional). The bar to ACCEPT is **≥ 4**.
2. **verdict**: `accept` or `reject`.
3. **rewrite_mandates**: for anything below the bar, a directive to *redesign* that piece (not a patch) — each tagged **severity: minor | major**, citing `file:line` or the plan section.

Be specific and demanding, but fair: if it genuinely clears the bar, ACCEPT and say why in one line. Don't manufacture rejections to look thorough.
```

- [ ] **Step 2: Verify frontmatter + verdict vocabulary**

Run: `grep -q '^name: bar-raiser$' agents/bar-raiser.md && grep -q 'rewrite_mandates' agents/bar-raiser.md && grep -q 'severity' agents/bar-raiser.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/bar-raiser.md
git commit -m "feat: bar-raiser gatekeeper agent (Stage 3)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: The `bar-raiser-eval` playbook

**Files:**
- Create: `skills/team-dev-workflow/references/bar-raiser-eval.md`

- [ ] **Step 1: Write `skills/team-dev-workflow/references/bar-raiser-eval.md`**

````markdown
# bar-raiser-eval playbook

Everything [`experts-eval.md`](experts-eval.md) does, **plus a blocking bar-raiser** at both checkpoints. The bar-raiser (`consortium:bar-raiser`) is a single authoritative gatekeeper — distinct from the author and the advisory experts. Its **verdict gates**: work doesn't advance until it accepts (or the user overrides).

## Plan checkpoint
Run the experts-eval plan reviewers (advisory) and revise the plan. **Then dispatch `consortium:bar-raiser` on the plan.** If it rejects (rigor < 4), apply its rewrite mandates and re-dispatch — up to **N rounds (default 3)**. Once it accepts, **present the bar-raised plan to the user for approval** (the human gate, see SKILL.md) before any code is written.

## Build checkpoint
1. **Spec-compliance gate** — `consortium:spec-compliance-reviewer` must be `COMPLIANT` first.
2. **Advisory experts** in parallel — `consortium:code-quality-reviewer`, `consortium:domain-conventions-reviewer`, plus any installed conditional reviewers the registry triggers.
3. **Bar-raiser verdict** — dispatch `consortium:bar-raiser` on the diff.
4. **Synthesize** all findings (experts + bar-raiser) per experts-eval §5.
5. **Verdict loop:** if `reject`, dispatch fix-implementers with the **rewrite mandates** (redesign, not patch), then re-run from step 1. Loop until `accept` or **N rounds (default 3)**.
6. If still `reject` after N rounds, **stop and surface to the user** with the remaining mandates — do not ship under the bar.

## Severity
The bar-raiser tags each mandate `minor | major`. (These severities also drive `vibe-coding`'s autonomous finish — spec §3.6.)

## Everything else
Synthesis, grounding, the posture principle, the human plan-approval gate, the trivial short-circuit, terse output, and ship-as-PR all apply exactly as in `experts-eval` / the skill — this playbook only adds the bar-raiser and its loop.
````

- [ ] **Step 2: Verify it builds on experts-eval and loops**

Run: `grep -q 'experts-eval.md' skills/team-dev-workflow/references/bar-raiser-eval.md && grep -qi 'rounds' skills/team-dev-workflow/references/bar-raiser-eval.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/team-dev-workflow/references/bar-raiser-eval.md
git commit -m "feat: bar-raiser-eval playbook (Stage 3)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: List the bar-raiser in the registry

**Files:**
- Modify: `skills/team-dev-workflow/references/reviewer-registry.md`

- [ ] **Step 1: Add a gate section after the "Always-on" table**

Insert this block immediately before the `## Conditional (by change-type)` heading:

```markdown
## Gate (`bar-raiser-eval` only)

| reviewer | checkpoint | mode | focus |
|---|---|---|---|
| `consortium:bar-raiser` | plan + build | **gate (verdict, ≤N rounds)** | high-bar adversarial review; rewrite mandates |

```

- [ ] **Step 2: Verify**

Run: `grep -q 'consortium:bar-raiser' skills/team-dev-workflow/references/reviewer-registry.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/team-dev-workflow/references/reviewer-registry.md
git commit -m "feat: list bar-raiser as the bar-raiser-eval gate in the registry (Stage 3)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Wire `bar-raiser-eval` into the skill

**Files:**
- Modify: `skills/team-dev-workflow/SKILL.md`

- [ ] **Step 1: Update the banner summary line**

Replace:
```
- `bar-raiser-eval` — blocking bar-raiser (not in this build; running experts-eval)
```
with:
```
- `bar-raiser-eval` — experts + a blocking bar-raiser (verdict-gated, ≤N rounds)
```

- [ ] **Step 2: Update the routing block**

Replace:
```
- `bar-raiser-eval` | `debate` | `vibe-coding` → say "‹TIER› isn't implemented in this build yet — running experts-eval", then follow [`references/experts-eval.md`](references/experts-eval.md).
```
with:
```
- `bar-raiser-eval` → follow [`references/bar-raiser-eval.md`](references/bar-raiser-eval.md).
- `debate` → say "debate isn't implemented in this build yet — running experts-eval", then follow [`references/experts-eval.md`](references/experts-eval.md).
- `vibe-coding` → say "vibe-coding isn't implemented in this build yet — running bar-raiser-eval (but I'll still ask before building)", then follow [`references/bar-raiser-eval.md`](references/bar-raiser-eval.md).
```

- [ ] **Step 3: Verify**

Run: `grep -q 'references/bar-raiser-eval.md' skills/team-dev-workflow/SKILL.md && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/team-dev-workflow/SKILL.md
git commit -m "feat: route bar-raiser-eval to its playbook; re-point debate/vibe degrade (Stage 3)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Run tests green

- [ ] **Step 1: Stage 3 structural test**

Run: `bash scripts/stage3.test.sh; echo "exit=$?"`
Expected: all `ok`, `0 failure(s)`, `exit=0`.

- [ ] **Step 2: Regression — Stages 1 & 2**

Run: `bash scripts/effort.test.sh >/dev/null && echo s1ok; bash scripts/stage2.test.sh >/dev/null && echo s2ok`
Expected: `s1ok` and `s2ok`.

---

## Task 7: Live manual verification (user-driven)

Reinstall/reload the plugin first (so `consortium:bar-raiser` and the routing change register).

- [ ] **Step 1:** `/consortium:team-dev-effort bar-raiser-eval`
- [ ] **Step 2:** Ask for a non-trivial change in a git repo. Expect: banner → plan reviewers → **bar-raiser reviews the plan** → (rewrites if rigor < 4) → **plan presented for your approval** → build → spec-compliance gate → advisory experts → **bar-raiser verdict** → verdict loop if needed → PR offer.
- [ ] **Step 3:** Confirm a **trivial** edit (rename) still short-circuits (no bar-raiser, no gate).
- [ ] **Step 4:** Commit any fixes from the live test (skip if none).

---

## Self-Review (completed during planning)

- **Spec coverage:** bar-raiser role/verdict (§3.3) → Task 2; gate at plan+build + verdict loop (§5.3) → Task 3; advisory-vs-gated line (§3.4) → playbook builds on experts-eval; severity for vibe-coding (§3.6) → agent + playbook; human gate (§3.7) preserved → playbook references it.
- **Scope:** subagent path only; `workflows/bar-raiser-gate.js` deferred (Stage 3b), consistent with spec §11 fallback-first.
- **Placeholder scan:** none — agent + playbook written in full.
- **Consistency:** agent name `bar-raiser` and verdict tokens (`accept`/`reject`, `rewrite_mandates`, `severity`, rigor ≥ 4) match across the agent, the playbook, the registry row, and the structural test. Routing degrades `debate`→experts-eval and `vibe-coding`→bar-raiser-eval (closest available), each with a one-line note.

---

## Follow-on (not in this plan)
- **Stage 3b:** `workflows/bar-raiser-gate.js` — the deterministic verdict loop as a dynamic workflow (typed `agent({agentType:'consortium:bar-raiser', schema})`), with this subagent path as the fallback.
