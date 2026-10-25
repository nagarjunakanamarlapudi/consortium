---
agent: implementer
worktree: <absolute-worktree>
device: <assigned-device-id> # Omit when the agent has no device capability.
dictated: ["<verbatim-value>"] # Use [] when there are no dictated values.
# Optional overrides; omit to use the resolved settings:
# app: [codex]
# tier: deep
# model: <model>
# effort: <effort>
# timeout_minutes: 90
# report: <allowed-report-schema>
---

## Task
Implement <the chosen behavior> and leave the change ready for manager review.

## Context
Follow <repo instructions>; <decision already made> sets the expected behavior.

## Scope
Modify `<existing-path>` only, in the assigned worktree.

## Do not change
<verbatim-value>; preserve <out-of-scope behavior and files>.

## Premises
- `<existing-path>:<line>` establishes <the factual premise>; use a sole `none` bullet if there are no premises.

## Tests
found by: <searcher run id or exact search command>; affected tests: `<affected-test-path>` and <every other affected test>.

## Done means
`<language lint command>` and `<named test command>` pass through <required wrappers and locks>; show commands, relevant output and exit codes.

## Forbidden
Never git commit, git push, git tag, merge, open a PR, deploy, print secrets or edit outside Scope and the assigned worktree.

## Stop when
Return NEEDS_CONTEXT when a premise is false, instructions conflict or an unmade decision is needed; change nothing further that depends on it.

## Report
Return schema `none` with payload null, status, summary, decisions, evidence, changes, checks and questions; end with one fenced json object and leave changes uncommitted.
