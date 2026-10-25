import os
from pathlib import Path

import pytest
import yaml

from consortium.config import ConfigError, glob_match, load_settings
from test_cli import add_worktree, make_repo

ROOT = Path(__file__).resolve().parents[1]


def write_config(folder, values):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "config.yaml").write_text(yaml.safe_dump(values))


def test_later_layer_wins(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert load_settings(repo).get("app") == "all"
    assert load_settings(repo).source("app") == "default"
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"app": ["codex"]})
    assert load_settings(repo).get("app") == ["codex"]
    assert load_settings(repo).source("app") == "user"
    write_config(repo / ".consortium", {"app": ["claude"]})
    assert load_settings(repo).get("app") == ["claude"]
    assert load_settings(repo).source("app") == "repo"
    settings = load_settings(repo, {"app": ["codex"]})
    assert settings.get("app") == ["codex"]
    assert settings.source("app") == "brief"
    assert settings.get("thresholds.reviewers_min_lines") == 200
    assert settings.get("missing", 7) == 7


@pytest.mark.parametrize("value", ["either", "both", "codex", [], ["codex", "codex"], ["unknown"], None, 1, {}])
@pytest.mark.parametrize("location", ["user", "repo", "agent", "brief"])
def test_invalid_app_forms_name_the_accepted_forms(tmp_path, value, location):
    repo = make_repo(tmp_path / "repo")
    patch = {"app": value}
    if location == "brief":
        load = lambda: load_settings(repo, patch)
    else:
        folder = Path(os.environ["CONSORTIUM_HOME"]) if location == "user" else repo / ".consortium"
        if location == "agent":
            patch = {"agents": {"sample-reader": patch}}
        write_config(folder, patch)
        load = lambda: load_settings(repo)
    with pytest.raises(ConfigError) as error:
        load()
    message = str(error.value)
    assert "all" in message and "list" in message and "[codex]" in message
    if value == "either":
        assert "now 'all'" in message
    if value == "codex":
        assert "one-item list" in message


@pytest.mark.parametrize("value", [[], ["codex", "codex"], ["unknown"], "codex", None, [1], {}])
def test_invalid_apps_is_refused(tmp_path, value):
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"apps": value})
    with pytest.raises(ConfigError, match="apps:.*non-empty.*distinct"):
        load_settings(None)


@pytest.mark.parametrize("agent_patch", [False, True])
def test_app_plus_items_append_or_need_an_inherited_list(tmp_path, agent_patch):
    repo = make_repo(tmp_path / "repo")
    def patch(app):
        return {"agents": {"sample-reader": {"app": app}}} if agent_patch else {"app": app}
    write_config(Path(os.environ["CONSORTIUM_HOME"]), patch(["codex"]))
    write_config(repo / ".consortium", patch(["+claude"]))
    dotted = "agents.sample-reader.app" if agent_patch else "app"
    settings = load_settings(repo)
    assert settings.get(dotted) == ["codex", "claude"]
    assert settings.source(dotted) == "user+repo"
    write_config(Path(os.environ["CONSORTIUM_HOME"]), patch("all"))
    with pytest.raises(ConfigError, match=r"'\+' items need a list to add to, not 'all'"):
        load_settings(repo)


