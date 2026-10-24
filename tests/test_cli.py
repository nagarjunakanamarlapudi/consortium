import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_repo(path):
    path.mkdir()
    git(path, "init", "--quiet")
    return path


def add_worktree(main, worktree):
    # Orphan worktrees exercise shared git state without making commits.
    git(main, "worktree", "add", "--quiet", "--orphan", "-b", worktree.name, str(worktree))
    return worktree


def test_version(run_cli, tmp_path):
    result = run_cli("version", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "consortium 1.0.0-next\n"
    assert result.stderr == ""


def test_unknown_subcommand_is_usage_error(run_cli):
    result = run_cli("not-a-command")
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_main_checkout_from_a_linked_worktree(tmp_path):
    from consortium.paths import main_checkout, repo_root

    main = make_repo(tmp_path / "main")
    worktree = add_worktree(main, tmp_path / "linked")
    nested = worktree / "nested"
    nested.mkdir()
    assert repo_root(nested) == worktree.resolve()
    assert main_checkout(worktree) == main.resolve()
    assert main_checkout(main) == main.resolve()


def test_repo_config_dir_follows_a_symlinked_folder(tmp_path):
    from consortium.paths import repo_config_dir

    first = make_repo(tmp_path / "first")
    config = first / ".consortium"
    config.mkdir()
    second = make_repo(tmp_path / "second")
    (second / ".consortium").symlink_to(config, target_is_directory=True)
    worktree = add_worktree(second, tmp_path / "linked")
    assert repo_config_dir(worktree) == config.resolve()
    assert repo_config_dir(second) == config.resolve()


def test_repo_config_dir_outside_git_is_the_folder_itself(tmp_path):
    from consortium.paths import repo_config_dir

    folder = tmp_path / "plain"
    folder.mkdir()
    assert repo_config_dir(folder) == (folder / ".consortium").resolve()


def test_repo_root_outside_git_is_none(tmp_path):
    from consortium.paths import repo_root

    assert repo_root(tmp_path) is None


def test_package_root_is_resolved_from_the_module():
    from consortium.paths import package_root

    assert package_root() == ROOT / "plugins/consortium"


def test_state_home_is_created_on_first_use(tmp_path, monkeypatch):
    from consortium.paths import state_home

    state = tmp_path / "custom" / "state"
    monkeypatch.setenv("CONSORTIUM_HOME", str(state))
    assert not state.exists()
    assert state_home() == state
    assert state.is_dir()
    assert state_home() == state


def test_state_home_defaults_to_user_home(tmp_path, monkeypatch):
    from consortium.paths import state_home

    monkeypatch.delenv("CONSORTIUM_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert state_home() == tmp_path / ".consortium"
    assert (tmp_path / ".consortium").is_dir()


def test_available_command_module_registers_its_handler(tmp_path, monkeypatch):
    import consortium
    from consortium.cli import main

    (tmp_path / "explain.py").write_text(
        "def register(sub):\n"
        "    parser = sub.add_parser('probe')\n"
        "    parser.set_defaults(func=lambda args: 7)\n"
    )
    monkeypatch.setattr(consortium, "__path__", [str(tmp_path)])
    importlib.invalidate_caches()
    try:
        assert main(["probe"]) == 7
    finally:
        sys.modules.pop("consortium.explain", None)


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("import missing_consortium_test_dependency\n", ModuleNotFoundError),
        ("def register(:\n", SyntaxError),
    ],
)
def test_broken_command_module_fails_loudly(tmp_path, monkeypatch, source, error):
    import consortium
    from consortium.cli import main

    (tmp_path / "explain.py").write_text(source)
    monkeypatch.setattr(consortium, "__path__", [str(tmp_path)])
    importlib.invalidate_caches()
    with pytest.raises(error):
        main(["version"])
