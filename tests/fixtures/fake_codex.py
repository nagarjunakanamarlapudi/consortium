#!/usr/bin/env python3
"""Local Codex boundary double; never contacts a model."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


argv = sys.argv[1:]
Path(os.environ["FAKE_CODEX_RECORD"]).write_text(json.dumps({
    "argv": argv, "stdin": sys.stdin.read(), "env": dict(os.environ), "pid": os.getpid(),
}))
mode = os.environ.get("FAKE_CODEX_MODE", "ok")
if mode == "sleep":
    # A descendant that ignores TERM proves the whole process group is killed.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen([sys.executable, "-c",
                             "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(90)"])
    Path(os.environ["FAKE_CODEX_RECORD"] + ".child").write_text(str(child.pid))
    time.sleep(90)
if mode == "quota":
    print("usage limit reached", file=sys.stderr)
    sys.exit(1)
if mode == "noisy":
    # A good run whose agent talks about HTTP 429 and quotas is still a good run.
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message",
                                                         "text": "Handles HTTP 429: rate limit and quota errors."}}))
if mode == "write-main":
    (Path(os.environ["FAKE_CODEX_MAIN"]) / "outside.txt").write_text("outside scope\n")
Path(argv[argv.index("-o") + 1]).write_text(
    "not a report" if mode == "malformed" else os.environ["FAKE_CODEX_REPORT"]
)
sys.stdout.write((Path(__file__).parent / "codex_events.jsonl").read_text())
