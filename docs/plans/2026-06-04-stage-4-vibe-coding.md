# Consortium Stage 4 (vibe-coding) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `vibe-coding` real: run the `bar-raiser-eval` pipeline **autonomously** (no human gates), resolving ambiguity with documented assumptions, and finish by opening a PR — with a severity-gated ending (minor concerns ship with notes; a major unresolved concern stops and asks the user).

**Architecture:** No new agent — vibe-coding reuses the experts + `bar-raiser` agents. A `vibe-coding.md` playbook redefines only the *posture* (autonomous, no gate, fresh branch) and the *finish* (severity-gated `shipped`/`blocked`) on top of `bar-raiser-eval.md`. `SKILL.md` routes `vibe-coding` to it. Subagent path; the `vibe.js` end-to-end workflow is a later follow-on.

**Tech Stack:** Markdown (playbook), Bash (structural test). Behavior verified live.

**Spec:** `docs/specs/2026-06-04-consortium-design.md` §3.6 (vibe-coding), §3.7 (gate exclusion), §5.3 (severity).

---

## File structure (this plan)

- `scripts/stage4.test.sh` — structural test: playbook exists + documents autonomy/PR/severity-finish; skill routes it.
- `skills/team-dev-workflow/references/vibe-coding.md` — the autonomous playbook.
- `skills/team-dev-workflow/SKILL.md` — *modified* to route `vibe-coding` and update its banner line.

---

## Task 1: Structural test (red first)

**Files:**
- Create: `scripts/stage4.test.sh`

- [ ] **Step 1: Write `scripts/stage4.test.sh`**

```bash
#!/usr/bin/env bash
# Structural checks for Stage 4 (vibe-coding). Behavior is verified live.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok(){ printf 'ok   - %s\n' "$1"; }
fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }

pb="$ROOT/skills/team-dev-workflow/references/vibe-coding.md"

# 1. playbook exists and builds on bar-raiser-eval
if [ -f "$pb" ] && grep -q "bar-raiser-eval.md" "$pb"; then ok "vibe-coding playbook present (builds on bar-raiser-eval)"; else fail "vibe-coding playbook missing or doesn't build on bar-raiser-eval"; fi

# 2. documents autonomy (no gate) + PR + fresh branch
if [ -f "$pb" ] && grep -qi "autonomous" "$pb" && grep -qi "no human gate\|no gate\|without stopping" "$pb" && grep -qi "PR" "$pb" && grep -qi "branch" "$pb"; then ok "playbook documents autonomous + PR + branch"; else fail "playbook missing autonomy/PR/branch language"; fi

# 3. documents the severity-gated finish (minor ships, major stops + asks)
if [ -f "$pb" ] && grep -qi "minor" "$pb" && grep -qi "major" "$pb" && grep -qi "stop" "$pb"; then ok "playbook documents severity-gated finish"; else fail "playbook missing severity-gated finish"; fi

# 4. SKILL routes vibe-coding to its playbook
sk="$ROOT/skills/team-dev-workflow/SKILL.md"
if grep -q "references/vibe-coding.md" "$sk"; then ok "skill links vibe-coding playbook"; else fail "skill does not link vibe-coding playbook"; fi

# 5. the human-gate section still excludes vibe-coding (regression guard)
if grep -q "vibe-coding\` never gates" "$sk"; then ok "skill still exempts vibe-coding from the human gate"; else fail "skill no longer exempts vibe-coding from the gate"; fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
```

- [ ] **Step 2: Make executable and run (expect red)**

Run: `chmod +x scripts/stage4.test.sh && bash scripts/stage4.test.sh; echo "exit=$?"`
Expected: `FAIL` lines for the playbook + routing (check 5 may already pass), non-zero exit.

- [ ] **Step 3: Commit**

