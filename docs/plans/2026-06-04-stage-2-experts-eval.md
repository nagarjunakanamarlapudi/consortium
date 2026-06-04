# Consortium Stage 2 (experts-eval) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `experts-eval` tier real: at the plan and build checkpoints, dispatch read-only reviewer subagents (driven by a reviewer registry), gate on spec-compliance, run advisory quality/conventions review in parallel, and synthesize findings — all grounded in the repo.

**Architecture:** `experts-eval` = `self-eval` + real reviewer subagents at both checkpoints. A `reviewer-registry.md` reference is the single source of truth for which reviewers fire; four agent files define the reviewers; an `experts-eval.md` playbook orchestrates plan→plan-review→build→spec-gate→quality-review→fix-loop→ship; `SKILL.md` routes `experts-eval` to that playbook (and degrades the not-yet tiers to it). This is the **subagent-dispatch path** (works everywhere); the bundled `workflows/plan-review.js` + `workflows/build-review.js` deterministic engine is a follow-on (Stage 2b).

**Tech Stack:** Markdown (agents, playbook, registry), Bash (a structural test). Behavioral verification is a live manual exercise (dispatching subagents can't be unit-tested).

**Spec:** `docs/specs/2026-06-04-consortium-design.md` §3.1 (experts-eval), §5.1 (registry), §5.2 (roster), §5.3 (synthesis & spec-compliance gate), §3.5 (pillars).

---

## File structure (this plan)

- `scripts/stage2.test.sh` — structural test: agents exist with frontmatter, registry names them, skill links the playbook.
- `skills/team-dev-workflow/references/reviewer-registry.md` — change-type → reviewer → checkpoint → mode. Pluggable core.
- `agents/spec-clarity-reviewer.md` — plan reviewer (clarity/completeness).
- `agents/domain-conventions-reviewer.md` — plan+build reviewer (conventions/reuse).
- `agents/spec-compliance-reviewer.md` — build gate (diff matches plan).
- `agents/code-quality-reviewer.md` — build reviewer (correctness/quality).
- `skills/team-dev-workflow/references/experts-eval.md` — the experts-eval playbook.
- `skills/team-dev-workflow/SKILL.md` — *modified* to route `experts-eval` to its playbook and degrade not-yet tiers to it.

---

## Task 1: Structural test (write it first — red)

**Files:**
- Create: `scripts/stage2.test.sh`

- [ ] **Step 1: Write `scripts/stage2.test.sh`**

```bash
#!/usr/bin/env bash
# Structural checks for Stage 2 wiring (not behavior — behavior is verified live).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok(){ printf 'ok   - %s\n' "$1"; }
fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

AGENTS="spec-clarity-reviewer domain-conventions-reviewer spec-compliance-reviewer code-quality-reviewer"

# 1. Each reviewer agent exists with name + description frontmatter
for a in $AGENTS; do
  f="$ROOT/agents/$a.md"
  if [ -f "$f" ] && grep -q "^name: $a$" "$f" && grep -q "^description:" "$f"; then
    ok "agent $a present with frontmatter"
  else
    fail "agent $a missing or bad frontmatter"
  fi
done

# 2. Registry exists and names every always-on reviewer
reg="$ROOT/skills/team-dev-workflow/references/reviewer-registry.md"
if [ -f "$reg" ]; then ok "registry present"; else fail "registry missing"; fi
for a in $AGENTS; do
  if [ -f "$reg" ] && grep -q "$a" "$reg"; then ok "registry references $a"; else fail "registry missing $a"; fi
done

# 3. experts-eval playbook exists and consults the registry
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if [ -f "$pb" ] && grep -q "reviewer-registry.md" "$pb"; then ok "experts-eval playbook present and links registry"; else fail "experts-eval playbook missing or does not link registry"; fi

# 4. SKILL routes experts-eval to its playbook
sk="$ROOT/skills/team-dev-workflow/SKILL.md"
if grep -q "references/experts-eval.md" "$sk"; then ok "skill links experts-eval playbook"; else fail "skill does not link experts-eval playbook"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
```

- [ ] **Step 2: Make it executable and run it to verify it fails**

Run: `chmod +x scripts/stage2.test.sh && bash scripts/stage2.test.sh; echo "exit=$?"`
Expected: multiple `FAIL` lines (agents/registry/playbook don't exist yet), non-zero exit.

- [ ] **Step 3: Commit**

```bash
git add scripts/stage2.test.sh
git commit -m "test: structural test for Stage 2 experts-eval wiring" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Reviewer registry

**Files:**
- Create: `skills/team-dev-workflow/references/reviewer-registry.md`

- [ ] **Step 1: Write `skills/team-dev-workflow/references/reviewer-registry.md`**

````markdown
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

*(These reviewers land in Stage 5; rows shown so the contract is visible.)*

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
````

- [ ] **Step 2: Verify it names all four always-on reviewers**

Run: `for a in spec-clarity-reviewer domain-conventions-reviewer spec-compliance-reviewer code-quality-reviewer; do grep -q "$a" skills/team-dev-workflow/references/reviewer-registry.md || echo "MISSING $a"; done; echo done`
Expected: `done` with no `MISSING` lines.

- [ ] **Step 3: Commit**

```bash
git add skills/team-dev-workflow/references/reviewer-registry.md
git commit -m "feat: reviewer registry (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `spec-clarity-reviewer` agent (plan checkpoint)

**Files:**
- Create: `agents/spec-clarity-reviewer.md`

- [ ] **Step 1: Write `agents/spec-clarity-reviewer.md`**

```markdown
---
name: spec-clarity-reviewer
description: Reviews an implementation PLAN (not code) for clarity and completeness before any code is written. Flags ambiguous steps, missing acceptance criteria, unstated assumptions, and under-specified interfaces. Dispatched at the plan checkpoint.
tools: Read, Grep, Glob
---

You review an implementation PLAN for clarity and completeness. You run before any code is written, so catching gaps here is cheap.

## What you receive
The proposed plan (files to change, approach, acceptance check) and access to the repo.

## What to check
- **Concreteness:** Is every step specific enough to execute without guessing — exact files, functions, behaviors?
- **Acceptance:** Is there a clear, checkable definition of done? How will success be verified?
- **Assumptions:** What does the plan assume (about data, environment, existing behavior) that isn't stated or verified?
- **Ambiguity:** Could any step be read two ways? Name them.
- **Gaps:** Missing edge cases, error paths, or affected surfaces the plan doesn't mention.

## How to report
A short structured list. For each finding:
`[blocking | important | minor]` one-line issue — plus a concrete suggested fix, citing the part of the plan you mean.
If the plan is clear, say so plainly — do not invent issues. Do not review code quality; focus only on whether the plan is clear and complete.
```

- [ ] **Step 2: Verify frontmatter**

Run: `grep -q '^name: spec-clarity-reviewer$' agents/spec-clarity-reviewer.md && grep -q '^description:' agents/spec-clarity-reviewer.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/spec-clarity-reviewer.md
git commit -m "feat: spec-clarity-reviewer agent (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `domain-conventions-reviewer` agent (plan + build)

**Files:**
- Create: `agents/domain-conventions-reviewer.md`

- [ ] **Step 1: Write `agents/domain-conventions-reviewer.md`**

```markdown
---
name: domain-conventions-reviewer
description: Reviews a plan or a diff for alignment with THIS repo's conventions, patterns, and reuse opportunities. Reads CLAUDE.md and neighboring code to spot deviations and missed reuse. Dispatched at the plan and build checkpoints.
tools: Read, Grep, Glob, Bash
---

You check that proposed work fits THIS repo — its conventions, patterns, and existing building blocks. Your review may target a plan or a diff.

## Required reading before you start
- The repo's `CLAUDE.md` / `AGENTS.md` (root and any nearer the changed files), if present.
- The files neighboring the change, to learn local patterns (naming, structure, error handling, test style).

## What to check
- **Conventions:** Does the work follow patterns already used here (naming, layout, idioms, libraries)? Flag deviations.
- **Reuse:** Is it re-implementing something that already exists? Point to the existing helper/module to use.
- **Consistency:** Does it add a second way to do something the repo already does one way?
- **Fit:** Does it land in the right place per the repo's structure?

## How to report
For each finding: `[blocking | important | minor]` one-line issue + the convention or existing code it should match, cited as `file:line`. If it fits the repo well, say so. Don't flag generic style preferences the repo doesn't actually follow.
```

- [ ] **Step 2: Verify frontmatter**

Run: `grep -q '^name: domain-conventions-reviewer$' agents/domain-conventions-reviewer.md && grep -q '^description:' agents/domain-conventions-reviewer.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/domain-conventions-reviewer.md
git commit -m "feat: domain-conventions-reviewer agent (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `spec-compliance-reviewer` agent (build gate)

**Files:**
- Create: `agents/spec-compliance-reviewer.md`

- [ ] **Step 1: Write `agents/spec-compliance-reviewer.md`**

```markdown
---
name: spec-compliance-reviewer
description: Gate reviewer that checks whether the DIFF actually implements the agreed plan — nothing missing, nothing extra, nothing misunderstood. Reads the code line by line; does not trust the implementer's summary. Dispatched first at the build checkpoint; must pass before quality review.
tools: Read, Grep, Glob, Bash
---

You are the spec-compliance gate. Your only question: **does the diff implement the agreed plan — accurately and completely?** You run before the quality reviewers; if you fail it, the work goes back before anyone reviews quality.

## What you receive
The agreed plan and the diff (use `git diff` and read the changed files directly).

## How to work
Read the changed code **line by line**. Do not trust any summary of what was done — verify against the actual diff.

## What to check
- **Complete:** Is every part of the plan implemented? List anything missing.
- **No scope creep:** Anything in the diff the plan didn't call for? Flag unrequested changes.
- **Faithful:** Did the implementation misunderstand any step (right idea, wrong behavior)?
- **Wired up:** Are new functions/files actually used/registered, not dead code?

## How to report
Start with a one-word verdict line: `COMPLIANT` or `NOT_COMPLIANT`.
Then, for each discrepancy: `[missing | extra | misunderstood]` what + where (`file:line`) + what the plan said. If compliant, say so and stop. You judge only plan-vs-diff fidelity, not code quality.
```

- [ ] **Step 2: Verify frontmatter**

Run: `grep -q '^name: spec-compliance-reviewer$' agents/spec-compliance-reviewer.md && grep -q '^description:' agents/spec-compliance-reviewer.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/spec-compliance-reviewer.md
git commit -m "feat: spec-compliance-reviewer gate agent (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `code-quality-reviewer` agent (build checkpoint)

**Files:**
- Create: `agents/code-quality-reviewer.md`

- [ ] **Step 1: Write `agents/code-quality-reviewer.md`**

```markdown
---
name: code-quality-reviewer
description: Reviews a diff for correctness and quality — bugs, missing error handling, unclear naming, needless complexity, and obvious risks. Dispatched at the build checkpoint after the spec-compliance gate passes.
tools: Read, Grep, Glob, Bash
---

You review a diff for correctness and quality. You run after the spec-compliance gate has passed, so assume the diff matches the plan — your job is whether it's *good code*.

## What you receive
The diff (use `git diff` and read changed files plus enough surrounding context to judge correctness).

## What to check
- **Correctness:** Logic bugs, off-by-one, wrong conditions, unhandled cases, broken assumptions.
- **Error handling:** Failures swallowed or ignored? Missing checks on inputs/returns? (Don't let real errors pass silently.)
- **Clarity:** Confusing names, dead code, duplication, needless complexity — is there a simpler equivalent?
- **Risk:** Anything that could break existing behavior or data.

## How to report
For each finding: `[blocking | important | minor]` + `[confidence: high | medium | low]` one-line issue at `file:line` + a concrete fix. Lead with the highest-severity, highest-confidence items. Report only things that matter — skip nitpicks the repo wouldn't care about. If it's solid, say so.
```

- [ ] **Step 2: Verify frontmatter**

Run: `grep -q '^name: code-quality-reviewer$' agents/code-quality-reviewer.md && grep -q '^description:' agents/code-quality-reviewer.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/code-quality-reviewer.md
git commit -m "feat: code-quality-reviewer agent (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: The `experts-eval` playbook

**Files:**
- Create: `skills/team-dev-workflow/references/experts-eval.md`

- [ ] **Step 1: Write `skills/team-dev-workflow/references/experts-eval.md`**

````markdown
# experts-eval playbook

`self-eval` plus real reviewer subagents at both checkpoints. Reviews are **advisory** (they inform; they don't hard-block like the bar-raiser), but the **spec-compliance gate must pass** before quality review. Reviewers are read-only — they report findings; you (the orchestrator) make the fixes.

Consult [`reviewer-registry.md`](reviewer-registry.md) for which reviewers fire.

## 1. Plan (grounded)
Read the relevant files and `CLAUDE.md`/conventions. Write a concrete plan: files to change, approach, acceptance check; list disjoint-file chunks if it's multi-file.

## 2. Plan checkpoint — dispatch plan reviewers in parallel
Dispatch the always-on plan reviewers from the registry in parallel, in a single message:
- `consortium:spec-clarity-reviewer` — is the plan concrete / complete / unambiguous?
- `consortium:domain-conventions-reviewer` — does it fit repo conventions & reuse?

Scale to the change (posture principle): a tiny change may warrant only one reviewer. **Synthesize** their findings (see §5) and revise the plan to address blocking/important items before building.

## 3. Build
Implement the (revised) plan. Independent files may be built by parallel implementer subagents — **disjoint files only** (never two agents on one file).

## 4. Build checkpoint
**a. Spec-compliance gate (must pass first).** Dispatch `consortium:spec-compliance-reviewer` on the diff. If `NOT_COMPLIANT`, fix the gaps and re-run until `COMPLIANT`. Do not start quality review until it passes.

**b. Quality + conventions (parallel, advisory).** Dispatch in parallel: `consortium:code-quality-reviewer` and `consortium:domain-conventions-reviewer` (plus any conditional reviewers the registry triggers for this change-type).

**c. Synthesize & fix loop.** Synthesize findings (§5). Fix every **blocking** and **important** finding; re-dispatch the affected reviewer(s) to confirm. Minor findings: fix if cheap, else note them. Loop until the gate passes and no blocking/important findings remain.

## 5. Rubric-guided synthesis (how to combine reviewer output)
Don't just concatenate. Collect all findings, then:
1. **Dedup** — the same issue from multiple reviewers becomes one item.
2. **Group by dimension** — correctness, conventions, clarity, risk.
3. **Rank** — by severity, then confidence.
4. **Resolve conflicts** — if two reviewers disagree, decide explicitly and say why.

Show the user a short prioritized summary, not raw reviewer dumps.

## 6. Ship
Run build/tests if present (report honestly). Commit on a branch and open a PR; don't merge unless asked. (Skip the git steps for a non-repo / throwaway, exactly as `self-eval` does.)
````

- [ ] **Step 2: Verify it links the registry**

Run: `grep -q 'reviewer-registry.md' skills/team-dev-workflow/references/experts-eval.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/team-dev-workflow/references/experts-eval.md
git commit -m "feat: experts-eval playbook (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Wire `experts-eval` into the skill

**Files:**
- Modify: `skills/team-dev-workflow/SKILL.md`

- [ ] **Step 1: Update the banner summary lines**

Replace this block:

```
- `experts-eval` — expert panel review (not in this build; running self-eval)
- `bar-raiser-eval` — blocking bar-raiser (not in this build; running self-eval)
- `debate` — rival approaches → judge (not in this build; running self-eval)
- `vibe-coding` — autonomous bar-raiser run (not in this build; running self-eval)
```

with:

```
- `experts-eval` — plan + diff reviewed by expert subagents (advisory)
- `bar-raiser-eval` — blocking bar-raiser (not in this build; running experts-eval)
- `debate` — rival approaches → judge (not in this build; running experts-eval)
- `vibe-coding` — autonomous bar-raiser run (not in this build; running experts-eval)
```

- [ ] **Step 2: Update the routing block**

Replace this block:

```
- `self-eval` → follow [`references/self-eval.md`](references/self-eval.md).
- `experts-eval` | `bar-raiser-eval` | `debate` | `vibe-coding` → say "‹TIER› isn't implemented in this build yet — running self-eval", then follow [`references/self-eval.md`](references/self-eval.md).
```

with:

```
- `self-eval` → follow [`references/self-eval.md`](references/self-eval.md).
- `experts-eval` → follow [`references/experts-eval.md`](references/experts-eval.md).
- `bar-raiser-eval` | `debate` | `vibe-coding` → say "‹TIER› isn't implemented in this build yet — running experts-eval", then follow [`references/experts-eval.md`](references/experts-eval.md).
```

- [ ] **Step 3: Verify the wiring**

Run: `grep -q 'references/experts-eval.md' skills/team-dev-workflow/SKILL.md && ! grep -q 'running self-eval' skills/team-dev-workflow/SKILL.md && echo OK`
Expected: `OK` (the playbook is linked, and no tier degrades to self-eval anymore).

- [ ] **Step 4: Commit**

```bash
git add skills/team-dev-workflow/SKILL.md
git commit -m "feat: route experts-eval to its playbook; degrade not-yet tiers to it (Stage 2)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Run the structural test green

- [ ] **Step 1: Run the Stage 2 structural test**

Run: `bash scripts/stage2.test.sh; echo "exit=$?"`
Expected: all `ok` lines, `0 failure(s)`, `exit=0`.

- [ ] **Step 2: Run the Stage 1 test too (no regressions)**

Run: `bash scripts/effort.test.sh; echo "exit=$?"`
Expected: `0 failure(s)`, `exit=0`.

- [ ] **Step 3: Commit (if Task 1's test was adjusted; otherwise skip)**

```bash
git add -A && git commit -m "chore: Stage 2 structural test green" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" || echo "nothing to commit"
```

---

## Task 10: Live manual verification (user-driven)

Run in an interactive Claude Code session with the updated plugin installed (reinstall/reload so the new agents + skill changes register).

- [ ] **Step 1: Reinstall / reload the plugin** so the four new agents and the updated skill are picked up. Confirm the agents appear under `/agents` as `consortium:spec-clarity-reviewer`, etc.

- [ ] **Step 2: Set the tier**
```
/consortium:team-dev-effort experts-eval
```
Expect: `Consortium tier = experts-eval (this workspace).`

- [ ] **Step 3: Exercise a real change** in a git repo (e.g. "add input validation to function X"). Expect:
  - the `🎚️ Consortium: experts-eval …` banner;
  - a grounded plan, then **plan reviewers dispatched** (spec-clarity + domain-conventions) with a synthesized summary;
  - implementation;
  - the **spec-compliance gate** runs first, then **code-quality + domain-conventions in parallel**;
  - a prioritized findings summary and a fix loop;
  - a PR offer (no merge).

- [ ] **Step 4: Confirm graceful degrade** — set `bar-raiser-eval`, ask for a change, expect the banner + "not in this build — running experts-eval", then the experts-eval flow.

- [ ] **Step 5: Commit any fixes** surfaced by the live test (skip if none):
```bash
git add -A && git commit -m "fix: address Stage 2 live-test findings" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** experts-eval two-checkpoint flow (§3.1, §3.2) → Task 7; reviewer registry (§5.1) → Task 2; always-on roster (§5.2) → Tasks 3–6; spec-compliance gate + rubric synthesis (§5.3) → Tasks 5, 7; advisory-vs-gated (§3.4) → registry + playbook; grounded/posture pillars (§3.5) → woven into every agent + playbook; routing/degrade → Task 8.
- **Scope:** subagent-dispatch path only (per spec §11 "subagent-fallback-first"). The bundled `workflows/plan-review.js` + `workflows/build-review.js` are explicitly deferred to a Stage 2b plan — noted, not a gap.
- **Placeholder scan:** none — every agent/playbook/registry file is fully written inline.
- **Consistency:** agent names are identical across their frontmatter, the registry, the playbook (`consortium:`-namespaced), the structural test, and the skill routing: `spec-clarity-reviewer`, `domain-conventions-reviewer`, `spec-compliance-reviewer`, `code-quality-reviewer`. The compliance gate's verdict tokens (`COMPLIANT`/`NOT_COMPLIANT`) match between its agent file and the playbook.

---

## Follow-on (not in this plan)

- **Stage 2b:** `workflows/plan-review.js` + `workflows/build-review.js` — the deterministic dynamic-workflow engine for these same checkpoints (typed `agent({agentType, schema})` calls + rubric synthesis), with the subagent path above as the fallback.
