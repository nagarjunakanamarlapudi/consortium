---
name: team-dev-effort
description: Use when the user asks to view or change Consortium's development effort tier for a workspace or globally. Supports off, self-eval, experts-eval, bar-raiser-eval, debate, and vibe-coding.
---

# Consortium — development effort

Use the canonical package script for every read and write. Do not edit Codex,
Claude, or repository configuration directly.

## Read the active tier

```bash
bash "$PLUGIN_ROOT/scripts/effort.sh" --resolve
```

Report the printed tier.

## Set a tier

Accept exactly one of `off`, `self-eval`, `experts-eval`,
`bar-raiser-eval`, `debate`, or `vibe-coding`.

- For the active workspace, run `bash "$PLUGIN_ROOT/scripts/effort.sh" TIER`.
- When the user explicitly requests a global default, run:

  ```bash
  bash "$PLUGIN_ROOT/scripts/effort.sh" experts-eval --global
  ```

  Substitute the requested tier. A global write also clears the active
  workspace override by design.

After a write, run the `--resolve` command and report the effective tier and
whether the change was workspace-scoped or global.
