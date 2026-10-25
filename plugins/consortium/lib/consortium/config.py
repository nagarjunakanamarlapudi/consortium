"""Layered factory settings and the shared path-glob rule."""

import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from consortium import paths


class ConfigError(Exception):
    """A configuration or job description cannot be used."""


APPS = {"claude", "codex"}


def validate_apps(value) -> None:
    if (not isinstance(value, list) or not value or
            not all(isinstance(item, str) and item in APPS for item in value) or len(set(value)) != len(value)):
        raise ConfigError(f"apps: expected a non-empty list of distinct supported apps {sorted(APPS)}, got {value!r}")


def allowed_apps(value, apps, key="app") -> tuple:
    if value == "all":
        return tuple(apps)
    if (isinstance(value, list) and value and
            all(isinstance(item, str) and item in apps for item in value) and len(set(value)) == len(value)):
        return tuple(value)
    names = sorted(apps) if isinstance(apps, set) else list(apps)
    example = "codex" if "codex" in names else names[0]
    message = f"{key}: expected 'all' or a non-empty list of distinct names from apps {names}, e.g. [{example}]; got {value!r}"
    if value == "either":
        message += "; 'either' is now 'all'"
    elif isinstance(value, str) and value in APPS:
        message += f"; write {value!r} as a one-item list: [{value}]"
    raise ConfigError(message)


# A brief's front matter also names its agent, worktree, dictated values and device, and carries the per-agent fields
# that resolve_agent takes as its brief argument. Of its keys, only these are global settings.
BRIEF_SETTINGS = ("app",)


@dataclass(frozen=True)
class Settings:
    values: dict
    sources: dict[str, str]
    # Keep the snapshot's layers: agent resolution interleaves global app
    # choices with per-agent patches, which a merged dictionary cannot express.
    _layers: tuple = field(default=(), init=False, repr=False, compare=False)

    def get(self, dotted: str, default=None):
        value = self.values
        for key in dotted.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def source(self, dotted: str) -> str:
        return self.sources.get(dotted, "")


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ConfigError(f"cannot read settings from {path}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping")
    return data


def _same_kind(previous, incoming) -> bool:
    if type(previous) is type(incoming) or {type(previous), type(incoming)} <= {int, float}:
        return True
    # Symbolic defaults may be replaced by lists, and a later layer may put them back.
    return any(word in (previous, incoming) for word in ("auto", "all")) and all(
        isinstance(value, (str, list)) for value in (previous, incoming))


def _merge(values: dict, patch: dict, sources: dict, source: str, prefix: str = "") -> None:
    for key, incoming in patch.items():
        if not isinstance(key, str):
            raise ConfigError(f"{prefix or 'settings'}: keys must be strings")
        dotted = f"{prefix}.{key}" if prefix else key
        present = key in values
        previous = values.get(key)
        app_setting = key == "app" and (not prefix or prefix.startswith("agents."))
        if app_setting and not (isinstance(incoming, list) and any(
                isinstance(item, str) and item.startswith("+") for item in incoming)):
            allowed_apps(incoming, APPS, dotted)
        if key == "apps" and not prefix and not isinstance(incoming, list):
            validate_apps(incoming)
        if present and previous is not None and not _same_kind(previous, incoming):
            raise ConfigError(f"{dotted}: expected {type(previous).__name__}")
        if isinstance(incoming, dict):
            if not present or previous is None:
                values[key] = {}
            if incoming:
                sources.pop(dotted, None)
                _merge(values[key], incoming, sources, source, dotted)
            elif not values[key]:
                sources[dotted] = source
            continue
        if isinstance(incoming, list):
            plus = [isinstance(item, str) and item.startswith("+") for item in incoming]
            if any(plus) and not all(plus):
                raise ConfigError(f"{dotted}: cannot mix '+' and plain list items")
            if incoming and all(plus):
                if previous is not None and not isinstance(previous, list):
                    raise ConfigError(f"{dotted}: '+' items need a list to add to, not {previous!r}")
                values[key] = deepcopy(previous or []) + [item[1:] for item in incoming]
                if app_setting:
                    allowed_apps(values[key], APPS, dotted)
                earlier = sources.get(dotted)
                sources[dotted] = f"{earlier}+{source}" if earlier else source
                continue
        values[key] = deepcopy(incoming)
        sources[dotted] = source


def load_settings(repo: Path | None, brief: dict | None = None) -> Settings:
    layers = [("default", _read_yaml(paths.package_root() / "defaults.yaml"))]
    user_file = paths.state_home() / "config.yaml"
    if user_file.exists():
        layers.append(("user", _read_yaml(user_file)))
    if repo is not None:
        repo_file = paths.repo_config_dir(repo) / "config.yaml"
        if repo_file.exists():
            layers.append(("repo", _read_yaml(repo_file)))
    if brief is not None:
        if not isinstance(brief, dict):
            raise ConfigError("brief: expected a mapping")
        layers.append(("brief", {key: deepcopy(brief[key]) for key in BRIEF_SETTINGS if key in brief}))
    values, sources = {}, {}
    for source, patch in layers:
        _merge(values, patch, sources, source)
        validate_apps(values.get("apps"))
        allowed_apps(values.get("app"), values["apps"])
        agents = values.get("agents", {})
        if isinstance(agents, dict):
            for name, agent in agents.items():
                if isinstance(agent, dict) and "app" in agent:
                    allowed_apps(agent["app"], values["apps"], f"agents.{name}.app")
    settings = Settings(values, sources)
    object.__setattr__(settings, "_layers", tuple(layers))
    return settings


def glob_match(path: str, pattern: str) -> bool:
    """Match repo-relative paths; single stars never cross a slash."""
    translated = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            translated.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            translated.append(".*")
            index += 2
        elif pattern[index] == "*":
            translated.append("[^/]*")
            index += 1
        else:
            translated.append(re.escape(pattern[index]))
            index += 1
    return re.fullmatch("".join(translated), path) is not None
