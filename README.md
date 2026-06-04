# Consortium

A Claude Code plugin for **team-style development with a tunable evaluation bar**. Pick how much multi-agent review a change gets — from none, to a self-check, to an expert panel, to a blocking bar-raiser — plus a `debate` mode and a fully autonomous `vibe-coding` mode. All review is grounded in your real repo.

> Status: **alpha** (Stages 0–1). `off` and `self-eval` are live; `experts-eval`, `bar-raiser-eval`, `debate`, and `vibe-coding` are declared and currently run `self-eval` until their stages land.

## Install

```bash
/plugin marketplace add <owner>/consortium     # or a local path during development
/plugin install consortium@consortium
```

## Tiers

| Tier | What it does |
|---|---|
| `off` | Plugin stands down; plain Claude handles the task. |
| `self-eval` *(default)* | Plan → build → review your own diff → PR. |
| `experts-eval` | Expert reviewers vet the plan and diff (advisory). *(coming soon)* |
| `bar-raiser-eval` | Experts + a blocking bar-raiser with rewrite mandates. *(coming soon)* |
| `debate` | Rival approaches argued, a judge picks the plan. *(coming soon)* |
| `vibe-coding` | Autonomous bar-raiser-quality run; opens a PR. *(coming soon)* |

## Usage

```bash
/consortium:team-dev-effort                    # show the current tier
/consortium:team-dev-effort experts-eval       # set it for this workspace
/consortium:team-dev-effort self-eval --global # set your user-wide default
```

Then just ask Claude to build something; the `team-dev-workflow` skill announces the active tier and runs the matching process.

## Requirements

Core tiers work on any recent Claude Code. The dynamic-workflow engine used by the heavier tiers requires **Claude Code v2.1.154+**; where it's unavailable the plugin falls back to plain subagent dispatch.

## License

MIT — see [LICENSE](LICENSE).
