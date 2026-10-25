import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
import yaml

from consortium import paths
from consortium.config import ConfigError, load_settings
from consortium.registry import (
    compose_prompt, load_registry, parse_front_matter, resolve_agent,
)
from test_cli import add_worktree, make_repo
from test_config import write_config

FIXTURES = Path(__file__).parent / "fixtures/jd"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def package(tmp_path, monkeypatch):
    package = tmp_path / "package"
    agents = package / "job-descriptions"
    agents.mkdir(parents=True)
    (package / "defaults.yaml").write_bytes((ROOT / "plugins/consortium/defaults.yaml").read_bytes())
    for source in FIXTURES.glob("*.md"):
        (agents / source.name).write_bytes(source.read_bytes())
    monkeypatch.setattr(paths, "package_root", lambda: package)
    return package


def write_job(folder, name="repo-reader", **patch):
    front, body = parse_front_matter((FIXTURES / "sample-reader.md").read_text())
    front["name"] = name
    front["consortium"].update(patch)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text("---\n" + yaml.safe_dump(front) + "---\n" + body)
    return path


def test_registry_reads_plugin_and_repo_agents(tmp_path, package):
    repo = make_repo(tmp_path / "repo")
    write_job(repo / ".consortium/agents")
    registry = load_registry(repo)
    assert set(registry) == {"sample-reader", "sample-builder", "repo-reader"}
    assert registry["sample-reader"].origin == "plugin"
    assert registry["repo-reader"].origin == "repo"
    assert registry["repo-reader"].ready
    assert registry["repo-reader"].meta["write_scope"] == "all"
    assert registry["repo-reader"].meta["timeout_minutes"] == 60
    assert registry["repo-reader"].meta["app"] == "all"
    assert "cite evidence" in registry["repo-reader"].body
    linked = add_worktree(repo, tmp_path / "linked")
    assert "repo-reader" in load_registry(linked)


def test_repo_agent_cannot_shadow_a_plugin_agent(tmp_path, package):
    repo = make_repo(tmp_path / "repo")
    write_job(repo / ".consortium/agents", "sample-reader")
    with pytest.raises(ConfigError, match="a repo can't rewrite a generic agent; make a repo-only agent under its own name"):
        load_registry(repo)


def test_old_format_agent_is_not_ready():
    registry = load_registry(None)
    assert not registry["bar-raiser"].ready
    with pytest.raises(ConfigError, match="bar-raiser has no consortium: block; it belongs to the old workflow"):
        resolve_agent("bar-raiser", load_settings(None), registry)


def test_unknown_consortium_key_is_an_error(tmp_path, package):
    write_job(package / "job-descriptions", "bad-agent", unknown="value")
    with pytest.raises(ConfigError, match="unknown"):
        load_registry(None)


@pytest.mark.parametrize("patch, field", [
    ({"version": 0}, "version"), ({"version": True}, "version"),
    ({"station": "unknown"}, "station"), ({"mode": "write"}, "mode"),
    ({"write_scope": "outside"}, "write_scope"),
    ({"capabilities": ["root"]}, "capabilities"),
    ({"tier": "ultra"}, "tier"), ({"app": "other"}, "app"),
    ({"timeout_minutes": "forever"}, "timeout_minutes"),
    ({"locks": "disk"}, "locks"),
])
def test_invalid_consortium_metadata_is_an_error(tmp_path, package, patch, field):
    write_job(package / "job-descriptions", "bad-agent", **patch)
    with pytest.raises(ConfigError, match=field):
        load_registry(None)


def test_front_matter_preserves_body_and_handles_plain_markdown():
    assert parse_front_matter("plain\n---\nbody\n") == ({}, "plain\n---\nbody\n")
    assert parse_front_matter("---\r\nname: x\r\n---\r\n\r\nBody\r\n") == ({"name": "x"}, "\r\nBody\r\n")
    with pytest.raises(ConfigError):
        parse_front_matter("---\nname: x\n")
    with pytest.raises(ConfigError):
        parse_front_matter("---\n- x\n---\nbody")


def test_resolve_agent_precedence(tmp_path, package):
    repo = make_repo(tmp_path / "repo")
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {
        "app": ["codex"], "agents": {"sample-reader": {"tier": "deep"}}
    })
    registry = load_registry(repo)
    settings = load_settings(repo)
    run = resolve_agent("sample-reader", settings, registry)
    assert (run.app, run.tier, run.model, run.effort) == ("codex", "deep", "gpt-6.1-sol", "xhigh")
    assert run.sources["tier"] == "user"
    run = resolve_agent("sample-reader", settings, registry, {"model": "custom-model", "effort": "high"})
    assert (run.model, run.effort) == ("custom-model", "high")
    assert run.sources["model"] == "brief"
    write_config(repo / ".consortium", {"app": ["claude"], "agents": {"sample-reader": {"tier": "cheap"}}})
    run = resolve_agent("sample-reader", load_settings(repo), registry)
    assert (run.app, run.tier, run.model, run.effort) == ("claude", "cheap", "haiku", "low")
    with pytest.raises(FrozenInstanceError):
        run.model = "changed"


