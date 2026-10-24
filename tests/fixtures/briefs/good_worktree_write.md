---
agent: fixture-writer
dictated: [Keep the public function name.]
---

## Task
Improve the distance helper without changing its interface.

## Context
The helper is used by several surfaces.

## Scope
- `shop/distance.py`

## Do not change
Keep the public function name.

## Premises
- The helper is defined at `shop/distance.py:4`.

## Tests
- `tests/test_distance.py`
- `tests/test_store_card.py`
- `tests/test_search.py`
- `tests/test_feed.py`
- `tests/test_share.py`
- `tests/test_notify.py`
found by: `rg -l distance_km tests`

## Done means
Run `make lint` and `pytest tests`.

## Forbidden
Never commit or push. Never edit outside Scope or print secrets.

## Stop when
Report NEEDS_CONTEXT if a premise is false or a decision is needed.

## Report
Return findings.v1 with changes and evidence.
