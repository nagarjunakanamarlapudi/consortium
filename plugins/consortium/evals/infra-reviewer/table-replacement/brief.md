---
agent: infra-reviewer
---

## Task
Review the uncommitted infrastructure change. TABLE is a declarative resource: name is its logical id; changing that id replaces the stateful table, and removal of the old table deletes its data. Flag replacement and data loss.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/infra-reviewer/table-replacement/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
Review the uncommitted diff within `infra/` and its surrounding context.

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
Return findings.v1 in the standard report envelope with status, summary, decisions, evidence, changes, checks, questions and payload.
