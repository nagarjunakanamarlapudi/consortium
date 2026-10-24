---
agent: spec-gate
dictated: ["[5, 10, 15, 20]"]
---

## Task
Review the uncommitted diff against this contract. Price thresholds must stay in the dictated order. Complete the compliance mapping and report discrepancies.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/spec-gate/number-reversal/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
Review the uncommitted diff within `shop/` and its surrounding context.

## Do not change
[5, 10, 15, 20]

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
