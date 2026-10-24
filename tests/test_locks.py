import fcntl
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "plugins/consortium/lib"
CLI = ROOT / "bin/consortium"
PYTHON_CLI = [
    sys.executable, "-c",
    f"import sys; sys.path.insert(0, {str(LIB)!r}); "
    "from consortium.cli import main; sys.exit(main())",
]


@pytest.fixture(autouse=True)
def clean_lock_environment(monkeypatch):
    monkeypatch.delenv("CONSORTIUM_LOCKS_HELD", raising=False)
    monkeypatch.delenv("CONSORTIUM_RUN", raising=False)


@pytest.fixture
def start_cli():
    processes = []

    def start(*args, cwd=None):
        process = subprocess.Popen(
            [*PYTHON_CLI, *args], cwd=cwd or ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True,
        )
        processes.append(process)
        return process

    yield start
    for process in processes:
        # A deliberately killed wrapper can leave its child alive.
        process.poll()  # Reap exited wrappers before killpg (macOS rejects zombie-only groups).
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=5)


def wait_for_file(path, timeout=10):
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert path.exists(), f"timed out waiting for {path}"


def waiting_line(process):
    readable, _, _ = select.select([process.stderr], [], [], 10)
    assert readable, "no lock-wait diagnostic"
    line = process.stderr.readline()
    assert line.startswith("waiting for "), line
    return line


def start_holder(start_cli, tmp_path, name="test-stack", seconds=30):
    ready = tmp_path / f"{name.replace(':', '_')}-ready"
    finished = ready.with_suffix(".finished")
    code = (
        "from pathlib import Path; import time; "
        f"Path({str(ready)!r}).touch(); time.sleep({seconds}); "
        f"Path({str(finished)!r}).touch()"
    )
    process = start_cli("lock", name, "--", sys.executable, "-c", code)
    wait_for_file(ready)
    return process, finished


def owner():
    return {"pid": os.getpid(), "command": "test holder", "cwd": str(ROOT),
            "run_id": "test-run", "started": "2026-10-24T00:00:00+00:00"}


def configured_repo(tmp_path, *, floor=0, wait=3600):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    config = repo / ".consortium"
    config.mkdir()
    (config / "config.yaml").write_text(
        f"locks:\n  disk_floor_gb: {floor}\n  wait_seconds: {wait}\n"
        "worktree:\n  dir: scratch-worktrees\n"
    )
    return repo


def test_runs_the_command_and_returns_its_exit_code(run_cli):
    result = run_cli("lock", "test-stack", "--", "sh", "-c", "echo child-output; exit 7")
    assert result.returncode == 7
    assert result.stdout == "child-output\n"
    assert result.stderr == ""


def test_second_holder_waits_then_runs(start_cli, tmp_path):
    first, finished = start_holder(start_cli, tmp_path, seconds=1)
    second = start_cli(
        "lock", "test-stack", "--", sys.executable, "-c",
        f"from pathlib import Path; assert Path({str(finished)!r}).exists(); print('second ran')",
    )
    line = waiting_line(second)
    assert f"held by pid {first.pid} (" in line
    assert " since " in line
    first.communicate(timeout=10)
    stdout, stderr = second.communicate(timeout=10)
    assert first.returncode == second.returncode == 0
    assert stdout == "second ran\n"
    assert stderr == ""  # the diagnostic already read must appear only once


def test_wait_timeout_exits_4_and_names_the_holder(run_cli, start_cli, tmp_path):
    first, _ = start_holder(start_cli, tmp_path)
    result = run_cli("lock", "test-stack", "--wait", "0.1", "--", "true")
    assert result.returncode == 4
    assert f"waiting for test-stack: held by pid {first.pid} (" in result.stderr
    assert result.stderr.count("waiting for test-stack:") == 1
    assert "timed out" in result.stderr


def test_lock_freed_when_the_holder_is_killed(start_cli, tmp_path):
    from consortium.locks import lock_path

    first, _ = start_holder(start_cli, tmp_path)
    inode = lock_path("test-stack").stat().st_ino
    acquired = tmp_path / "acquired"
    second = start_cli(
        "lock", "test-stack", "--", sys.executable, "-c",
        f"from pathlib import Path; Path({str(acquired)!r}).touch()",
    )
    waiting_line(second)
    started = time.monotonic()
    first.kill()
    wait_for_file(acquired, timeout=1)
    second.communicate(timeout=5)
    assert time.monotonic() - started < 1
    assert second.returncode == 0
    assert lock_path("test-stack").stat().st_ino == inode


def test_nested_same_lock_does_not_deadlock(run_cli):
    started = time.monotonic()
    result = run_cli(
        "lock", "test-stack", "--", str(CLI), "lock", "test-stack", "--wait", "0",
        "--", "true",
    )
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started < 2
    assert result.stderr == ""


