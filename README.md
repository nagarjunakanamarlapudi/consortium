# Consortium

A Claude Code and Codex plugin for **development with agents sized to the
change**. The `agent-recipes` playbook routes work, writes checked briefs,
dispatches agents and stops at decision and verification gates. Questions
and small edits stay in the chat. The old tier-based review board is
available by opting in.

> Status: **beta**. `off`, `self-eval`, `experts-eval`, `bar-raiser-eval`, and `vibe-coding` are live. `debate` is the one tier not yet built — selecting it runs `experts-eval` for now.

## Install in Claude Code

```bash
/plugin marketplace add nagarjunakanamarlapudi/consortium --ref v0.1.0
/plugin install consortium@consortium
```

## Install in Codex

```bash
codex plugin marketplace add nagarjunakanamarlapudi/consortium --ref v0.1.0
codex plugin add consortium@consortium
```

Start a new Claude Code or Codex session after installation before relying on
the Consortium skills. The marketplace reference is the released version; use
a local path only while developing the plugin itself.

## Tiers

These tiers control the old review board. It is off by default; everyday
agent work uses `agent-recipes`.

| Tier | What it does |
|---|---|
| `off` *(default)* | Old review board stands down; `agent-recipes` routes the task. |
| `self-eval` | Plan → build → review your own diff → PR. |
| `experts-eval` | Expert reviewers vet the plan and diff (advisory). |
| `bar-raiser-eval` | Experts + a blocking bar-raiser with rewrite mandates. |
| `debate` | Rival approaches argued, a judge picks the plan. *(coming soon — runs `experts-eval` for now)* |
| `vibe-coding` | Autonomous bar-raiser-quality run; opens a PR. |

## Usage

### Claude Code

```bash
/consortium:team-dev-effort                    # show the current tier
/consortium:team-dev-effort experts-eval       # set it for this workspace
/consortium:team-dev-effort off --global       # set your user-wide default
```

Then ask Claude to build something; `agent-recipes` routes the job and
delegates to `team-dev-workflow` when the resolved tier is on.

### Codex

Ask Codex to use `team-dev-effort` to show or set the tier — for example,
“Set Consortium's tier to `experts-eval` for this workspace,” or “Set my
Consortium default to `off`.” Then ask Codex to build something;
`agent-recipes` routes the job with the same briefs and gates as Claude Code.

### Turning the old workflow back on

Use `/consortium:team-dev-effort experts-eval` in Claude Code or
`$team-dev-effort experts-eval` in Codex. Add `--global` to set the default
for every workspace; existing workspace overrides still take precedence.
With a tier on, the playbook routes to `team-dev-workflow`, and the brief
check warns instead of refusing. Set the tier to `off` to return to the
agent-recipes playbook.

### Tier state and precedence

Both hosts use the same state, resolved in this order:

1. Persistent workspace override — in Git, `git rev-parse --git-path
   consortium/tier`; outside Git, a hashed path below
   `~/.consortium/workspaces/`.
2. `CONSORTIUM_TIER`, for a temporary one-off or CI override.
3. Persistent user-wide default: `~/.consortium/default-tier`.
4. Built-in `off` default.

Setting a tier for a workspace writes its workspace override. Setting it
globally writes `~/.consortium/default-tier` and clears the active workspace
override. Neither operation writes Claude Code or Codex configuration files.

## Design mocks — `app-interactive-mocks`

Bundled skill: generate **walkable, multi-screen, Figma-quality** interactive UI mocks (phone/tablet/foldable/web) as one self-contained HTML file per flow — with a 20+ theme gallery, drift-proof state catalog, accessibility audit, and execution-ready spec sections (interaction matrix, widget-tree + navigation mapping).

### Claude Code

```bash
/consortium:app-interactive-mocks
```

You can also ask, “Design mocks for a checkout flow.”

### Codex

Ask Codex naturally: “Design interactive mocks for a checkout flow.” Codex
selects `app-interactive-mocks`; Claude slash-command syntax does not apply.

See `skills/app-interactive-mocks/README.md`.

## Requirements

Agent work needs **uv, Python 3.11+ and tmux**. The `consortium` command comes
with the plugin; there's nothing else to install:

- Claude Code puts it on PATH in its own sessions.
- For Codex and your terminal, each session start writes a small `consortium`
  command into `$XDG_BIN_HOME`, or `~/.local/bin` where uv installs itself,
  when that folder exists. It runs the installed plugin's copy, and inside a
  Claude Code session that session's own copy. The plugin never replaces a
  file there that it didn't write, so a `consortium` of your own stays put.
  That folder needs to be on your PATH.
- Codex runs a plugin's hooks only once you trust them: open `/hooks` in
  Codex and trust Consortium's, and do it again when an update changes one.
  Until then the Codex playbook runs the plugin's own copy by its full path.

The old workflow's core tiers work on any recent Claude Code. The dynamic-workflow engine used by the heavier tiers requires **Claude Code v2.1.154+**; where it's unavailable the plugin falls back to plain subagent dispatch.

## License

MIT — see [LICENSE](LICENSE).
