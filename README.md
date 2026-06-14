# Consortium

A Claude Code plugin for **team-style development with a tunable evaluation bar**. Pick how much multi-agent review a change gets — from none, to a self-check, to an expert panel, to a blocking bar-raiser — plus a `debate` mode and a fully autonomous `vibe-coding` mode. All review is grounded in your real repo.

> Status: **beta**. `off`, `self-eval`, `experts-eval`, `bar-raiser-eval`, and `vibe-coding` are live. `debate` is the one tier not yet built — selecting it runs `experts-eval` for now.

## Install

```bash
/plugin marketplace add nagarjunakanamarlapudi/consortium     # or a local path during development
/plugin install consortium@consortium
```

## Tiers

| Tier | What it does |
|---|---|
| `off` | Plugin stands down; plain Claude handles the task. |
| `self-eval` *(default)* | Plan → build → review your own diff → PR. |
| `experts-eval` | Expert reviewers vet the plan and diff (advisory). |
| `bar-raiser-eval` | Experts + a blocking bar-raiser with rewrite mandates. |
| `debate` | Rival approaches argued, a judge picks the plan. *(coming soon — runs `experts-eval` for now)* |
| `vibe-coding` | Autonomous bar-raiser-quality run; opens a PR. |

## Usage

```bash
/consortium:team-dev-effort                    # show the current tier
/consortium:team-dev-effort experts-eval       # set it for this workspace
/consortium:team-dev-effort self-eval --global # set your user-wide default
```

Then just ask Claude to build something; the `team-dev-workflow` skill announces the active tier and runs the matching process.

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
