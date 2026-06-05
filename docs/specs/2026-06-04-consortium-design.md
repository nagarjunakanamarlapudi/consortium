# Consortium — Design Spec

- **Date:** 2026-06-04
- **Status:** Approved for planning (brainstorming complete)
- **Plugin name:** `consortium`
- **Headline skill:** `team-dev-workflow`
- **Repo:** `/Users/nagarjuna/projects/consortium` (one git repo = marketplace + plugin)

---

## 1. Summary & thesis

**Consortium** is an open-source Claude Code plugin that blends two existing pieces of prior work:

- **LLM Consortium** (`/Users/nagarjuna/projects/llm-consortium`) — an empirical study of 12 multi-agent collaboration topologies. It established *which* ways of combining agents actually improve quality: structural-adversarial review with rewrite mandates (#1), cross-model/diverse review (#2), specialist panels, structured debate; and *what fails*: naive parallel-merge ("Frankenstein"), solo self-review.
- **Ada Dev workflow** (`/Users/nagarjuna/projects/Aadhaa/.claude/skills/aadhaa-dev-workflow`) — a session-scoped effort dispatcher (`quick`/`standard`/`thorough`/`regular`) with a reviewers registry, parallel wave implementation, and multi-perspective review.

**Thesis:** Ada provides the *delivery frame* (a settable level, a banner, an off switch, the posture principle, a reviewer registry); the Consortium study provides the *content of the modes* (which deliberation pattern + the hard-won lessons). The product is a single dial — **how high is the evaluation bar?** — realized as a small ladder of evaluation tiers plus two siblings — a generative `debate` mode and an autonomous `vibe-coding` mode — all **grounded in real repo state and conversation context** (not abstract prompts, which is what the study benchmarked).

---

## 2. Goals & non-goals

### Goals
- A clean, **installable, cross-machine** Claude Code plugin (single repo doubles as its own marketplace).
- One legible product axis: an **evaluation-bar ladder** (`off` ⊂ `self-eval` ⊂ `experts-eval` ⊂ `bar-raiser-eval`) plus selectable `debate` and `vibe-coding` modes.
- **Max-parallel implementation** via subagents as a constant (not a knob).
- A **pluggable reviewer registry**: add a reviewer = add an agent file + one registry row; rows may reference *any* installed agent (Consortium's own or another plugin's).
- A strong, **general starter reviewer roster** (generalized from Aadhaa + new), with the Aadhaa stack-specific skills documented as extension *examples*.
- **Hybrid orchestration:** deterministic phases run as bundled **dynamic-workflow** scripts (Claude Code v2.1.154+) when available, with a **plain-subagent fallback** so the plugin works everywhere and stays deterministic where it can.

### Non-goals (v1)
- **Cross-model Python bridge.** Decided: subagents on the session model only. True cross-model diversity (calling Gemini/GPT/etc. via the `llm-consortium` engine) is out of scope; "diverse review" is realized as **diverse-persona** reviewers on one model.
- Porting Aadhaa's **stack-specific task skills** (flutter-e2e, internal-api-endpoint, custom-domain, beta-testing, bizops-deployer). They stay in Aadhaa; cited as examples.
- The full 12-topology matrix. We ship only the patterns that earned their place.

---

## 3. The evaluation model (the heart)

Every assisted task runs the same fixed pipeline; only the **evaluators** change with the tier:

```
Plan  →  ⟦plan checkpoint⟧  →  Build (always max-parallel subagents)  →  ⟦build checkpoint⟧  →  Ship
```

### 3.1 Efforts (`/consortium:team-dev-effort <value>`)

| Effort | Plan checkpoint | Build | Build checkpoint | Gate |
|---|---|---|---|---|
| **`off`** | — plugin stands down; plain Claude handles the whole task — | | | — |
| **`self-eval`** | author self-checks the plan | max-parallel | author self-checks the diff | none |
| **`experts-eval`** | expert reviewers vet the plan *(count scales to change)* | max-parallel | spec-compliance gate → expert panel + diverse lenses → fix loop | **advisory** |
| **`bar-raiser-eval`** | experts **+ bar-raiser** vet the plan | max-parallel | experts **+ bar-raiser**; rewrite mandates | **hard verdict gate, ≤N rounds** |
| **`debate`** | rivals argue competing approaches → **judge synthesizes** the plan | max-parallel | expert review (advisory), fix loop | advisory |
| **`vibe-coding`** | *autonomous* — plans & proceeds, no approval | max-parallel | experts **+ bar-raiser**, **autonomous** | **hard gate, severity-gated finish** |

- Tiers 1–4 (`off`…`bar-raiser-eval`) are a **cumulative ladder** — each a superset of the one above. One mental dial.
- `debate` is a selectable sibling — the **one generative mode**, whose *plan phase* is itself a consortium (LLM-Consortium v8); its build checkpoint runs at `experts-eval` level.
- `vibe-coding` is a selectable sibling — the **autonomous mode**: `bar-raiser-eval` with every human checkpoint removed (see §3.6).
- Every tier **except `vibe-coding`** also has a **human plan-approval gate** (see §3.7). "Advisory" above refers to the *reviewers* not hard-blocking — **not** to skipping *your* approval of the plan.

### 3.2 Two checkpoints
Evaluation is not a single stage — it happens at **plan** (cheapest place to catch a wrong approach) and at **build** (the diff). The tier staffs both.

### 3.3 The bar-raiser
A single authoritative gatekeeper (Amazon metaphor + study v4b), **distinct from the author and from the expert reviewers**, with blocking authority. It returns `{ verdict: accept|reject, rigor_score, rewrite_mandates[] }` and demands *rewrite mandates* (throw out and redesign weak sections), not patches. Loop ≤ N rounds (default 3); if still rejected, surface to the user.

### 3.4 Advisory vs. gated
`experts-eval` **surfaces** findings → author fixes → ships when addressed. `bar-raiser-eval` **blocks** until the bar is met. This is the crisp line between the top two tiers.

### 3.5 Cross-cutting pillars (every mode)
- **Grounded** — reviewers read real files, honor `CLAUDE.md`/conventions, and cite `file:line`.
- **Posture principle** — a tier is a *ceiling, not a quota*; trivial edits stay trivial. Reviewer count scales to the change.
- **Escalate, don't silently inflate** — if a task proves bigger/riskier mid-flight, suggest dialing up rather than quietly doing more.
- **No competing-implementations-then-merge** — deliberately avoided; that is the study's v3 "Frankenstein" anti-pattern. Build parallelism is throughput over *disjoint* files only.

### 3.6 `vibe-coding` — autonomous mode
`vibe-coding` runs the **`bar-raiser-eval` pipeline in autonomous posture**: it plans, builds, and runs the bar-raiser gate **without stopping for human input**, resolving ambiguities with **sensible assumptions it documents as it goes**, and hands back finished work **at the end** as a **PR** (never auto-merged; on a fresh branch).

**Severity-gated finish** (the sole human seam, and it's at the *end*, not mid-run):
- Bar-raiser **accepts** → open the PR.
- Bar-raiser still rejects after the N-round cap but remaining concerns are **minor** (nits, naming, small refactors) → **open the PR anyway**, with the concerns documented in the PR body.
- Remaining concerns are **major/blocking** (correctness, security, data-loss, architectural) → **stop, do not open a PR, report**, and the skill asks the human for next steps.

Because workflows can't ask for input, the *workflow* returns `{ outcome: "shipped" | "blocked", pr?, concerns[], report }` autonomously (branching on the bar-raiser's `severity` tags); the **skill** handles the escalation only when `outcome === "blocked"`. So `vibe-coding` is a single end-to-end workflow run with at most one human touchpoint *afterward*.

**Safety:** fresh branch only; permission prompts still gate destructive ops; respects budget/concurrency caps; the banner warns it runs hands-off to completion.

### 3.7 Human plan-approval gate
Every tier **except `vibe-coding`** presents the plan and **waits for the user's approval before any code is written** (the user may edit it first). At `experts-eval`+ the plan reviewers vet the plan first, so the user approves an *already-vetted* plan. The gate uses Claude Code's **native plan mode** (`EnterPlanMode` → `ExitPlanMode`) for the standard approval UI; the reviewers run *before* it, so the gate itself needs no tools (robust to plan-mode tool restrictions). This is the **human** gate — distinct from the bar-raiser's automated *quality* gate (§3.3). **Trivial edits skip the workflow entirely at every tier** — a rename, formatting, a docs/comment edit, a version bump, or a no-behavior-change one-liner is just made directly (no plan / reviewers / gate / loop); a tier is a *ceiling, not a floor*. `vibe-coding` never gates: it's autonomous, with its sole human touchpoint at the end on a major unresolved concern (§3.6). The gate is run by the *skill* (workflows can't pause for input), so it always sits at a seam between phases — never inside a workflow.

---

## 4. Plugin structure & packaging

One git repo that is simultaneously the marketplace and the plugin:

```
consortium/
├── .claude-plugin/
│   ├── plugin.json                  # plugin manifest
│   └── marketplace.json             # makes the repo installable (source: ".")
├── commands/
│   └── team-dev-effort.md           # /consortium:team-dev-effort <tier>
├── skills/
│   └── team-dev-workflow/
│       ├── SKILL.md                 # orchestrator: resolve tier → run pipeline
│       └── references/
│           ├── self-eval.md
│           ├── experts-eval.md
│           ├── bar-raiser-eval.md
│           ├── debate.md
│           └── reviewer-registry.md # change-type → which reviewers fire (pluggable core)
├── agents/
│   ├── bar-raiser.md
│   ├── spec-clarity-reviewer.md
│   ├── domain-conventions-reviewer.md
│   ├── spec-compliance-reviewer.md
│   ├── code-quality-reviewer.md
│   ├── security-reviewer.md
│   ├── cicd-reviewer.md             # NEW
│   ├── iac-change-reviewer.md       # generalized from Aadhaa cdk-change-reviewer
│   ├── test-coverage-reviewer.md
│   ├── debater.md
│   └── judge.md
├── workflows/                       # bundled dynamic-workflow scripts (skill-invoked via the Workflow tool; NOT a first-class plugin component)
│   ├── plan-review.js               # plan checkpoint fan-out
│   ├── build-review.js              # spec-gate → panel + lenses → fix loop
│   ├── bar-raiser-gate.js           # verdict loop (≤N rounds)
│   ├── debate.js                    # debaters → judge → plan
│   └── vibe.js                      # autonomous end-to-end (bar-raiser posture)
├── hooks/
│   └── hooks.json                   # SessionStart: establish session id + banner reminder
├── docs/
│   ├── specs/2026-06-04-consortium-design.md   # this file
│   └── adding-your-own-reviewer.md  # the pluggable interface, documented
├── README.md
├── LICENSE                          # MIT
└── CONTRIBUTING.md
```

### 4.1 `plugin.json`
```json
{
  "name": "consortium",
  "displayName": "Consortium",
  "description": "Team-dev workflow with selectable evaluation tiers (self-eval → experts-eval → bar-raiser-eval) plus a debate mode — multi-agent review & planning grounded in your repo.",
  "version": "0.1.0",
  "author": { "name": "Nagarjuna" },
  "license": "MIT",
  "keywords": ["code-review", "multi-agent", "workflow", "consortium", "bar-raiser", "subagents"]
}
```

### 4.2 `marketplace.json`
```json
{
  "name": "consortium",
  "owner": { "name": "Nagarjuna" },
  "plugins": [
    { "name": "consortium", "source": ".", "description": "Team-dev workflow + evaluation-tier consortiums." }
  ]
}
```
Note: marketplace name == plugin name → install reads `consortium@consortium`. Acceptable; revisit only if a multi-plugin marketplace is wanted later.

### 4.3 Install UX
```
/plugin marketplace add <owner>/consortium      # GitHub owner/repo (or git URL)
/plugin install consortium@consortium
/consortium:team-dev-effort experts-eval        # set the bar
```
Once installed, everything is namespaced: skill `consortium:team-dev-workflow`, command `/consortium:team-dev-effort`, agents `consortium:bar-raiser`, etc.

### 4.4 State & persistence
- **Global default** — `~/.claude/settings.json` → `env: { "CONSORTIUM_TIER": "self-eval" }`. Per-user, persistent, read by the orchestrator via `$CONSORTIUM_TIER`.
- **Per-session override** — set by the command without `--global`; applies to the current session only, leaving the global default untouched.
- **Resolution order:** session override → global default → `self-eval` fallback.
- **Default tier:** `self-eval`.
- **Command grammar:**
  - `team-dev-effort` — show effective tier + its source.
  - `team-dev-effort <tier>` — set session override.
  - `team-dev-effort <tier> --global` — write the global default into `~/.claude/settings.json`.
- **Banner** (printed by the orchestrator each engagement; load-bearing — its absence signals the workflow is not active). Printed as a **dimmed Markdown blockquote** so it stays unobtrusive:
  ```
  > 🎚️ Consortium: experts-eval (session) · expert panel reviews plan + diff (advisory) — change: /consortium:team-dev-effort off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding
  ```

---

## 5. Orchestrator mechanics

### 5.0 Execution model — hybrid (workflow preferred, subagent fallback)
The **skill is the conductor**: it resolves the tier, prints the banner, runs the interactive checkpoints (plan/mock approval), and decides when to ship. The **deterministic fan-out / verify / loop phases** run as **bundled dynamic-workflow scripts** (the Workflow tool) when available, and as **plain subagent dispatch (the Agent tool)** as a portable fallback when not.

- The **per-tier reference playbooks** (`references/*.md`) are the single source of truth for *what* each phase does; the workflow script and the fallback both implement the same playbook.
- **Workflows are autonomous** — they cannot pause for user input — so every phase that needs sign-off is its **own** workflow, **chained across turns** by the skill. Interactivity never lives inside a workflow.
- Workflow scripts call our agents as typed subagents — `agent(prompt, { agentType: "consortium:bar-raiser", schema })` — yielding **schema-validated** verdicts/findings (no free-text parsing).
- **Packaging reality:** dynamic workflows are *not* a first-class plugin component (no auto-registered `workflows/`). We bundle the scripts and the skill invokes them via the Workflow tool with `scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/<file>.js"` and `args`. Requires Claude Code **v2.1.154+** (research preview); the subagent fallback covers older or disabled setups (no runtime detection exists, so the skill offers the fallback whenever a workflow call isn't possible).
- **Script constraints:** scripts orchestrate only (no direct FS/shell — agents do all I/O); avoid `Date.now()` / `Math.random()` / argless `new Date()` (they throw — pass timestamps via `args`, vary by index); respect the ≤16-concurrent and 1000-agent caps; reference bundled files only via `${CLAUDE_PLUGIN_ROOT}` (no `../`).
- **`vibe-coding` is the one fully-autonomous mode** — with no interactive seams it's a *single* end-to-end workflow; its only possible human touchpoint (a major unresolved concern) is handled by the skill *after* the run returns `blocked` (§3.6).

On any build/refactor/ship request the skill runs:

0. **Resolve tier** → print banner. If `off`, announce and stand down (other skills still apply).
1. **Plan** (grounded: read repo, `CLAUDE.md`, conventions). Decompose into **disjoint-file waves** so build can parallelize safely.
   - `experts-eval`/`bar-raiser-eval`: **plan checkpoint** — dispatch plan reviewers per registry; at top tier the **bar-raiser gates the plan** before code is written.
   - `debate`: dispatch N **debaters** (rival approaches) → **judge** synthesizes the plan.
2. **Build** — dispatch implementer subagents in **parallel waves** over disjoint files (max parallelism, bounded by §7 cap).
3. **Build checkpoint** —
   - `self-eval`: author self-reviews the diff.
   - `experts-eval`: **spec-compliance reviewer (gate)** → then quality + perspective reviewers per registry in parallel → advisory fix loop.
   - `bar-raiser-eval`: experts **+ bar-raiser** → verdict + rewrite mandates, loop ≤ N until accept.
4. **Ship** — commit + open PR (never auto-merge unless asked).

### 5.1 Reviewer registry (pluggable core)
`references/reviewer-registry.md` — the single source of truth mapping **change-type → reviewer agent → checkpoint (plan/build) → mode (advisory/gating)**. Adding a reviewer = add an agent + one row. A row may reference any installed agent (e.g. `pr-review-toolkit`'s) so users compose instead of reimplement.

Always-on (at `experts-eval`+): `spec-clarity-reviewer` (plan), `domain-conventions-reviewer` (plan+build), `spec-compliance-reviewer` (build gate), `code-quality-reviewer` (build). Conditional rows fire by change-type (see roster).

### 5.2 Starter roster (`agents/`)

| agent | checkpoint | fires when | origin |
|---|---|---|---|
| `spec-clarity-reviewer` | plan | always (experts+) | Aadhaa → generalized |
| `domain-conventions-reviewer` | plan + build | always (experts+) | Aadhaa `domain-reviewer` → generalized |
| `spec-compliance-reviewer` | build (gate) | always (experts+) | Aadhaa thorough playbook |
| `code-quality-reviewer` | build | always (experts+) | study v5 + general |
| `security-reviewer` | build | authz / crypto / input / secrets | new |
| `cicd-reviewer` | build | CI/CD pipeline files change | NEW (fills the gap) |
| `iac-change-reviewer` | build | infra files (TF/CDK/Pulumi/CFN) | Aadhaa `cdk-change-reviewer` → generalized |
| `test-coverage-reviewer` | build | logic/behavior changes | new (or reuse pr-review-toolkit) |
| perspective reviewers (type-design · silent-failure · simplicity · comments) | build | by change-type | reuse `pr-review-toolkit` or ship lean versions |
| `bar-raiser` | plan + build (gate) | tier = `bar-raiser-eval` | study v4b + Amazon |
| `debater` ×N · `judge` | plan | mode = `debate` | study v8 |

> The **panel** (study v5) is the domain specialists above (security, cicd, iac, …). The **diverse lenses** (study v2b blind-spot coverage) are the *perspective reviewers* row — several different lenses on the *same* diff. `experts-eval` runs both, scaled to the change; shipped lean or reused per §10.2.

### 5.3 Synthesis & verdict (shared building blocks)
- **Rubric-guided synthesis** — when multiple reviewers return findings, the orchestrator dedups and reconciles **dimension-by-dimension** (security, correctness, maintainability, …), not naive concatenation. Reimplements the study's `merge_rubric_guided` insight; avoids the v3 Frankenstein failure.
- **Verdict gate** — bar-raiser output is structured (`accept|reject` + `rigor_score` + `rewrite_mandates[]`, each mandate tagged `severity: minor|major`). Reject → fix-implementers dispatched with the mandates → re-review. Bar to accept ≈ rigor 4/5. Loop ≤ N (default 3). The `severity` tags drive `vibe-coding`'s severity-gated finish (§3.6).

---

## 6. What we take from prior work

- **Port + generalize (reviewers):** spec-clarity, domain→domain-conventions, cdk→iac-change, spec-compliance.
- **New agents:** `cicd-reviewer`, `bar-raiser`, `debater`/`judge`, `security-reviewer`.
- **Reimplement study patterns as subagent prompts** (the study is Python; we want CC subagents): rubric-guided synthesis, adversarial rewrite-mandate (v4b), debate (v8), specialist-panel framing (v5).
- **Leave in Aadhaa (examples only):** flutter-e2e, internal-api-endpoint, custom-domain, beta-testing, bizops-deployer.
- **Generalize later (phase 2):** `mobile-app-mocks → design-mocks`, `update-claude-md → docs-refresh`.

---

## 7. Build concurrency
Max parallelism is the default, but bounded by a **safe per-wave cap** (default **4**) because concurrent test/server runs contend for ports/resources (Ada's hard-won lesson). Configurable via `CONSORTIUM_MAX_PARALLEL` (settings.json env). Pure-edit tasks with no test/server step may exceed the default; tasks that run `ci-test`/dev servers should respect it. Waves are formed over **disjoint file sets** so concurrent implementers never touch the same file.

---

## 8. Hooks (`hooks/hooks.json`)
- **`SessionStart`** — establish a session id (from the hook's stdin JSON) and surface it into context so the command/orchestrator can scope the per-session override; also emit a one-line "Consortium active (tier: …)" reminder.
- No formatting/PostToolUse hooks shipped in v1 (kept language-agnostic; users add their own).

---

## 9. Open-source polish
- `README.md` — what it is, the tier ladder, install, the registry/pluggability, a 60-second demo.
- `LICENSE` — MIT.
- `CONTRIBUTING.md` — how to add a reviewer/skill, the registry contract, testing.
- `docs/adding-your-own-reviewer.md` — the pluggable interface, using a generalized Aadhaa reviewer as the worked example.

---

## 10. Open questions / to validate during build
1. **Session-override scoping** — confirm the exact `SessionStart` hook capability for surfacing a stable session id to subsequent Bash calls; fallback to `settings.local.json` / project-scoped override if clean isolation isn't available.
2. **Reuse vs. ship** — decide per-agent whether to ship our own (`type-design`, `silent-failure`, `test-coverage`, `comment` reviewers) or reference `pr-review-toolkit`'s via the registry.
3. **Marketplace naming** — keep `consortium@consortium` or introduce a distinct marketplace name.
4. **Workflow invocation specifics** — validate in practice that the skill can run a plugin-bundled script via `Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/…", args })`, and confirm the exact `agentType` namespacing for plugin agents inside scripts (`consortium:bar-raiser` vs bare). Both are engine-level and under-documented in the research preview.
5. **Workflow availability** — research preview, v2.1.154+, can be disabled, no runtime detection. The **subagent fallback is the contract** that keeps the plugin working everywhere; the CC-version requirement is documented in the README and the skill.

---

## 11. Staged build plan (seeds the implementation plan)
The per-tier reference playbooks are authored once and executed by **either** engine. Each orchestration tier is built **subagent-fallback-first** (works everywhere), then its **bundled workflow script** is added as the deterministic upgrade.

- **Stage 0 — Skeleton:** repo + `plugin.json` + `marketplace.json`; installs as an empty, valid plugin.
- **Stage 1 — Spine:** `team-dev-effort` command + state resolution + banner + `off` and `self-eval` end-to-end (no workflows needed).
- **Stage 2 — experts-eval:** registry + plan/build checkpoints + always-on reviewers + rubric synthesis via **subagent dispatch**; then add `workflows/plan-review.js` + `workflows/build-review.js`.
- **Stage 3 — bar-raiser-eval:** `bar-raiser` agent (verdict with `severity` tags) + verdict gate + rewrite-mandate loop (subagent path); then add `workflows/bar-raiser-gate.js`.
- **Stage 4 — vibe-coding:** autonomous posture over the Stage-3 pipeline — severity-gated finish (`shipped`/`blocked`), PR-on-success, skill-side escalation on a major blocker; ships `workflows/vibe.js`. *(Depends on Stage 3.)*
- **Stage 5 — debate:** `debater`/`judge` agents + debate plan phase (subagent path); then add `workflows/debate.js`.
- **Stage 6 — specialized reviewers:** `security`, `cicd`, `iac-change`, `test-coverage`, perspective lenses + registry wiring + change-type detection.
- **Stage 7 — OSS polish:** README (incl. the v2.1.154+ requirement + fallback note), LICENSE, CONTRIBUTING, `adding-your-own-reviewer.md`, examples.

Each stage is independently testable (install + exercise the new tier/agent on both engines where applicable).

---

## 12. Success criteria
- `/plugin install consortium@consortium` works on a clean machine; `/consortium:team-dev-effort` shows/sets the tier; banner reflects the effective tier and source.
- Each tier demonstrably changes evaluation behavior on a sample change (self-check → expert panel → blocking bar-raiser); `debate` produces a judged plan.
- Adding a new reviewer requires only a new agent file + one registry row (verified with a toy reviewer).
- No cross-model dependency; runs entirely on the session model with subagents.
- `vibe-coding` runs a sample task end-to-end with **no human input**, opens a PR on success, and **stops + asks** when a *major* concern remains unresolved (minor concerns ship with notes).