def test_repo_global_app_beats_user_agent_app(tmp_path, package):
    repo = make_repo(tmp_path / "repo")
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"agents": {"sample-reader": {"app": ["codex"]}}})
    write_config(repo / ".consortium", {"app": ["claude"]})
    run = resolve_agent("sample-reader", load_settings(repo), load_registry(repo))
    assert (run.app, run.model, run.sources["app"]) == ("claude", "sonnet", "repo")


@pytest.mark.parametrize("layer", ["user", "repo"])
@pytest.mark.parametrize("field", ["mode", "report", "station", "version", "body", "prompt"])
def test_repo_cannot_patch_mode_or_prompt(tmp_path, package, layer, field):
    repo = make_repo(tmp_path / "repo")
    folder = Path(os.environ["CONSORTIUM_HOME"]) if layer == "user" else repo / ".consortium"
    write_config(folder, {"agents": {"sample-reader": {field: "changed"}}})
    with pytest.raises(ConfigError, match="a repo can't rewrite a generic agent; make a repo-only agent under its own name"):
        resolve_agent("sample-reader", load_settings(repo), load_registry(repo), manager_app="codex")


@pytest.mark.parametrize("mode, capabilities, expected", [
    ("read-only", ["read", "search"], "read-only"),
    ("read-only", ["read", "device"], "danger-full-access"),
    ("read-only", ["read", "shell"], "danger-full-access"),
    ("worktree-write", ["read", "search"], "danger-full-access"),
])
def test_sandbox_derivation(tmp_path, package, mode, capabilities, expected):
    write_job(package / "job-descriptions", "sandbox-agent", mode=mode, capabilities=capabilities)
    run = resolve_agent("sandbox-agent", load_settings(None), load_registry(None), manager_app="codex")
    assert run.sandbox == expected


@pytest.mark.parametrize("manager, model", [("claude", "sonnet"), ("codex", "gpt-6.1-sol"), (None, "gpt-6.1-sol")])
def test_all_becomes_the_manager_app(package, manager, model):
    run = resolve_agent("sample-reader", load_settings(None), load_registry(None), manager_app=manager)
    assert (run.app, run.model) == (manager or "codex", model)
    assert run.allowed_apps == ("codex", "claude")
    assert run.sources["allowed_apps"] == run.sources["app"]


@pytest.mark.parametrize("app, manager, expected", [
    (["claude"], "codex", "claude"), (["codex"], "claude", "codex"),
    (["claude", "codex"], "codex", "codex"), (["codex", "claude"], "claude", "claude"),
    (["claude", "codex"], None, "claude"),
])
def test_explicit_app_list_preserves_order_and_prefers_manager(package, app, manager, expected):
    run = resolve_agent("sample-reader", load_settings(None), load_registry(None), {"app": app}, manager)
    assert run.app == expected
    assert run.allowed_apps == tuple(app)
    assert run.sources["app"] == run.sources["allowed_apps"] == "brief"


def test_narrowed_apps_refuse_an_agent_outside_the_list(tmp_path, package):
    state = Path(os.environ["CONSORTIUM_HOME"])
    write_config(state, {"apps": ["codex"]})
    run = resolve_agent("sample-reader", load_settings(None), load_registry(None), manager_app="claude")
    assert run.app == "codex" and run.allowed_apps == ("codex",)
    write_config(state, {"apps": ["codex"], "agents": {"sample-reader": {"app": ["claude"]}}})
    with pytest.raises(ConfigError, match="claude"):
        resolve_agent("sample-reader", load_settings(None), load_registry(None), manager_app="claude")


@pytest.mark.parametrize("location", ["global", "agent", "job", "brief"])
def test_app_names_must_be_in_configured_apps(package, location):
    patch = {"apps": ["codex"]}
    front = {}
    if location == "global":
        patch["app"] = ["claude"]
    elif location == "agent":
        patch["agents"] = {"sample-reader": {"app": ["claude"]}}
    elif location == "job":
        write_job(package / "job-descriptions", "sample-reader", app=["claude"])
    else:
        front["app"] = ["claude"]
    write_config(Path(os.environ["CONSORTIUM_HOME"]), patch)
    with pytest.raises(ConfigError, match=r"app:.*all.*list.*\[codex\].*claude"):
        resolve_agent("sample-reader", load_settings(None, front), load_registry(None), front)


def test_all_uses_configured_app_order(package):
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"apps": ["claude", "codex"]})
    run = resolve_agent("sample-reader", load_settings(None), load_registry(None))
    assert run.app == "claude" and run.allowed_apps == ("claude", "codex")


