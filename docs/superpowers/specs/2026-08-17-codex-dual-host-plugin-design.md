# Consortium dual-host plugin design

## Goal

Publish Consortium as one versioned GitHub repository that works with both
Claude Code and Codex. Aadhaa must consume the published GitHub version rather
than any developer's local Consortium checkout.

## Scope

This change packages the existing Consortium skills, effort controls, and
reviewer roles for Codex while retaining the current Claude plugin without a
behavioural regression. It does not add MCP servers, hooks, public-directory
publication, or new workflow tiers.

## Architecture

The Consortium repository remains the only source of workflow content. Its
existing `skills/`, `scripts/`, templates, and assets are canonical. The
existing `.claude-plugin/` package remains the Claude entry point.

Codex receives a package at `plugins/consortium/` with a
`.codex-plugin/plugin.json` manifest. Where Codex accepts the same directory
structure, the package uses relative symlinks to the canonical source. The
only copied/adapted files are those whose host format differs, such as Codex
agent TOML definitions and small host-launcher wrappers.

The repository marketplace at `.agents/plugins/marketplace.json` exposes the
Codex package at `./plugins/consortium`. It is the marketplace that users add
from GitHub with `codex plugin marketplace add
nagarjunakanamarlapudi/consortium --ref v0.1.0`.

## Shared behaviour

`scripts/effort.sh` remains the public effort-tier interface. It is refactored
to use a host-neutral state layout; neither `CLAUDE_PLUGIN_DATA` nor Codex
plugin-data directories participate in tier resolution.

For a Git worktree, the persistent workspace override is stored at the path
returned by `git rev-parse --git-path consortium/tier`. Git metadata is private
to that worktree and never committed. Outside a Git worktree, the script stores
the override below `~/.consortium/workspaces/`, in a directory named with a
`sha256-` prefix followed by the SHA-256 hex digest of the canonical working
directory. The user-wide persistent default is `~/.consortium/default-tier`.

Both hosts resolve the tier with this fixed precedence:

1. persistent workspace override;
2. explicit `CONSORTIUM_TIER` environment value, for a temporary one-off or CI
   override;
3. persistent user-wide default;
4. built-in `self-eval` default.

`team-dev-effort TIER` writes the persistent override for the active
workspace. `team-dev-effort TIER --global` writes the user-wide default and
removes the persistent override for the active workspace, preserving the
existing command's reset intent. The `--global` option must not modify
`~/.claude/settings.json` or a Codex global configuration file.

The workflow wording becomes host-neutral for planning and approvals. Claude
uses its native planning controls where available; Codex follows its normal
explicit-plan and user-approval flow. Tier semantics and reviewer selection
are identical.

## Codex agent adapters

Each applicable existing Claude reviewer gets a focused Codex TOML adapter
that preserves its review remit. Reviewers run read-only; the implementer has
workspace write access. Adapters do not duplicate the source skill content or
invent product-specific policy.

## Aadhaa dependency

Aadhaa declares Consortium in its repository marketplace file using a
`git-subdir` source whose URL is
`https://github.com/nagarjunakanamarlapudi/consortium.git` and whose path is
`./plugins/consortium`. Its `sha` is the exact 40-character object ID of the
published Consortium release candidate commit. It never refers to a local
filesystem path or the moving `main` branch. The companion install instructions
state how to refresh the marketplace and install or upgrade the plugin.

## Versioning and release sequence

The new Codex manifest starts at `0.1.0`. The Consortium pull request includes
the manifest, marketplace, adapters, documentation, tests, and any necessary
script refactor. Its pushed branch commit is the immutable source used by the
companion Aadhaa pull request, allowing both pull requests to be reviewed
together. When Consortium is merged, that same commit is tagged `v0.1.0`.

## Validation

Validation must prove:

- the Codex manifest and marketplace JSON parse and pass the plugin validation
  tooling;
- every package symlink resolves within the checked-out Consortium repository;
- Codex agent TOML definitions parse and preserve appropriate sandbox levels;
- the effort script resolves the same tier under Claude and Codex from Git
  worktree state, non-Git fallback state, `CONSORTIUM_TIER`, user default, and
  built-in default in the documented precedence order;
- `--global` affects only Consortium-owned user state and clears only the
  active workspace override;
- Claude's existing plugin checks continue to pass;
- Aadhaa's marketplace JSON resolves the immutable GitHub package and contains
  no local Consortium path.

## Review and pull-request gates

Every changed implementation file receives independent review before a pull
request is created. At minimum, the review set covers packaging correctness,
shell-script behaviour, agent/skill parity, and Aadhaa dependency integrity.
All actionable findings are resolved and the reviewers re-check the revised
diff. A final whole-diff review and the relevant test suite must pass before
each branch is pushed and its pull request opened.

## Non-goals

- Do not add a local checkout dependency to Aadhaa.
- Do not publish Consortium to the universal public plugin directory in this
  change.
- Do not add lifecycle hooks or an MCP server solely for Codex compatibility.
- Do not duplicate shared skills, scripts, templates, or assets when a safe
  relative symlink can be used.
