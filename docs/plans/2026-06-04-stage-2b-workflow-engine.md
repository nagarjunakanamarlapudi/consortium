# Consortium Stage 2b (workflow engine — proof-of-pattern) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the dynamic-workflow engine with **one proven script** — `workflows/plan-review.js` (the experts-eval plan-checkpoint fan-out) — invoked **workflow-preferred with a subagent fallback**, so we validate the bundled-`scriptPath` + `agentType` integration end-to-end before replicating to the other checkpoints.

**Architecture:** Bundled `.js` scripts under `workflows/`. The skill/playbook invokes one via `Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/<name>.js", args })`. Scripts orchestrate only (agents do I/O); agents are called by namespaced `agentType` (`consortium:*`) with a `schema` for structured findings. The per-tier playbook steps remain the fallback when Workflow is unavailable (CC < v2.1.154 or disabled).

**Tech Stack:** JavaScript (workflow scripts), Markdown (README + playbook wiring), Bash (`node --check` + grep structural test).

**Spec:** `docs/specs/2026-06-04-consortium-design.md` §5.0 (execution model + script constraints), §5.1–5.3, §10 (open questions #4/#5 this validates).

**Prerequisite:** the runtime smoke test (`consortium-smoke`) passed — `agent()` + `schema` + return work here. If it didn't, stop and reassess before building.

---

## File structure (this plan)

- `workflows/plan-review.js` — fan out the plan reviewers → structured findings.
- `workflows/README.md` — how the skill invokes bundled workflows + constraints + fallback.
- `skills/team-dev-workflow/references/experts-eval.md` — *modified* §2 to prefer the workflow, fall back to direct dispatch.
- `scripts/stage2b.test.sh` — structural + `node --check` test.

---

## Task 1: Structural test (red first)

**Files:**
- Create: `scripts/stage2b.test.sh`

- [ ] **Step 1: Write `scripts/stage2b.test.sh`**

```bash
#!/usr/bin/env bash
# Structural + syntax checks for the workflow engine (Stage 2b). Behavior verified live (installed session).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0; ok(){ printf 'ok   - %s\n' "$1"; }; fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

js="$ROOT/workflows/plan-review.js"
# 1. script present with meta + reviewer agentTypes + schema + parallel
if [ -f "$js" ] && grep -q "export const meta" "$js" && grep -q "consortium:spec-clarity-reviewer" "$js" && grep -q "consortium:domain-conventions-reviewer" "$js" && grep -q "schema" "$js" && grep -q "parallel" "$js"; then ok "plan-review.js present (meta, reviewer agentTypes, schema, parallel)"; else fail "plan-review.js missing/incomplete"; fi

# 2. JS syntax valid (node --check does not run the script, so workflow globals are fine)
if command -v node >/dev/null 2>&1; then
  if node --check "$js" 2>/dev/null; then ok "plan-review.js passes node --check"; else fail "plan-review.js has a syntax error"; fi
else
  ok "node unavailable — syntax check skipped"
fi

# 3. README documents invocation (${CLAUDE_PLUGIN_ROOT}) + fallback
r="$ROOT/workflows/README.md"
if [ -f "$r" ] && grep -q "CLAUDE_PLUGIN_ROOT" "$r" && grep -qi "fallback" "$r"; then ok "workflows/README documents invocation + fallback"; else fail "workflows/README missing/incomplete"; fi

# 4. experts-eval playbook prefers the workflow with an explicit fallback
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if grep -q "plan-review.js" "$pb" && grep -qi "fallback" "$pb"; then ok "experts-eval prefers the workflow with fallback"; else fail "experts-eval not wired to the workflow"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
```

- [ ] **Step 2: Make executable and run (expect red)**

Run: `chmod +x scripts/stage2b.test.sh && bash scripts/stage2b.test.sh; echo "exit=$?"`
Expected: `FAIL` for the script/README/playbook (node check may pass-or-skip), non-zero exit.

- [ ] **Step 3: Commit**

```bash
git add scripts/stage2b.test.sh
git commit -m "test: structural test for the workflow engine (Stage 2b)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `workflows/plan-review.js`

**Files:**
- Create: `workflows/plan-review.js`

- [ ] **Step 1: Write `workflows/plan-review.js`**

```javascript
export const meta = {
  name: 'consortium-plan-review',
  description: 'Fan out the experts-eval plan reviewers and return their structured findings',
  phases: [{ title: 'Plan review' }],
}

// Each reviewer returns findings in this shape (schema-validated by the runtime).
const FINDINGS = {
  type: 'object',
  properties: {
    reviewer: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { enum: ['blocking', 'important', 'minor'] },
          issue: { type: 'string' },
          suggestion: { type: 'string' },
        },
        required: ['severity', 'issue'],
      },
    },
  },
  required: ['reviewer', 'findings'],
}

