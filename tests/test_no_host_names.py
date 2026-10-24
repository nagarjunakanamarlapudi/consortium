import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHIPPED_PATHS = (
    "plugins/consortium",
    ".claude-plugin",
    ".agents",
    "skills",
    "hooks",
    "commands",
)


def test_the_plugin_never_names_its_host_repos():
    names_file = Path(os.environ.get("CONSORTIUM_HOST_NAMES_FILE", "~/.consortium/host-names")).expanduser()
    if not names_file.is_file():
        pytest.skip("host names file is missing")
    names = [name.strip().casefold() for name in names_file.read_text().splitlines()]
    names = [name for name in names if name]
    matches = set()
    for name in SHIPPED_PATHS:
        for directory, _, filenames in os.walk(ROOT / name, followlinks=True):
            for filename in filenames:
                path = Path(directory) / filename
                relative = str(path.relative_to(ROOT))
                text = relative.casefold() + "\n" + path.read_text(errors="replace").casefold()
                if any(host in text for host in names):
                    matches.add(relative)
    assert not matches, "Host names found in: " + ", ".join(sorted(matches))
