---
description: Show or set the Consortium evaluation tier (off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding). Pass --global to persist a Consortium user default.
argument-hint: "[off|self-eval|experts-eval|bar-raiser-eval|debate|vibe-coding] [--global]"
allowed-tools: Bash
---

Run the Consortium state script and report its output to the user verbatim:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/effort.sh" $ARGUMENTS
```

Notes:
- No arguments → prints the current tier and where it came from.
- A tier name → sets the per-workspace override.
- A tier name plus `--global` → writes your Consortium user default into `~/.consortium/default-tier`.
- Do not add commentary beyond the script's output unless the user asks a follow-up.