// The plan text is passed in by the skill; agents read the repo themselves for grounding.
const plan = (args && args.plan) || ''
if (!plan) log('No args.plan provided; reviewers will rely on repo context only.')

// Always-on plan reviewers (mirrors references/reviewer-registry.md).
const REVIEWERS = [
  { agentType: 'consortium:spec-clarity-reviewer', label: 'plan:spec-clarity' },
  { agentType: 'consortium:domain-conventions-reviewer', label: 'plan:domain-conventions' },
]

const reviews = await parallel(
  REVIEWERS.map((rv) => () =>
    agent(
      `You are reviewing an implementation PLAN for the current repo. Read the repo as needed for grounding.\n\nPLAN:\n${plan}\n\nReturn your findings.`,
      { agentType: rv.agentType, label: rv.label, phase: 'Plan review', schema: FINDINGS },
    ),
  ),
)

return { reviews: reviews.filter(Boolean) }
```

- [ ] **Step 2: Verify content + syntax**

Run: `grep -q 'consortium:spec-clarity-reviewer' workflows/plan-review.js && grep -q 'consortium:domain-conventions-reviewer' workflows/plan-review.js && (command -v node >/dev/null 2>&1 && node --check workflows/plan-review.js && echo "syntax OK" || echo "node skipped")`
Expected: `syntax OK` (or `node skipped`), no error.

- [ ] **Step 3: Commit**

```bash
git add workflows/plan-review.js
git commit -m "feat: plan-review.js workflow (experts-eval plan checkpoint) (Stage 2b)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `workflows/README.md`

**Files:**
- Create: `workflows/README.md`

- [ ] **Step 1: Write `workflows/README.md`**

````markdown
# Consortium workflows

Bundled dynamic-workflow scripts (the deterministic engine). They are **not** a first-class plugin component, so the `team-dev-workflow` skill invokes them explicitly via the Workflow tool:

```
Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/<name>.js", args: { ... } })
```

Each script is the **workflow-preferred** path for a checkpoint; the matching steps in the per-tier playbooks are the **subagent fallback** for when the Workflow feature (Claude Code v2.1.154+) is unavailable or disabled.

## Conventions
- Scripts **orchestrate only** — no filesystem/shell. The dispatched agents (`consortium:*`) do all reading/writing.
- Agents are called by **namespaced type**: `agent(prompt, { agentType: 'consortium:<agent>', schema })`.
- Avoid `Date.now()` / `Math.random()` (they throw in the workflow runtime); pass anything time-varying via `args`.
- Respect the runtime caps (≤16 concurrent, 1000 agents/run). Reference bundled files only via `${CLAUDE_PLUGIN_ROOT}` (no `../`).

## Scripts
- `plan-review.js` — fan out the plan reviewers (spec-clarity, domain-conventions) → structured findings. Backs the experts-eval / bar-raiser-eval **plan checkpoint**.
- *(coming next: `build-review.js`, `bar-raiser-gate.js`, `vibe.js`)*
````

- [ ] **Step 2: Verify**

