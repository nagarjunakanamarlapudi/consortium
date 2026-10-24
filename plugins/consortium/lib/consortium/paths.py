"""Locate the package, machine state, and a repository's shared overrides."""

import os
import subprocess
from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def state_home() -> Path:
    home = Path(os.environ.get("CONSORTIUM_HOME", "~/.consortium")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return home


def repo_root(start: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def main_checkout(repo: Path) -> Path:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve().parent


def repo_config_dir(repo: Path) -> Path:
    return (main_checkout(repo) / ".consortium").resolve()
