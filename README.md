# Consortium

A Claude Code and Codex plugin for **team-style development with a tunable
evaluation bar**. Pick how much multi-agent review a change gets — from none,
to a self-check, to an expert panel, to a blocking bar-raiser — plus a
`debate` mode and a fully autonomous `vibe-coding` mode. All review is grounded
in your real repo.

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

| Tier | What it does |
|---|---|
| `off` | Plugin stands down; the plain host handles the task. |
| `self-eval` *(default)* | Plan → build → review your own diff → PR. |
| `experts-eval` | Expert reviewers vet the plan and diff (advisory). |
| `bar-raiser-eval` | Experts + a blocking bar-raiser with rewrite mandates. |
| `debate` | Rival approaches argued, a judge picks the plan. *(coming soon — runs `experts-eval` for now)* |
| `vibe-coding` | Autonomous bar-raiser-quality run; opens a PR. |

## Usage

### Claude Code

```bash
/consortium:team-dev-effort                    # show the current tier
/consortium:team-dev-effort experts-eval       # set it for this workspace
/consortium:team-dev-effort self-eval --global # set your user-wide default
```

Then just ask Claude to build something; the `team-dev-workflow` skill
announces the active tier and runs the matching process.

### Codex

Ask Codex to use `team-dev-effort` to show or set the tier — for example,
“Set Consortium's tier to `experts-eval` for this workspace,” or “Set my
Consortium default to `self-eval`.” Then ask Codex to build something; its
`team-dev-workflow` skill applies the same tier semantics and reviewer
selection as Claude Code.

### Tier state and precedence

Both hosts use the same state, resolved in this order:

1. Persistent workspace override — in Git, `git rev-parse --git-path
   consortium/tier`; outside Git, a hashed path below
   `~/.consortium/workspaces/`.
2. `CONSORTIUM_TIER`, for a temporary one-off or CI override.
3. Persistent user-wide default: `~/.consortium/default-tier`.
4. Built-in `self-eval` default.

Setting a tier for a workspace writes its workspace override. Setting it
globally writes `~/.consortium/default-tier` and clears the active workspace
override. Neither operation writes Claude Code or Codex configuration files.

## Design mocks — `app-interactive-mocks`

Bundled skill: generate **walkable, multi-screen, Figma-quality** interactive UI mocks (phone/tablet/foldable/web) as one self-contained HTML file per flow — with a 20+ theme gallery, drift-proof state catalog, accessibility audit, and execution-ready spec sections (interaction matrix, widget-tree + navigation mapping).

```bash
/consortium:app-interactive-mocks            # or just ask: "design mocks for a checkout flow"
```

See `skills/app-interactive-mocks/README.md`.

## Requirements

Core tiers work on any recent Claude Code. The dynamic-workflow engine used by the heavier tiers requires **Claude Code v2.1.154+**; where it's unavailable the plugin falls back to plain subagent dispatch.

## License

MIT — see [LICENSE](LICENSE).
