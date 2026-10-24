#!/usr/bin/env python3
"""Claude print-mode boundary double; never contacts a model."""

import json
import os
from pathlib import Path
import sys


Path(os.environ["FAKE_CLAUDE_RECORD"]).write_text(json.dumps({
    "argv": sys.argv[1:], "stdin": sys.stdin.read(),
}))
print(os.environ["FAKE_CLAUDE_RESULT"])
sys.exit(int(os.environ.get("FAKE_CLAUDE_EXIT", "0")))
