import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/consortium/hooks/put_on_path.py"


@pytest.fixture
def hook_env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    folder = tmp_path / "commands"
    folder.mkdir()
    return {"HOME": str(home), "XDG_BIN_HOME": str(folder), "PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"}


def installed_copy(folder, name):
    assert SCRIPT.is_file(), "SessionStart PATH hook is missing"
    (folder / "hooks").mkdir(parents=True)
    script = folder / "hooks/put_on_path.py"
    shutil.copyfile(SCRIPT, script)
    command = folder / "bin/consortium"
    command.parent.mkdir()
    command.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(name) + ' "$@"\n')
    command.chmod(0o755)
    return script, command


def run_hook(script, env, app="claude", bootstrap=None):
    env = dict(env)
    if app == "codex":
        env["PLUGIN_ROOT"] = str(Path(env["HOME"]) / "not-the-installed-copy")
    else:
        env.pop("PLUGIN_ROOT", None)
    args = [sys.executable, str(script)]
    if bootstrap is not None:
        args = [sys.executable, "-c", bootstrap, str(script)]
    result = subprocess.run(args, input='{"source":"startup"}\n', env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    return result


def run_command(env, *args, path=None):
    env = dict(env, PATH=path if path is not None else os.defpath)
    return subprocess.run(
        [str(Path(env["XDG_BIN_HOME"]) / "consortium"), *args], env=env, capture_output=True, text=True, timeout=10
    )


@pytest.mark.parametrize("app", ["claude", "codex"])
def test_writes_executable_command_that_runs_recorded_copy(tmp_path, hook_env, app):
    script, command = installed_copy(tmp_path / "installed", "recorded")
    assert run_hook(script, hook_env, app).stderr == ""
    target = Path(hook_env["XDG_BIN_HOME"]) / "consortium"
    assert target.read_text().startswith("#!/bin/sh\n#")
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    result = run_command(hook_env, "version", "two words", "quote'", "*", "")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "recorded\nversion\ntwo words\nquote'\n*\n\n"
    assert result.stderr == ""
    assert str(command) in target.read_text()


def test_prefers_first_executable_session_copy_on_path(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "recorded", "recorded")
    assert run_hook(script, hook_env, "codex").stderr == ""
    _, unrelated = installed_copy(tmp_path / "checkout", "checkout")
    cache = tmp_path / "plugins/cache/market/consortium"
    _, disabled = installed_copy(cache / "disabled", "disabled")
    disabled.chmod(0o644)
    _, first = installed_copy(cache / "first copy", "first")
    _, second = installed_copy(cache / "second", "second")
    path = ":".join(str(command.parent) for command in (unrelated, disabled, first, second))
    result = run_command(hook_env, "one argument", path=path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "first\none argument\n"
    assert result.stderr == ""


def test_path_entries_are_not_globbed(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "recorded", "recorded")
    assert run_hook(script, hook_env).stderr == ""
    cache = tmp_path / "plugins/cache/market/consortium"
    _, literal = installed_copy(cache / "copy[ab]", "literal")
    installed_copy(cache / "copya", "expanded")
    result = run_command(hook_env, path=str(literal.parent))
    assert result.returncode == 0, result.stderr
    assert result.stdout == "literal\n"


@pytest.mark.parametrize("kind", ["file", "checkout-link", "broken-link", "directory"])
def test_leaves_user_owned_paths_unchanged(tmp_path, hook_env, kind):
    script, command = installed_copy(tmp_path / "checkout", "checkout")
    target = Path(hook_env["XDG_BIN_HOME"]) / "consortium"
    if kind == "file":
        target.write_bytes(b"user's command\n\xff")
    elif kind == "directory":
        target.mkdir()
    else:
        target.symlink_to(command if kind == "checkout-link" else tmp_path / "missing")
    before = target.lstat()
    contents = target.read_bytes() if target.is_file() else None
    link = os.readlink(target) if target.is_symlink() else None
    for app in ("codex", "claude"):
        assert run_hook(script, hook_env, app).stderr == ""
        assert target.lstat().st_ino == before.st_ino
        if contents is not None:
            assert target.read_bytes() == contents
        if link is not None:
            assert os.readlink(target) == link
    assert sorted(path.name for path in target.parent.iterdir()) == ["consortium"]


@pytest.mark.parametrize("app", ["claude", "codex"])
@pytest.mark.parametrize("live", [False, True])
def test_replaces_old_readme_cache_link(tmp_path, hook_env, app, live):
    script, _ = installed_copy(tmp_path / "new", "new")
    _, old = installed_copy(tmp_path / "plugins/cache/market/consortium/old", "old")
    if not live:
        old.unlink()
    target = Path(hook_env["XDG_BIN_HOME"]) / "consortium"
    target.symlink_to(old)
    assert run_hook(script, hook_env, app).stderr == ""
    assert not target.is_symlink()
    result = run_command(hook_env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "new\n"


@pytest.mark.parametrize(
    "previous_app,app,copy_state,replaced",
    [
        ("claude", "codex", "live", True),
        ("codex", "claude", "live", False),
        ("codex", "claude", "missing", True),
        ("codex", "claude", "not-executable", True),
        ("claude", "claude", "live", True),
        ("codex", "codex", "live", True),
    ],
)
def test_refresh_policy_between_apps(tmp_path, hook_env, previous_app, app, copy_state, replaced):
    old_script, old_command = installed_copy(tmp_path / "old", "old")
    script, _ = installed_copy(tmp_path / "new", "new")
    assert run_hook(old_script, hook_env, previous_app).stderr == ""
    target = Path(hook_env["XDG_BIN_HOME"]) / "consortium"
    before = target.stat().st_ino
    if copy_state == "missing":
        old_command.unlink()
    elif copy_state == "not-executable":
        old_command.chmod(0o644)
    assert run_hook(script, hook_env, app).stderr == ""
    assert (target.stat().st_ino != before) == replaced
    result = run_command(hook_env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ("new\n" if replaced else "old\n")


@pytest.mark.parametrize("app", ["claude", "codex"])
def test_same_app_and_copy_does_not_rewrite(tmp_path, hook_env, app):
    script, _ = installed_copy(tmp_path / "installed", "recorded")
    assert run_hook(script, hook_env, app).stderr == ""
    target = Path(hook_env["XDG_BIN_HOME"]) / "consortium"
    before = target.stat()
    contents = target.read_bytes()
    assert run_hook(script, hook_env, app).stderr == ""
    assert target.stat().st_ino == before.st_ino
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    assert target.read_bytes() == contents


@pytest.mark.parametrize("xdg", [None, ""])
def test_uses_local_bin_when_xdg_is_unset_or_empty(tmp_path, hook_env, xdg):
    script, _ = installed_copy(tmp_path / "installed", "recorded")
    folder = Path(hook_env["HOME"]) / ".local/bin"
    folder.mkdir(parents=True)
    if xdg is None:
        hook_env.pop("XDG_BIN_HOME")
    else:
        hook_env["XDG_BIN_HOME"] = xdg
    assert run_hook(script, hook_env).stderr == ""
    assert os.access(folder / "consortium", os.X_OK)
    assert not (tmp_path / "commands/consortium").exists()


@pytest.mark.parametrize("xdg", [False, True])
def test_missing_bin_folder_is_not_created(tmp_path, hook_env, xdg):
    script, _ = installed_copy(tmp_path / "installed", "recorded")
    if xdg:
        folder = tmp_path / "missing/bin"
        hook_env["XDG_BIN_HOME"] = str(folder)
    else:
        hook_env.pop("XDG_BIN_HOME")
        folder = Path(hook_env["HOME"]) / ".local/bin"
    assert run_hook(script, hook_env).stderr == ""
    assert not folder.exists()
    assert not folder.parent.exists()


def test_read_only_folder_is_silent(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "installed", "recorded")
    folder = Path(hook_env["XDG_BIN_HOME"])
    folder.chmod(0o555)
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("this user can write to read-only directories")
        assert run_hook(script, hook_env).stderr == ""
        assert list(folder.iterdir()) == []
    finally:
        folder.chmod(0o755)


def test_recorded_path_with_space_and_single_quote(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "copy with a ' quote", "quoted")
    assert run_hook(script, hook_env).stderr == ""
    result = run_command(hook_env, "argument with a ' quote")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "quoted\nargument with a ' quote\n"
    assert result.stderr == ""


def test_unprintable_copy_path_is_never_written(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "copy\nexit 0\n", "newline")
    assert run_hook(script, hook_env).stderr == ""
    assert list(Path(hook_env["XDG_BIN_HOME"]).iterdir()) == []


def test_missing_recorded_copy_requests_session_refresh(tmp_path, hook_env):
    script, command = installed_copy(tmp_path / "installed", "recorded")
    assert run_hook(script, hook_env).stderr == ""
    command.unlink()
    result = run_command(hook_env)
    assert result.returncode == 127
    assert result.stdout == ""
    assert str(command) in result.stderr
    assert "start a Claude Code or Codex session" in result.stderr
    assert len(result.stderr.splitlines()) == 1


def test_failed_replace_preserves_existing_command_and_cleans_up(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "old", "old")
    new_script, _ = installed_copy(tmp_path / "new", "new")
    assert run_hook(script, hook_env).stderr == ""
    target = Path(hook_env["XDG_BIN_HOME"]) / "consortium"
    before = target.stat().st_ino
    contents = target.read_bytes()
    bootstrap = (
        "import runpy, sys\nfrom unittest.mock import patch\n"
        "with patch('os.replace', side_effect=OSError):\n"
        "    runpy.run_path(sys.argv[1], run_name='__main__')\n"
    )
    assert run_hook(new_script, hook_env, bootstrap=bootstrap).stderr == ""
    assert target.stat().st_ino == before
    assert target.read_bytes() == contents
    assert sorted(path.name for path in target.parent.iterdir()) == ["consortium"]


def test_unexpected_error_is_one_short_diagnostic(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "installed", "recorded")
    bootstrap = (
        "import runpy, sys\nfrom unittest.mock import patch\n"
        "with patch('pathlib.Path.is_dir', side_effect=RuntimeError('first\\nsecond')):\n"
        "    runpy.run_path(sys.argv[1], run_name='__main__')\n"
    )
    result = run_hook(script, hook_env, bootstrap=bootstrap)
    assert result.stderr == "consortium put_on_path: RuntimeError\n"
    assert list(Path(hook_env["XDG_BIN_HOME"]).iterdir()) == []


def test_windows_is_a_noop(tmp_path, hook_env):
    script, _ = installed_copy(tmp_path / "installed", "recorded")
    bootstrap = (
        "import pathlib, runpy, sys, tempfile\nfrom unittest.mock import patch\n"
        "with patch('os.name', 'nt'):\n"
        "    runpy.run_path(sys.argv[1], run_name='__main__')\n"
    )
    assert run_hook(script, hook_env, bootstrap=bootstrap).stderr == ""
    assert list(Path(hook_env["XDG_BIN_HOME"]).iterdir()) == []
