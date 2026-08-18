# self-eval playbook

The lightest assisted tier: the author does the work and reviews their own output. No extra reviewer subagents — the "evaluation" is a disciplined self-review.

1. **Plan (brief, grounded).** Read the relevant files and any `CLAUDE.md`/conventions. State in 2–6 lines what you'll change (files + approach) and the acceptance check. If it spans more than a couple of files, list disjoint-file chunks.
2. **Plan-approval gate (plan mode).** Present the plan for approval via plan mode (`EnterPlanMode` → `ExitPlanMode`) and **build only after the user approves** — they may tweak it first. (Trivial changes never get here — handled upstream.)
3. **Build.** Implement directly. For genuinely independent files you may dispatch parallel implementer subagents — but only over **disjoint** files (never two agents editing one file).
4. **Self-review (the evaluation).** Re-read your own diff against the plan. Check: does it do what was asked? any obvious bugs? error handling? does it match conventions? **Is it as short and clear as it should be — cut needless length, vagueness, duplication, and over-abstraction; reuse what already exists?** Do build/tests still pass? Fix what you find.
5. **Verify.** Run the project's build/tests if they exist; report results honestly (don't claim green without running them).
6. **Ship.** Commit on a branch and open a PR. Don't merge unless the user explicitly asks.

Keep it light — this tier is momentum with a sanity check, not heavy process.
