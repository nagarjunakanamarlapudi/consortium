---
agent: implementer
---

## Task
Fix the off-by-one in quantity_steps so quantity_steps(3) returns [1, 2, 3] and quantity_steps(0) returns []. Keep the existing failing regression test and add a zero-count assertion beside it.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/implementer/small-fix/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
- `shop/pricing.py`
- `tests/test_pricing.py`

## Do not change
Keep all behavior outside the task unchanged.

## Premises
- `shop/pricing.py:10` defines quantity_steps, with its regression in `tests/test_pricing.py:4`.

## Tests
- `tests/test_pricing.py`
found by: `rg -l quantity_steps tests`

## Done means
Run `make lint` and `uv run --no-project --with pytest pytest tests/test_pricing.py` (the sample repository has no environment of its own), show exit 0 for both, and leave the fix uncommitted.

## Forbidden
Never commit, push, tag, merge, create a pull request or deploy.

## Stop when
Return NEEDS_CONTEXT when a premise is false or required evidence is unavailable.

## Report
Return none in the standard report envelope with status, summary, decisions, evidence, changes, checks, questions and payload.
