"""Read job descriptions and resolve one agent against a settings snapshot."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from consortium import paths
from consortium.config import ConfigError, Settings, _merge

REWRITE_ERROR = "a repo can't rewrite a generic agent; make a repo-only agent under its own name"
STATIONS = {"investigate", "design", "build", "check", "verify", "ship", "record", "operate"}
MODES = {"read-only", "worktree-write", "operate"}
CAPABILITIES = {"read", "search", "shell", "edit", "toolchain", "device", "dev-stack", "cloud", "web"}
TIERS = {"deep", "standard", "cheap"}
APPS = {"claude", "codex", "either"}
LIST_FIELDS = {"capabilities", "locks", "alt_reports", "inputs", "done_means", "stop_when", "forbidden", "knowledge", "triggers"}
META_FIELDS = LIST_FIELDS | {"version", "station", "mode", "write_scope", "tier", "app", "timeout_minutes", "report"}
PATCH_FIELDS = {"app", "tier", "model", "effort", "timeout_minutes", "locks", "notes", "done_means", "forbidden", "triggers", "knowledge"}


def parse_front_matter(text: str) -> tuple[dict, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            try:
                front = yaml.safe_load("".join(lines[1:index]))
            except yaml.YAMLError as error:
                raise ConfigError("invalid YAML front matter") from error
            if front is None:
                front = {}
            if not isinstance(front, dict):
                raise ConfigError("front matter must be a mapping")
            return front, "".join(lines[index + 1:])
    raise ConfigError("front matter has no closing '---'")


def _validate_meta(meta: dict) -> dict:
    if not isinstance(meta, dict):
        raise ConfigError("consortium: expected a mapping")
    unknown = set(meta) - META_FIELDS
    if unknown:
        raise ConfigError(f"unknown consortium key: {', '.join(sorted(map(str, unknown)))}")
    meta = deepcopy(meta)
    meta.setdefault("app", "either")
    meta.setdefault("write_scope", "all")
    meta.setdefault("timeout_minutes", 60)
    if type(meta.get("version")) is not int or meta["version"] < 1:
        raise ConfigError("consortium.version: expected an integer >= 1")
    for key, choices in (
        ("station", STATIONS), ("mode", MODES), ("write_scope", {"all", "tests"}),
        ("tier", TIERS), ("app", APPS),
    ):
        if not isinstance(meta.get(key), str) or meta[key] not in choices:
            raise ConfigError(f"consortium.{key}: invalid value")
    if type(meta["timeout_minutes"]) is not int or meta["timeout_minutes"] <= 0:
        raise ConfigError("consortium.timeout_minutes: expected a positive integer")
    if not isinstance(meta.get("report"), str) or not meta["report"]:
        raise ConfigError("consortium.report: expected a schema name or 'none'")
    for key in LIST_FIELDS:
        value = meta.setdefault(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigError(f"consortium.{key}: expected a list of strings")
    if not set(meta["capabilities"]) <= CAPABILITIES:
        raise ConfigError("consortium.capabilities: unknown capability")
    return meta


@dataclass(frozen=True)
class JobDescription:
    name: str
    path: Path
    origin: Literal["plugin", "repo"]
    front: dict
    meta: dict
    body: str

    @property
    def ready(self) -> bool:
        return bool(self.meta)


def load_registry(repo: Path | None) -> dict[str, JobDescription]:
    registry = {}
    folders = [("plugin", paths.package_root() / "job-descriptions")]
    if repo is not None:
        folders.append(("repo", paths.repo_config_dir(repo) / "agents"))
    for origin, folder in folders:
        for path in sorted(folder.glob("*.md")):
            try:
                front, body = parse_front_matter(path.read_text())
                name = front.get("name", path.stem)
                if not isinstance(name, str) or not name:
                    raise ConfigError("name: expected a nonempty string")
                if name in registry:
                    raise ConfigError(REWRITE_ERROR)
                meta = _validate_meta(front["consortium"]) if "consortium" in front else {}
            except (ConfigError, OSError, UnicodeError) as error:
                raise ConfigError(f"{path}: {error}") from error
            registry[name] = JobDescription(name, path, origin, front, meta, body)
    return registry


@dataclass(frozen=True)
class AgentRun:
    name: str
    version: int
    app: str
    tier: str
    model: str | None
    effort: str | None
    mode: str
    write_scope: str
    sandbox: str
    capabilities: tuple
    locks: tuple
    timeout_minutes: int
    report: str
    alt_reports: tuple
    notes: tuple
    sources: dict


def _apply_patch(values, patch, sources, source):
    if not isinstance(patch, dict):
        raise ConfigError("agents: expected a mapping")
    if set(patch) & {"mode", "report", "station", "version", "body", "prompt"}:
        raise ConfigError(REWRITE_ERROR)
    unknown = set(patch) - PATCH_FIELDS
    if unknown:
        raise ConfigError(f"unknown agent patch key: {', '.join(sorted(map(str, unknown)))}")
    _merge(values, patch, sources, source)


def resolve_agent(name, settings, registry, brief: dict | None = None, manager_app: str | None = None) -> AgentRun:
    if name not in registry:
        raise ConfigError(f"unknown agent: {name}")
    job = registry[name]
    if not job.ready:
        raise ConfigError(f"{name} has no consortium: block; it belongs to the old workflow")
    values = deepcopy(job.meta)
    values["notes"] = []
    sources = {key: job.origin for key in values}
    sources["name"] = job.origin
    layers = settings._layers
    if not layers:
        # Settings constructed directly still provide a usable single snapshot.
        layers = (("repo", settings.values),)
    brief_layer = {}
    for source, layer in layers:
        if source == "default":
            continue
        if source == "brief":
            brief_layer.update(layer)
            continue
        if "app" in layer:
            values["app"] = layer["app"]
            sources["app"] = source
        agents = layer.get("agents", {})
        if not isinstance(agents, dict):
            raise ConfigError("agents: expected a mapping")
        _apply_patch(values, agents.get(name, {}), sources, source)
    if brief is not None:
        if not isinstance(brief, dict):
            raise ConfigError("brief: expected a mapping")
        brief_layer.update(brief)
    for key in ("app", "tier", "model", "effort", "timeout_minutes", "report"):
        if key not in brief_layer:
            continue
        value = brief_layer[key]
        if key == "report" and value != job.meta["report"] and value not in job.meta["alt_reports"]:
            raise ConfigError(f"{name}.report: not listed in alt_reports")
        _merge(values, {key: value}, sources, "brief")
    for key, choices in (("app", APPS), ("tier", TIERS)):
        if not isinstance(values[key], str) or values[key] not in choices:
            raise ConfigError(f"{name}.{key}: invalid value")
    if manager_app is not None and manager_app not in {"claude", "codex"}:
        raise ConfigError("manager_app: expected claude or codex")
    if values["app"] == "either" and manager_app is not None:
        values["app"] = manager_app
    if type(values["timeout_minutes"]) is not int or values["timeout_minutes"] <= 0:
        raise ConfigError(f"{name}.timeout_minutes: expected a positive integer")
    for key in ("locks", "notes"):
        if not isinstance(values[key], list) or not all(isinstance(item, str) for item in values[key]):
            raise ConfigError(f"{name}.{key}: expected a list of strings")
    for key in ("model", "effort"):
        if key not in values:
            dotted = f"tiers.{values['tier']}.{values['app']}.{key}"
            values[key] = settings.get(dotted)
            sources[key] = settings.source(dotted)
        if values[key] is not None and not isinstance(values[key], str):
            raise ConfigError(f"{name}.{key}: expected a string")
    sandbox = "read-only" if values["mode"] == "read-only" and set(values["capabilities"]) <= {"read", "search"} else "danger-full-access"
    sources["sandbox"] = sources["mode"]
    fields = {key: values[key] for key in (
        "version", "app", "tier", "model", "effort", "mode", "write_scope", "timeout_minutes", "report",
    )}
    for key in ("capabilities", "locks", "alt_reports", "notes"):
        fields[key] = tuple(values[key])
    return AgentRun(name=name, sandbox=sandbox, sources={key: sources[key] for key in ("name", "sandbox", *fields)}, **fields)


def _notes_block(notes: tuple) -> str:
    return "## Notes from this repo\n" + "\n".join(f"- {note}" for note in notes) if notes else ""


AGENT_ONLY = ("Do this brief yourself. Dispatching agents, and the agent-recipes and team-dev-workflow skills, "
              "are the manager's: never use them unless your brief says to.")


def compose_prompt(job: JobDescription, run: AgentRun, brief_text: str) -> str:
    # A Codex agent sees the same plugin skills as its manager; dispatching stays the manager's.
    parts = [f"# You are the {run.name} agent (job description v{run.version})\n{AGENT_ONLY}", job.body.strip()]
    if run.notes:
        parts.append(_notes_block(run.notes))
    parts.append(f"## Your brief\n{brief_text}".rstrip())
    parts.append(
        f"## Your report\nEnd with one fenced `json` block holding a single object that matches `{run.report}`, "
        "with status, summary, decisions, evidence, changes, checks, questions and payload."
    )
    return "\n\n".join(parts)
