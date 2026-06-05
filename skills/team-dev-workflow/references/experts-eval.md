# experts-eval playbook

`self-eval` plus real reviewer subagents at both checkpoints. Reviews are **advisory** (they inform; they don't hard-block like the bar-raiser), but the **spec-compliance gate must pass** before quality review. Reviewers are read-only — they report findings; you (the orchestrator) make the fixes.

Consult [`reviewer-registry.md`](reviewer-registry.md) for which reviewers fire.

## 1. Plan (grounded)
Read the relevant files and `CLAUDE.md`/conventions. Write a concrete plan: files to change, approach, acceptance check; list disjoint-file chunks if it's multi-file.

## 2. Plan checkpoint — review the plan (run the workflow)
**Run the bundled plan-review workflow.** This is the default for `experts-eval` and above — *not* optional, and yes even for a small fan-out (the deterministic engine + schema-validated findings are the whole point of these tiers):

`Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/plan-review.js", args: { plan } })`

It fans out the plan reviewers and returns their structured findings.

**Fallback — ONLY if the Workflow tool genuinely isn't available** (older Claude Code, or the call errors): dispatch the plan reviewers yourself, in parallel, in one message:
- `consortium:spec-clarity-reviewer` — is the plan concrete / complete / unambiguous?
- `consortium:domain-conventions-reviewer` — does it fit repo conventions & reuse?

Scale to the change (posture principle): a tiny change may warrant only one reviewer. **Synthesize** their findings (see §5) and revise the plan to address blocking/important items.

**Then present the vetted plan for approval via plan mode** (`EnterPlanMode` → `ExitPlanMode`) and **write no code until the user approves** — they may edit it first. (See the gate in SKILL.md. `vibe-coding` never gates; trivial changes never reach here.)

## 3. Build
Implement the (revised) plan. Independent files may be built by parallel implementer subagents — **disjoint files only** (never two agents on one file).

## 4. Build checkpoint
**a. Spec-compliance gate (must pass first).** Dispatch `consortium:spec-compliance-reviewer` on the diff. If `NOT_COMPLIANT`, fix the gaps and re-run until `COMPLIANT`. Do not start quality review until it passes.

**b. Quality + conventions (parallel, advisory).** Dispatch in parallel: `consortium:code-quality-reviewer` and `consortium:domain-conventions-reviewer`, plus any conditional reviewers the registry triggers for this change-type **whose agent is actually installed**. If a triggered reviewer isn't installed yet, note it in one line and **skip it — never substitute a different agent in its place**.

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
