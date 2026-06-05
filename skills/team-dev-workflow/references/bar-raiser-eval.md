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