def test_plus_list_appends(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_config(repo / ".consortium", {"risk": {"auth": ["+x/**"]}})
    settings = load_settings(repo)
    assert settings.get("risk.auth") == [
        "**/auth/**", "**/authz/**", "**/authn/**", "**/login/**", "**/oauth/**", "x/**"
    ]
    assert settings.source("risk.auth") == "default+repo"


def test_plain_list_replaces(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_config(repo / ".consortium", {"risk": {"auth": ["custom/**"]}})
    settings = load_settings(repo)
    assert settings.get("risk.auth") == ["custom/**"]
    assert settings.source("risk.auth") == "repo"
    write_config(repo / ".consortium", {"risk": {"auth": []}})
    assert load_settings(repo).get("risk.auth") == []


def test_mixed_plus_list_is_an_error(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_config(repo / ".consortium", {"risk": {"auth": ["+a", "b"]}})
    with pytest.raises(ConfigError, match=r"risk\.auth"):
        load_settings(repo)


@pytest.mark.parametrize("patch, field", [
    ({"thresholds": {"reviewers_min_lines": "many"}}, "thresholds.reviewers_min_lines"),
    ({"thresholds": []}, "thresholds"),
    ({"version": True}, "version"),
    ({"risk": {"auth": "x/**"}}, "risk.auth"),
])
def test_type_mismatch_is_an_error(tmp_path, patch, field):
    repo = make_repo(tmp_path / "repo")
    write_config(repo / ".consortium", patch)
    with pytest.raises(ConfigError, match=field):
        load_settings(repo)


@pytest.mark.parametrize("user, repo_patch, field, expected", [
    ({}, {"checks": {"dart": ["flutter analyze", "flutter test {tests}"]}}, "checks.dart",
     ["flutter analyze", "flutter test {tests}"]),
    ({}, {"gate": {"command": "make check"}}, "gate.command", "make check"),
    ({"checks": {"python": ["ruff check ."]}}, {"checks": {"python": "auto"}}, "checks.python", "auto"),
    ({}, {"locks": {"disk_floor_gb": 40.5}}, "locks.disk_floor_gb", 40.5),
])
def test_auto_and_numbers_take_a_later_value(tmp_path, user, repo_patch, field, expected):
    repo = make_repo(tmp_path / "repo")
    write_config(Path(os.environ["CONSORTIUM_HOME"]), user)
    write_config(repo / ".consortium", repo_patch)
    settings = load_settings(repo)
    assert settings.get(field) == expected
    assert settings.source(field) == "repo"


def test_plus_items_need_a_list_to_add_to(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_config(repo / ".consortium", {"checks": {"dart": ["+flutter analyze"]}})
    with pytest.raises(ConfigError, match=r"checks\.dart: '\+' items need a list to add to"):
        load_settings(repo)


def test_brief_front_matter_sets_only_global_settings(tmp_path):
    brief = {"agent": "builder", "worktree": str(tmp_path / "wt"), "dictated": ["v1"], "device": "phone-1",
             "app": ["codex"], "tier": "deep", "model": "one-job-model"}
    settings = load_settings(None, brief)
    assert (settings.get("app"), settings.source("app")) == (["codex"], "brief")
    assert settings.get("worktree") == {"dir": ".worktrees", "setup": []}
    assert all(settings.get(key) is None for key in ("agent", "dictated", "device", "tier", "model"))


def test_repo_layer_found_from_worktree_and_symlinked_copy(tmp_path):
    first = make_repo(tmp_path / "first")
    write_config(first / ".consortium", {"app": ["claude"]})
    second = make_repo(tmp_path / "second")
    (second / ".consortium").symlink_to(first / ".consortium", target_is_directory=True)
    linked = add_worktree(second, tmp_path / "linked")
    for repo in (first, second, linked):
        settings = load_settings(repo)
        assert settings.get("app") == ["claude"]
        assert settings.source("app") == "repo"


@pytest.mark.parametrize("contents", ["[one, two]\n", "app: [\n"])
def test_bad_config_has_a_useful_error(tmp_path, contents):
    state = Path(os.environ["CONSORTIUM_HOME"])
    state.mkdir()
    (state / "config.yaml").write_text(contents)
    with pytest.raises(ConfigError, match="config.yaml"):
        load_settings(None)


def test_loads_do_not_share_mutable_defaults(tmp_path):
    first = load_settings(None)
    first.get("risk.auth").append("changed/**")
    assert "changed/**" not in load_settings(None).get("risk.auth")


@pytest.mark.parametrize("path, pattern, expected", [
    ("auth/x.py", "**/auth/**", True),
    ("a/auth/b/c.py", "**/auth/**", True),
    ("src/infra.py", "infra/**", False),
    ("infra/main.tf", "infra/**", True),
    ("deploy-apps-stg", "deploy-*", True),
    ("deploy/apps-stg", "deploy-*", False),
    ("test_one.py", "**/test_*.py", True),
    ("a/test_one.py", "**/test_*.py", True),
    ("a/b/test_one.py", "a/*.py", False),
    ("schema/tables.sql", "**/schema/**/*.sql", True),
    ("a/schema/b/tables.sql", "**/schema/**/*.sql", True),
    ("a+b.py", "a+b.py", True),
    ("ab.py", "a+b.py", False),
    ("a/file.py.extra", "a/*.py", False),
])
def test_glob_match(path, pattern, expected):
    assert glob_match(path, pattern) is expected


@pytest.mark.parametrize("command, denied", [
    ("git commit -m x", True), ("git -C x commit", True), ("git --no-pager commit", True), ("git push", True),
    ("git -c a=b tag v1", True), ("git merge main", True), ("git rebase main", True),
    ("gh pr create", True), ("gh pr merge 3", True), ("gh release create v1", True), ("make x --no-verify", True),
    ("echo $(git push)", True), ("echo `git commit -m x`", True), ("git push;", True),
    ("git merge-base a b", False), ("git commit-tree abc", False), ("git diff -- push.py", False),
    ("git log --grep=commit", False), ("git status", False), ("gh pr view 3", False),
    ("git -c push.default=current status", False), ("git -c commit.gpgsign=false init -q", False),
    ("git -C x -c user.name=a -c commit.gpgsign=false init", False),
    ("git -c x=y -c merge.ff=false merge main", True), ("git stash push", False),
    ("git -c rebase.autoStash=true pull", False),
])
def test_default_guard_denies_writes_and_allows_reads(command, denied):
    import re
    settings = load_settings(None)
    patterns = settings.get("guard.deny") + settings.get("guard.deny_in_repo", [])
    assert any(re.search(pattern, command) for pattern in patterns) is denied


def test_default_guard_scopes_commit_rules_but_not_push():
    import re
    settings = load_settings(None)
    deny = settings.get("guard.deny")
    deny_in_repo = settings.get("guard.deny_in_repo", [])
    assert any(re.search(pattern, "git push") for pattern in deny)
    for command in ("git commit -m x", "git tag v1", "git merge main", "git rebase main"):
        assert not any(re.search(pattern, command) for pattern in deny), command
        assert any(re.search(pattern, command) for pattern in deny_in_repo), command
