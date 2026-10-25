#!/usr/bin/env python3
"""Keep the installed plugin's command available outside Claude Code sessions."""

import os
import shlex
import sys
import tempfile
from pathlib import Path

MARKER = "# Written by consortium put_on_path.py."


def should_write(target: Path, app: str, command: Path) -> bool:
    if target.is_symlink():
        link = os.readlink(target)
        return "/plugins/cache/" in link and link.endswith("/bin/consortium")
    if not target.exists():
        return True
    if not target.is_file():
        return False
    with target.open(encoding="utf-8", errors="surrogateescape") as stream:
        header = [stream.readline().rstrip("\n") for _ in range(4)]
        if header[:2] != ["#!/bin/sh", MARKER]:
            return False
        stream.seek(0)
        current = stream.read()
    # Compare the whole text, not the recorded copy: Codex updates its copy in place, so after an update that
    # changes this script the copy's path alone would match.
    if current == command_text(app, command):
        return False
    recorded_app = header[2][7:] if header[2].startswith("# app: ") else ""
    recorded_copy = header[3][8:] if header[3].startswith("# copy: ") else ""
    if app == "claude" and recorded_app == "codex":
        if Path(recorded_copy).is_file() and os.access(recorded_copy, os.X_OK):
            return False
    return True


def command_text(app: str, command: Path) -> str:
    return f"""#!/bin/sh
{MARKER}
# app: {app}
# copy: {command}
recorded_copy={shlex.quote(str(command))}
set -f
saved_ifs=$IFS
IFS=:
for entry in $PATH; do
    case "$entry" in
        */plugins/cache/*/consortium/*/bin)
            if [ -f "$entry/consortium" ] && [ -x "$entry/consortium" ]; then
                IFS=$saved_ifs
                exec "$entry/consortium" "$@"
            fi
            ;;
    esac
done
IFS=$saved_ifs
if [ -f "$recorded_copy" ] && [ -x "$recorded_copy" ]; then
    exec "$recorded_copy" "$@"
fi
printf '%s\\n' "consortium: $recorded_copy is missing; start a Claude Code or Codex session to refresh the command." >&2
exit 127
"""


def write_command(target: Path, app: str, command: Path) -> None:
    text = command_text(app, command)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", errors="surrogateescape", dir=target.parent, prefix=".consortium-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.chmod(0o755)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
        if os.name == "nt":
            return 0
        folder = Path(os.environ.get("XDG_BIN_HOME") or Path.home() / ".local/bin")
        if not folder.is_dir():
            return 0
        command = Path(__file__).resolve().parent.parent / "bin/consortium"
        if not str(command).isprintable():
            # The path lands in a comment line of an executable file; a newline would split it.
            return 0
        app = "codex" if os.environ.get("PLUGIN_ROOT") else "claude"
        target = folder / "consortium"
        if should_write(target, app, command):
            write_command(target, app, command)
    except OSError:
        pass
    except Exception as error:
        print(f"consortium put_on_path: {type(error).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
