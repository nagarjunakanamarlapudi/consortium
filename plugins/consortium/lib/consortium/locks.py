"""Machine-wide advisory locks and commands run while holding them."""

import argparse
import fcntl
import json
import math
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from consortium import paths
from consortium.cli import EXIT_DISK, EXIT_FAIL, EXIT_LOCK_TIMEOUT, EXIT_OK
from consortium.config import ConfigError, load_settings


class LockTimeout(Exception):
    """A lock could not be acquired before the wait expired."""


class DiskFloor(Exception):
    """The main checkout has less free space than its configured floor."""


def lock_path(name: str) -> Path:
    return paths.state_home() / "locks" / f"{name.replace(':', '_').replace('/', '_')}.lock"


def _held_names() -> set[str]:
    return {name for name in os.environ.get("CONSORTIUM_LOCKS_HELD", "").split(",") if name}


def _read_owner(handle) -> dict:
    try:
        handle.seek(0)
        value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _holder_text(name: str, owner: dict) -> str:
    return (f"{name}: held by pid {owner.get('pid', '?')} "
            f"({owner.get('command', '?')}) since {owner.get('started', '?')}")


@contextmanager
def hold(names: list[str], wait_seconds: float, owner: dict):
    """Acquire in name order; closing the files releases even a partial set.

    Lock files stay in place: unlinking one would let another process lock a
    different inode while a waiter still has the old file open.
    """
    deadline = time.monotonic() + wait_seconds
    inherited = _held_names()
    with ExitStack() as stack:
        for name in sorted(set(names) - inherited):
            path = lock_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context(path.open("a+"))
            announced = False
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    holder = _read_owner(handle)
                    if not announced:
                        print(f"waiting for {_holder_text(name, holder)}", file=sys.stderr, flush=True)
                        announced = True
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise LockTimeout(f"timed out acquiring {_holder_text(name, holder)}")
                    time.sleep(min(0.5, remaining))
            handle.seek(0)
            handle.truncate()
            json.dump({**owner, "name": name}, handle)
            handle.flush()
        yield


def list_locks() -> list[dict]:
    """Return owners of locks held now, ignoring stale on-disk metadata."""
    folder = paths.state_home() / "locks"
    records = []
    for path in sorted(folder.glob("*.lock")):
        try:
            with path.open("r+") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    record = _read_owner(handle)
                    record.setdefault("name", path.stem)
                    records.append(record)
        except FileNotFoundError:
            continue
    return records


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024 ** 3)


def _check_disk(repo: Path | None, settings) -> None:
    floor = settings.get("locks.disk_floor_gb")
    if floor <= 0:
        return
    checkout = repo or Path.cwd()
    try:
        checkout = paths.main_checkout(checkout)
    except subprocess.CalledProcessError:
        pass  # Plain folders keep their own settings and use their own disk.
    available = free_gb(checkout)
    if available >= floor:
        return
    folder = checkout / Path(settings.get("worktree.dir")).expanduser()
    sizes = []
    if folder.is_dir():
        for child in folder.iterdir():
            if not child.is_dir() or child.is_symlink():
                continue
            size = 0
            for file in child.rglob("*"):
                try:
                    if not file.is_symlink() and file.is_file():
                        size += file.stat().st_size
                except OSError:
                    continue
            sizes.append((size, child))
    lines = [f"disk: {available:g} GB free at {checkout}; floor is {floor} GB",
             f"largest folders under {folder}:"]
    for size, child in sorted(sizes, key=lambda item: (-item[0], str(item[1])))[:5]:
        lines.append(f"  {size / (1024 ** 3):.3f} GB  {child}")
    raise DiskFloor("\n".join(lines))


def _run_child(cmd: list[str], env: dict) -> int:
    child = None
    pending = []

    def forward(signum, frame):
        if child is None:
            pending.append(signum)
        else:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, forward)
        child = subprocess.Popen(cmd, env=env)
        for signum in pending:
            forward(signum, None)
        code = child.wait()
        return 128 - code if code < 0 else code
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run_locked(names: list[str], cmd: list[str], wait_seconds: float, repo: Path | None) -> int:
    settings = load_settings(repo)
    owner = {"pid": os.getpid(), "command": shlex.join(cmd), "cwd": str(Path.cwd()),
             "run_id": os.environ.get("CONSORTIUM_RUN"),
             "started": datetime.now(timezone.utc).isoformat()}
    try:
        with hold(names, wait_seconds, owner):
            if "disk" in names:
                _check_disk(repo, settings)
            env = dict(os.environ)
            env["CONSORTIUM_LOCKS_HELD"] = ",".join(sorted(_held_names() | set(names)))
            return _run_child(cmd, env)
    except LockTimeout as error:
        print(str(error), file=sys.stderr)
        return EXIT_LOCK_TIMEOUT
    except DiskFloor as error:
        print(str(error), file=sys.stderr)
        return EXIT_DISK


def _wait_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("wait must be a finite, nonnegative number") from error
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("wait must be a finite, nonnegative number")
    return seconds


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "lock", help="run a command with machine-wide locks, or list their holders",
        usage="consortium lock NAME [NAME...] [--wait SECONDS] -- CMD...\n       consortium lock --list",
    )
    parser.add_argument("--list", action="store_true", help="list current lock holders")
    parser.add_argument("--wait", type=_wait_seconds, metavar="SECONDS")
    # Keep the command's flags untouched. Options after the first name are
    # parsed separately, only on the left of the required '--' separator.
    parser.add_argument("arguments", nargs=argparse.REMAINDER, metavar="NAME")
    parser.set_defaults(func=_lock)


def _lock(args: argparse.Namespace) -> int:
    arguments = args.arguments
    separator = arguments.index("--") if "--" in arguments else len(arguments)
    header, cmd = arguments[:separator], arguments[separator + 1:]
    parser = argparse.ArgumentParser(prog="consortium lock")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--list", action="store_true", default=args.list)
    parser.add_argument("--wait", type=_wait_seconds, default=args.wait)
    options = parser.parse_args(header)
    if options.list:
        if options.names or cmd or options.wait is not None:
            parser.error("--list cannot be combined with names, a command, or --wait")
        for record in list_locks():
            print(_holder_text(record["name"], record))
        return EXIT_OK
    if not options.names or not cmd:
        parser.error("require at least one lock name and a command after '--'")
    try:
        repo = paths.repo_root(Path.cwd()) or Path.cwd()
        wait = options.wait
        if wait is None:
            wait = _wait_seconds(str(load_settings(repo).get("locks.wait_seconds")))
        return run_locked(options.names, cmd, wait, repo)
    except (ConfigError, OSError, argparse.ArgumentTypeError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL
