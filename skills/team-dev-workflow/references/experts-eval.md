# experts-eval playbook

`self-eval` plus real reviewer subagents — and the **build and its review run as one deterministic workflow**. Reviews are **advisory** (they inform; they don't hard-block like the bar-raiser), but the spec-compliance gate inside the build workflow must pass. Consult [`reviewer-registry.md`](reviewer-registry.md) for who reviews.

## 1. Plan (grounded)
Read the relevant files and `CLAUDE.md` / conventions. Write a concrete plan: files to change, approach, acceptance check; for multi-file work, list disjoint-file chunks.

## 2. Plan checkpoint
**Run the bundled plan-review workflow** (mandatory):

`Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/plan-review.js", args: { plan: "…the FULL plan text…" } })`

Pass `args` as a real JSON object containing the entire plan; it fans out the plan reviewers and returns structured findings. **Also auto-discover the repo's own plan-reviewers** (registry → *Project reviewers*): pass matching **plugin** (namespaced) reviewers in `args.extraReviewers`; **project-local (bare) reviewers you dispatch yourself** (Agent tool, in parallel) and merge their findings — the workflow can't see the repo's `.claude/agents/`. *(Fallback — no Workflow tool — dispatch `consortium:spec-clarity-reviewer` + `consortium:domain-conventions-reviewer` (and any matching project reviewers) yourself.)* Revise the plan to address blocking/important findings.

**Then the gate:** present the vetted plan for approval via plan mode (`EnterPlanMode` → `ExitPlanMode`) and **write no code until the user approves** (see the gate in SKILL.md).

## 3. Build (one workflow: implement + review + fix)
**Run the bundled build workflow** (mandatory) — it implements in parallel *and* reviews *and* fixes:

`Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/build.js", args: { plan: "…the approved plan…" } })`

For multi-file work, also pass `chunks` — disjoint-file task specs `[{ files: ["a"], instructions: "…" }, …]` — for parallel implementation. **Change-type reviewers:** match the plan's affected files/areas against the registry's **conditional** triggers (auth/crypto/secrets → `security-reviewer`; CI/CD files → `cicd-reviewer`; IaC → `iac-change-reviewer`; logic/behavior → `test-coverage-reviewer`). Pass matching **plugin** reviewers as `args.extraReviewers` (e.g. `["consortium:cicd-reviewer"]`). **Auto-discovered project-local reviewers** (bare, e.g. `cdk-change-reviewer`) the workflow can't dispatch — after `build.js`, **dispatch them yourself** (Agent tool) on the diff and fold their findings into the synthesis/fix before ship (registry → *Project reviewers*). It runs **implement → spec-compliance gate → advisory experts (`code-quality`, `domain-conventions`, `simplifier`) + any `extraReviewers` → fix loop** and returns `{ gate, reviews, barRaiser, rounds }`.

**Do not write the code yourself** — the workflow's implementer agents do (so the build is deterministic + parallel). They work from the approved plan + the repo, so the plan (now reviewed and approved) must be self-contained.

*(Fallback — only if the Workflow tool is unavailable: implement yourself over disjoint files, then run the spec-compliance gate, then `code-quality` + `domain-conventions` in parallel, fixing blocking/important findings in a loop.)*

## 4. Synthesize & present
From `build.js`'s return, give the user a **short prioritized summary** — dedup, group by dimension (correctness, conventions, clarity, risk), rank by severity. Not raw reviewer dumps; **no code re-prints** (the diff is the record). If anything blocking/important remained after the workflow's fix loop, surface it.

## 5. Ship
Run build/tests if present (report honestly). Commit on a branch and open a PR; don't merge unless asked. (Skip git for a non-repo / throwaway, like `self-eval`.)