def test_child_inherits_comma_separated_locks(run_cli, monkeypatch):
    monkeypatch.setenv("CONSORTIUM_LOCKS_HELD", "release,device:phone")
    result = run_cli(
        "lock", "test-stack", "test-stack", "--", sys.executable, "-c",
        "import os; print(','.join(sorted(os.environ['CONSORTIUM_LOCKS_HELD'].split(','))))",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "device:phone,release,test-stack"
    assert os.environ["CONSORTIUM_LOCKS_HELD"] == "release,device:phone"


def test_two_names_taken_in_sorted_order(start_cli, tmp_path):
    from consortium.locks import hold

    first, _ = start_holder(start_cli, tmp_path, name="ios-build")
    second = start_cli("lock", "test-stack", "ios-build", "--", "true")
    assert waiting_line(second).startswith("waiting for ios-build:")
    with hold(["test-stack"], 0, owner()):
        pass
    first.terminate()
    first.communicate(timeout=5)
    second.communicate(timeout=5)
    assert second.returncode == 0


@pytest.mark.parametrize("name, filename", [
    ("device:emulator-5554", "device_emulator-5554.lock"),
    ("device:usb/phone", "device_usb_phone.lock"),
])
def test_device_lock_name_is_file_safe(name, filename):
    from consortium.locks import lock_path

    assert lock_path(name) == Path(os.environ["CONSORTIUM_HOME"]) / "locks" / filename


def test_disk_floor_refuses_without_running(tmp_path, monkeypatch, capsys):
    from consortium import locks

    repo = configured_repo(tmp_path, floor=40)
    worktrees = repo / "scratch-worktrees"
    for size in range(1, 7):
        folder = worktrees / f"tree-{size}"
        folder.mkdir(parents=True)
        (folder / "data").write_bytes(b"x" * size * 1024)
    marker = tmp_path / "should-not-run"

    def free_space(path):
        assert path == repo
        with locks.lock_path("disk").open("r+") as handle:
            with pytest.raises(BlockingIOError):
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return 10

    monkeypatch.setattr(locks, "free_gb", free_space)
    assert locks.run_locked(["disk"], ["touch", str(marker)], 0, repo) == 5
    assert not marker.exists()
    stderr = capsys.readouterr().err
    assert "10" in stderr and "40" in stderr
    assert "tree-1" not in stderr
    positions = [stderr.index(f"tree-{size}") for size in (6, 5, 4, 3, 2)]
    assert positions == sorted(positions)


def test_disk_floor_through_cli_uses_repo_settings(run_cli, tmp_path):
    repo = configured_repo(tmp_path, floor=1000000000)
    marker = tmp_path / "should-not-run"
    result = run_cli("lock", "disk", "--", "touch", str(marker), cwd=repo)
    assert result.returncode == 5, result.stderr
    assert not marker.exists()
    assert "1000000000" in result.stderr


def test_list_shows_holder(run_cli, start_cli, tmp_path, monkeypatch):
    from consortium.locks import list_locks, lock_path

    monkeypatch.setenv("CONSORTIUM_RUN", "example-run")
    first, _ = start_holder(start_cli, tmp_path)
    record, = list_locks()
    assert record["name"] == "test-stack"
    assert record["pid"] == first.pid
    assert record["cwd"] == str(ROOT)
    assert record["run_id"] == "example-run"
    assert "time.sleep" in record["command"]
    assert record["started"]
    result = run_cli("lock", "--list")
    assert result.returncode == 0
    assert f"test-stack: held by pid {first.pid} (" in result.stdout
    first.terminate()
    first.communicate(timeout=5)
    assert list_locks() == []
    assert lock_path("test-stack").exists()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signals_forwarded_to_child(start_cli, tmp_path, signum):
    ready, received = tmp_path / "ready", tmp_path / "received"
    code = f"""
import os, signal, time
from pathlib import Path
def receive(signum, frame):
    Path({str(received)!r}).write_text(str(signum))
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
signal.signal(signal.SIGINT, receive)
signal.signal(signal.SIGTERM, receive)
Path({str(ready)!r}).touch()
while True:
    time.sleep(1)
"""
    process = start_cli("lock", "test-stack", "--", sys.executable, "-c", code)
    wait_for_file(ready)
    process.send_signal(signum)
    stdout, stderr = process.communicate(timeout=5)
    assert received.read_text() == str(signum)
    assert process.returncode == 128 + signum, (stdout, stderr)


def test_partial_acquisition_is_released_on_timeout(start_cli, tmp_path):
    from consortium.locks import LockTimeout, hold

    start_holder(start_cli, tmp_path, name="release")
    with pytest.raises(LockTimeout):
        with hold(["release", "ios-build"], 0, owner()):
            pytest.fail("entered a contended lock")
    with hold(["ios-build"], 0, owner()):
        pass


@pytest.mark.parametrize("contents", ["not json", json.dumps(owner())], ids=["invalid", "stale"])
def test_stale_metadata_does_not_hold_a_lock(run_cli, contents):
    from consortium.locks import lock_path

    path = lock_path("test-stack")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    result = run_cli("lock", "test-stack", "--wait", "0", "--", "true")
    assert result.returncode == 0, result.stderr


def test_default_wait_is_loaded_from_repo(run_cli, start_cli, tmp_path):
    repo = configured_repo(tmp_path, wait=0.05)
    start_holder(start_cli, tmp_path)
    result = run_cli("lock", "test-stack", "--", "true", cwd=repo)
    assert result.returncode == 4, result.stderr


@pytest.mark.parametrize("args", [(), ("test-stack",), ("--list", "test-stack"),
                                  ("test-stack", "--wait", "-1", "--", "true")])
def test_invalid_lock_invocation_is_usage_error(run_cli, args):
    result = run_cli("lock", *args)
    assert result.returncode == 2
