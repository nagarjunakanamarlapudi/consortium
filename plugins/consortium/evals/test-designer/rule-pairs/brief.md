---
agent: test-designer
---

## Task
Design mode. Produce a positive and negative test case for each of these three rules, using only this design: R1 accepts a quantity from 1 through 10 inclusive and rejects values outside that interval. R2 requires a signed-in user to place an order and rejects anonymous users. R3 accepts an order only when stock is at least the requested quantity, and rejects insufficient stock. Label rules R1, R2 and R3, and make expected outcomes explicit.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/test-designer/rule-pairs/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
- `shop/`

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
Return test-cases.v1 in the standard report envelope with status, summary, decisions, evidence, changes, checks, questions and payload.