```bash
git add scripts/stage4.test.sh
git commit -m "test: structural test for Stage 4 vibe-coding" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: The `vibe-coding` playbook

**Files:**
- Create: `skills/team-dev-workflow/references/vibe-coding.md`

- [ ] **Step 1: Write `skills/team-dev-workflow/references/vibe-coding.md`**

````markdown
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
````

- [ ] **Step 2: Verify the playbook's contract**

Run: `grep -qi 'autonomous' skills/team-dev-workflow/references/vibe-coding.md && grep -q 'bar-raiser-eval.md' skills/team-dev-workflow/references/vibe-coding.md && grep -qi 'minor' skills/team-dev-workflow/references/vibe-coding.md && grep -qi 'major' skills/team-dev-workflow/references/vibe-coding.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/team-dev-workflow/references/vibe-coding.md
git commit -m "feat: vibe-coding autonomous playbook (Stage 4)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Wire `vibe-coding` into the skill

**Files:**
- Modify: `skills/team-dev-workflow/SKILL.md`

- [ ] **Step 1: Update the banner summary line**

Replace:
```
- `vibe-coding` — autonomous bar-raiser run (not in this build; running experts-eval)
```
with:
```
- `vibe-coding` — autonomous: bar-raiser quality, no gates, opens a PR
```

- [ ] **Step 2: Update the routing line**

Replace:
```
- `vibe-coding` → say "vibe-coding isn't implemented in this build yet — running bar-raiser-eval (but I'll still ask before building)", then follow [`references/bar-raiser-eval.md`](references/bar-raiser-eval.md).
```
with:
```
- `vibe-coding` → follow [`references/vibe-coding.md`](references/vibe-coding.md). (Autonomous — no plan-approval gate; see that playbook.)
```

- [ ] **Step 3: Verify**

Run: `grep -q 'references/vibe-coding.md' skills/team-dev-workflow/SKILL.md && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/team-dev-workflow/SKILL.md
git commit -m "feat: route vibe-coding to its autonomous playbook (Stage 4)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Run tests green

- [ ] **Step 1: Stage 4 structural test**

Run: `bash scripts/stage4.test.sh; echo "exit=$?"`
Expected: all `ok`, `0 failure(s)`, `exit=0`.

- [ ] **Step 2: Regression — Stages 1–3**

Run: `for t in effort stage2 stage3; do bash scripts/$t.test.sh >/dev/null 2>&1 && echo "$t ok" || echo "$t FAIL"; done`
Expected: `effort ok`, `stage2 ok`, `stage3 ok`.

---

## Task 5: Live manual verification (user-driven)

Reinstall/reload first. **Test in a git repo you don't mind getting a PR/branch in** (vibe-coding acts autonomously).

- [ ] **Step 1:** `/consortium:team-dev-effort vibe-coding`
- [ ] **Step 2:** Ask for a non-trivial change. Expect: banner → it runs **without stopping for approval** → plan, build, spec-gate, experts, bar-raiser verdict + loop → ends by **opening a PR** (or, if a major concern remains, **stops and asks**). The report should list any assumptions it made, and contain **no code dumps**.
- [ ] **Step 3:** Confirm it worked on a **fresh branch** and did **not** merge.
- [ ] **Step 4:** Commit any fixes from the live test (skip if none).

---

## Self-Review (completed during planning)

- **Spec coverage:** autonomous posture, no gate, PR-on-success, fresh branch, documented assumptions (§3.6) → Task 2; severity-gated finish minor-ships/major-stops (§3.6) → Task 2; gate exclusion (§3.7) → preserved + regression-guarded in Task 1 check 5; reuses bar-raiser/experts (no new agent) → architecture.
- **Scope:** subagent path; `workflows/vibe.js` (single end-to-end autonomous workflow) deferred to Stage 4b, consistent with spec §11.
- **Placeholder scan:** none — playbook written in full.
- **Consistency:** playbook builds on `bar-raiser-eval.md`; severity tokens `minor`/`major` and the `accept`/`reject` verdict match the bar-raiser agent + spec §3.6; routing points `vibe-coding` at `vibe-coding.md`; the human-gate section in SKILL.md continues to exempt vibe-coding (checked).

---

## Follow-on (not in this plan)
- **Stage 4b:** `workflows/vibe.js` — vibe-coding as a single autonomous dynamic-workflow returning `{ outcome: "shipped" | "blocked", pr?, concerns[], report }`, with the skill handling the `blocked` escalation. This subagent playbook is the fallback.
