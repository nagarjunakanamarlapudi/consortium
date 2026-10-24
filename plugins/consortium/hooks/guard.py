#!/usr/bin/env python3
"""Keep the manager's tool hooks on a stdlib-only, silent fast path."""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
        if not payload.get("agent_id") and not os.environ.get("CONSORTIUM_RUN"):
            return 0
        command = Path(__file__).resolve().parent.parent / "bin/consortium"
        result = subprocess.run([str(command), "hook", sys.argv[1]], input=raw,
                                capture_output=True, text=True, check=True)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    except Exception as error:
        # A broken hook must never prevent the manager from doing their work.
        print(f"consortium guard: {type(error).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