Run: `grep -q CLAUDE_PLUGIN_ROOT workflows/README.md && grep -qi fallback workflows/README.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add workflows/README.md
git commit -m "docs: workflows/README — invocation, constraints, fallback (Stage 2b)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Wire experts-eval to prefer the workflow (with fallback)

**Files:**
- Modify: `skills/team-dev-workflow/references/experts-eval.md`

- [ ] **Step 1: Replace the §2 heading + intro**

Replace:
```
## 2. Plan checkpoint — dispatch plan reviewers in parallel
Dispatch the always-on plan reviewers from the registry in parallel, in a single message:
- `consortium:spec-clarity-reviewer` — is the plan concrete / complete / unambiguous?
- `consortium:domain-conventions-reviewer` — does it fit repo conventions & reuse?
```
with:
```
## 2. Plan checkpoint — review the plan
**Workflow-preferred:** if the Workflow tool is available, run the bundled script —
`Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/plan-review.js", args: { plan } })` —
which fans out the plan reviewers and returns structured findings.

**Fallback (no Workflow tool):** dispatch the always-on plan reviewers yourself, in parallel, in a single message:
- `consortium:spec-clarity-reviewer` — is the plan concrete / complete / unambiguous?
- `consortium:domain-conventions-reviewer` — does it fit repo conventions & reuse?
```

- [ ] **Step 2: Verify**

Run: `grep -q 'plan-review.js' skills/team-dev-workflow/references/experts-eval.md && grep -qi 'fallback' skills/team-dev-workflow/references/experts-eval.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/team-dev-workflow/references/experts-eval.md
git commit -m "feat: experts-eval plan checkpoint prefers plan-review.js workflow (Stage 2b)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Tests green

- [ ] **Step 1: Stage 2b test**

Run: `bash scripts/stage2b.test.sh; echo "exit=$?"`
Expected: all `ok`, `0 failure(s)`, `exit=0`.

- [ ] **Step 2: Regression**

Run: `for t in effort stage2 stage3 stage4; do bash scripts/$t.test.sh >/dev/null 2>&1 && echo "$t ok" || echo "$t FAIL"; done`
Expected: all `ok`.

---

## Task 6: Live validation (user-driven — the real test of §10)

In the **installed** session (reinstall first):

- [ ] **Step 1:** `/consortium:team-dev-effort experts-eval`, then ask for a non-trivial change in a git repo.
- [ ] **Step 2:** When it reaches the plan checkpoint, confirm it **invokes the `plan-review.js` workflow** (visible in `/workflows`) rather than dispatching the reviewers inline — and that the workflow's `agent({agentType:'consortium:spec-clarity-reviewer', …})` calls **resolve and return findings**.
- [ ] **Step 3:** If the bundled `scriptPath` or `agentType` doesn't resolve, confirm the skill **falls back** to direct subagent dispatch (no breakage). Report what happened so we adjust the invocation (e.g. bare vs namespaced agentType) before replicating.

---

## Self-Review (completed during planning)

- **Spec coverage:** execution model + constraints (§5.0) → README + script; structured findings (§5.3) → schema in plan-review.js; workflow-preferred-with-fallback (§5.0, §11) → Task 4; validates open questions §10 #4/#5 → Task 6.
- **Scope:** ONE script (plan checkpoint) as the proof-of-pattern; `build-review.js`, `bar-raiser-gate.js`, `vibe.js` are the follow-on once the integration is confirmed live. Deliberate — avoids writing four scripts against unvalidated `scriptPath`/`agentType` assumptions.
- **Placeholder scan:** none — script + README + wiring written in full.
- **Consistency:** agent types `consortium:spec-clarity-reviewer` / `consortium:domain-conventions-reviewer` match the agents + registry; the findings schema mirrors the reviewers' `[severity] issue + suggestion` report format.

---

## Follow-on (after live validation)
- `build-review.js` (spec-gate → experts → fix-loop), `bar-raiser-gate.js` (verdict loop ≤N), `vibe.js` (autonomous end-to-end → `{outcome, pr?, concerns[], report}`), each wired workflow-preferred with the existing playbook step as fallback.
