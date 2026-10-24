---
agent: fixture-operator
---

## Task
Run the local checks.

## Context
The sample project has a local check target.

## Scope
- `shop/distance.py`

## Do not change
Keep source files unchanged.

## Done means
Run `make lint` and `pytest tests`.

## Forbidden
Never commit or push or print secrets.

## Stop when
Report NEEDS_CONTEXT if the checks cannot run.

## Report
Return findings.v1 with check output.