@pytest.mark.parametrize("inherited, patch, expected", [
    (["codex"], ["+claude"], ("codex", "claude")),
    ("all", ["+claude"], None),
])
def test_agent_app_appends_to_job_list(package, inherited, patch, expected):
    write_job(package / "job-descriptions", "sample-reader", app=inherited)
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"agents": {"sample-reader": {"app": patch}}})
    if expected is None:
        with pytest.raises(ConfigError, match=r"'\+' items need a list to add to, not 'all'"):
            resolve_agent("sample-reader", load_settings(None), load_registry(None))
    else:
        run = resolve_agent("sample-reader", load_settings(None), load_registry(None))
        assert run.allowed_apps == expected
        assert run.sources["app"] == run.sources["allowed_apps"] == "plugin+user"


@pytest.mark.parametrize("agent_patch", [False, True])
def test_app_layers_alternate_all_and_lists(tmp_path, package, agent_patch):
    repo = make_repo(tmp_path / "repo")
    def patch(app):
        return {"agents": {"sample-reader": {"app": app}}} if agent_patch else {"app": app}
    write_config(Path(os.environ["CONSORTIUM_HOME"]), patch(["codex"]))
    write_config(repo / ".consortium", patch("all"))
    jobs = load_registry(repo)
    run = resolve_agent("sample-reader", load_settings(repo), jobs, manager_app="claude")
    assert (run.app, run.sources["app"]) == ("claude", "repo")
    front = {"app": ["claude"]}
    run = resolve_agent("sample-reader", load_settings(repo, front), jobs, front, "codex")
    assert run.allowed_apps == ("claude",)
    assert (run.app, run.sources["app"], run.sources["allowed_apps"]) == ("claude", "brief", "brief")


@pytest.mark.parametrize("value", ["either", "both", "codex", [], ["codex", "codex"], ["unknown"], None, 1, {}])
@pytest.mark.parametrize("location", ["job", "brief"])
def test_invalid_app_in_job_or_direct_brief(package, value, location):
    if location == "job":
        write_job(package / "job-descriptions", "bad-agent", app=value)
        load = lambda: load_registry(None)
    else:
        load = lambda: resolve_agent("sample-reader", load_settings(None), load_registry(None), {"app": value})
    with pytest.raises(ConfigError) as error:
        load()
    message = str(error.value)
    assert "all" in message and "list" in message and "[codex]" in message
    if value == "either":
        assert "now 'all'" in message
    if value == "codex":
        assert "one-item list" in message


@pytest.mark.parametrize("manager", ["all", "either", ["codex"]])
def test_manager_must_be_launchable(package, manager):
    with pytest.raises(ConfigError, match="manager_app"):
        resolve_agent("sample-reader", load_settings(None), load_registry(None), manager_app=manager)


def test_notes_locks_and_tier_settings_are_applied(tmp_path, package):
    repo = make_repo(tmp_path / "repo")
    write_config(Path(os.environ["CONSORTIUM_HOME"]), {"agents": {"sample-reader": {"notes": ["User note."]}}})
    write_config(repo / ".consortium", {
        "tiers": {"standard": {"codex": {"model": "repo-model"}}},
        "agents": {"sample-reader": {"notes": ["+Repo note."], "locks": ["+disk"]}},
    })
    run = resolve_agent("sample-reader", load_settings(repo), load_registry(repo), manager_app="codex")
    assert run.notes == ("User note.", "Repo note.")
    assert run.sources["notes"] == "user+repo"
    assert run.locks == ("disk",)
    assert (run.model, run.sources["model"]) == ("repo-model", "repo")


def test_brief_report_must_be_an_alternative(package):
    settings, registry = load_settings(None), load_registry(None)
    run = resolve_agent("sample-reader", settings, registry, {"report": "locations.v1"}, "codex")
    assert run.report == "locations.v1"
    with pytest.raises(ConfigError, match="report"):
        resolve_agent("sample-reader", settings, registry, {"report": "ops.v1"}, "codex")


def test_compose_prompt_parts_in_order(package):
    registry = load_registry(None)
    run = resolve_agent("sample-reader", load_settings(None), registry, manager_app="codex")
    run = replace(run, notes=("Use the repo conventions.", "Read README.md."))
    prompt = compose_prompt(registry[run.name], run, "Do the scoped task.")
    parts = [
        "# You are the sample-reader agent (job description v2)",
        "Read the files in scope", "## Notes from this repo\n- Use the repo conventions.\n- Read README.md.",
        "## Your brief\nDo the scoped task.", "## Your report", "findings.v1",
    ]
    offsets = [prompt.index(part) for part in parts]
    assert offsets == sorted(offsets)
    assert all(field in prompt.split("## Your report")[1] for field in (
        "status", "summary", "decisions", "evidence", "changes", "checks", "questions", "payload"
    ))
    assert "## Notes from this repo" not in compose_prompt(registry[run.name], replace(run, notes=()), "")


def test_compose_prompt_keeps_dispatch_with_the_manager(package):
    registry = load_registry(None)
    run = resolve_agent("sample-reader", load_settings(None), registry, manager_app="codex")
    header = compose_prompt(registry[run.name], run, "Do the scoped task.").split("\n\n")[0]
    assert header.startswith("# You are the sample-reader agent (job description v2)\n")
    assert "Do this brief yourself." in header
    assert "agent-recipes and team-dev-workflow skills" in header
