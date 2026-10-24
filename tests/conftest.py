import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/consortium/lib"))


@pytest.fixture(autouse=True)
def isolated_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSORTIUM_HOME", str(tmp_path / "state"))


@pytest.fixture
def run_cli():
    def run(*args, env=None, cwd=None):
        process_env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if env is not None:
            process_env.update(env)
        return subprocess.run(
            [str(ROOT / "bin/consortium"), *args],
            cwd=cwd if cwd is not None else ROOT,
            env=process_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    return run
