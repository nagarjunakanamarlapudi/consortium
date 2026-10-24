---
agent: searcher
---

## Task
Find every definition and caller of distance_km in this repository. Search code, tests, SQL and configuration, including categories with no matches, and show rerunnable commands.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/searcher/all-callers/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
- `shop/`
- `tests/`
- `web/`
- `infra/`
- `.github/`
- `Makefile`
- `pyproject.toml`

## Do not change
Keep all behavior outside the task unchanged.

## Premises
- none

## Tests
none — this case requests a read-only report.

## Done means
Return the requested evidence-backed report; do not run tests or edit files.

## Forbidden
Never commit, push, tag, merge, create a pull request or deploy.

## Stop when
Return NEEDS_CONTEXT when a premise is false or required evidence is unavailable.

## Report
Return locations.v1 in the standard report envelope with status, summary, decisions, evidence, changes, checks, questions and payload.
