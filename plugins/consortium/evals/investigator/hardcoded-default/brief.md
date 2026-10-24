---
agent: investigator
device: eval-no-device-needed
---

## Task
Reproduce the bug in distance_from_origin before suggesting a fix: when the caller supplies no origin it returns a distance from (0, 0), while the contract requires None. Write a failing regression in tests/test_missing_origin.py without modifying production code. Search every caller and identify the root cause.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/investigator/hardcoded-default/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
- `tests/`
- create: `tests/test_missing_origin.py`

## Do not change
Keep all behavior outside the task unchanged.

## Premises
- `shop/distance.py:8` defines distance_from_origin.

## Tests
- `tests/test_distance.py`
- `tests/test_store_card.py`
- `tests/test_search.py`
- `tests/test_feed.py`
- `tests/test_share.py`
- `tests/test_notify.py`
- create: `tests/test_missing_origin.py`
found by: `rg -l distance_km tests`

## Done means
Run `make lint` and `pytest tests/test_missing_origin.py`; the regression must demonstrate the reported bug. Record the actual command, output and nonzero exit code. Leave test changes uncommitted.

## Forbidden
Never commit, push, tag, merge, create a pull request or deploy.

## Stop when
Return NEEDS_CONTEXT when a premise is false or required evidence is unavailable.

## Report
Return case.v1 in the standard report envelope with status, summary, decisions, evidence, changes, checks, questions and payload.
