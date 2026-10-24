---
agent: ci-gate
---

## Task
Classify the recorded failure in artifacts/ci-output.txt against artifacts/flakes.md. The gate runner recorded: commit, this repository's HEAD; command, pytest tests/test_notify.py; exit code 1; failed step, that command; no reruns; no cleanup steps. Read logs only; recommend any rerun, never execute it.

## Context
The assigned sample repository is the current directory if it contains shop/; otherwise it is repos/ci-gate/known-flake/ under the eval session working directory. Work in that repository and resolve every scoped path there. The brief is outside the repository. No device is needed.

## Scope
- `artifacts/`

## Do not change
Keep all behavior outside the task unchanged.

## Premises
- `artifacts/ci-output.txt:1` records the failing command; `artifacts/flakes.md:3` lists its signature.

## Tests
none — this case requests a read-only report.

## Done means
Return the requested evidence-backed report; do not run tests or edit files.

## Forbidden
Never commit, push, tag, merge, create a pull request or deploy.

## Stop when
Return NEEDS_CONTEXT when a premise is false or required evidence is unavailable.

## Report
Return gate.v1 in the standard report envelope with status, summary, decisions, evidence, changes, checks, questions and payload.
