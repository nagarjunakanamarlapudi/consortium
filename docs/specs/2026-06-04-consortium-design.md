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

**Thesis:** Ada provides the *delivery frame* (a settable level, a banner, an off switch, the posture principle, a reviewer registry); the Consortium study provides the *content of the modes* (which deliberation pattern + the hard-won lessons). The product is a single dial — **how high is the evaluation bar?** — realized as a small ladder of evaluation tiers plus one generative debate mode, all **grounded in real repo state and conversation context** (not abstract prompts, which is what the study benchmarked).

---

## 2. Goals & non-goals

### Goals
- A clean, **installable, cross-machine** Claude Code plugin (single repo doubles as its own marketplace).
- One legible product axis: an **evaluation-bar ladder** (`off` ⊂ `self-eval` ⊂ `experts-eval` ⊂ `bar-raiser-eval`) plus a selectable `debate` mode.
- **Max-parallel implementation** via subagents as a constant (not a knob).
- A **pluggable reviewer registry**: add a reviewer = add an agent file + one registry row; rows may reference *any* installed agent (Consortium's own or another plugin's).
- A strong, **general starter reviewer roster** (generalized from Aadhaa + new), with the Aadhaa stack-specific skills documented as extension *examples*.

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

- Tiers 1–4 (`off`…`bar-raiser-eval`) are a **cumulative ladder** — each a superset of the one above. One mental dial.
- `debate` is the **one generative mode**: a selectable sibling whose *plan phase* is itself a consortium (LLM-Consortium v8). Its build checkpoint runs at `experts-eval` level.

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
- **Banner** (printed by the orchestrator each engagement; load-bearing — its absence signals the workflow is not active):
  ```
  🎚️ Consortium: experts-eval (session) · expert panel reviews plan + diff (advisory) — change: /consortium:team-dev-effort off|self-eval|experts-eval|bar-raiser-eval|debate
  ```

---

## 5. Orchestrator mechanics

`team-dev-workflow/SKILL.md` is the playbook the main agent follows. On any build/refactor/ship request:

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
- **Verdict gate** — bar-raiser output is structured (`accept|reject` + `rigor_score` + `rewrite_mandates[]`). Reject → fix-implementers dispatched with the mandates → re-review. Bar to accept ≈ rigor 4/5. Loop ≤ N (default 3).

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

---

## 11. Staged build plan (seeds the implementation plan)
- **Stage 0 — Skeleton:** repo + `plugin.json` + `marketplace.json`; installs as an empty, valid plugin.
- **Stage 1 — Spine:** `team-dev-effort` command + state resolution + banner + `off` and `self-eval` modes end-to-end.
- **Stage 2 — experts-eval:** registry + plan/build checkpoints + always-on reviewers (spec-clarity, domain-conventions, spec-compliance, code-quality) + rubric synthesis.
- **Stage 3 — bar-raiser-eval:** `bar-raiser` agent + verdict gate + rewrite-mandate loop.
- **Stage 4 — debate:** `debater`/`judge` agents + debate plan phase.
- **Stage 5 — specialized reviewers:** `security`, `cicd`, `iac-change`, `test-coverage` + registry wiring + change-type detection.
- **Stage 6 — OSS polish:** README, LICENSE, CONTRIBUTING, `adding-your-own-reviewer.md`, examples.

Each stage is independently testable (install + exercise the new tier/agent).

---

## 12. Success criteria
- `/plugin install consortium@consortium` works on a clean machine; `/consortium:team-dev-effort` shows/sets the tier; banner reflects the effective tier and source.
- Each tier demonstrably changes evaluation behavior on a sample change (self-check → expert panel → blocking bar-raiser); `debate` produces a judged plan.
- Adding a new reviewer requires only a new agent file + one registry row (verified with a toy reviewer).
- No cross-model dependency; runs entirely on the session model with subagents.
