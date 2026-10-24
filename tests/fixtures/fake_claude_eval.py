#!/usr/bin/env python3
"""Native eval CLI boundary double: no model or network calls."""
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
target = Path(args[2])
Path(os.environ["FAKE_CLAUDE_EVAL_RECORD"]).write_text(json.dumps({"argv": args,
    "agents_target": str((target / "agents").resolve()), "evals_target": str((target / "evals").resolve())}))
mode = os.environ.get("FAKE_CLAUDE_EVAL_MODE", "pass")
name = args[args.index("--case") + 1]
result = {"schemaVersion": 1, "partial": False, "cases": [{"name": name,
    "aggregates": {"score": 0 if mode in ("fail", "error") else 1},
    "arms": {"with": [{"score": 0 if mode in ("fail", "error") else 1,
              "error": "timeout" if mode == "error" else None,
              "graders": [{"name": "callers", "passed": mode != "fail", "explanation": "missing caller" if mode == "fail" else "matched", "scored": True}]}]}}]}
if mode == "missing":
    result["cases"] = []
else:
    result["cases"][0]["arms"]["with"] *= int(args[args.index("--runs") + 1])
Path(args[args.index("--json") + 1]).write_text("bad JSON" if mode == "malformed" else json.dumps(result))
sys.exit(1 if mode in ("fail", "error") else 0)
