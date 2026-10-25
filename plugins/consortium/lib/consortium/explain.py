"""Show effective settings, an agent, or its composed prompt."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from consortium import paths
from consortium.cli import EXIT_FAIL, EXIT_OK
from consortium.config import APPS, ConfigError, load_settings
from consortium.registry import _notes_block, compose_prompt, load_registry, parse_front_matter, resolve_agent


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("explain", help="show effective settings and their sources")
    parser.add_argument("agent", nargs="?")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--prompt", action="store_true")
    output.add_argument("--notes", action="store_true")
    parser.add_argument("--all", action="store_true", help="show every setting")
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--manager", choices=sorted(APPS))
    parser.set_defaults(func=_explain)


def _leaves(values, prefix=""):
    for key, value in values.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            yield from _leaves(value, dotted)
        else:
            yield dotted, value


def _short_paths(value, repo):
    if isinstance(value, str) and Path(value).is_absolute():
        return _path_text(value, repo)
    if isinstance(value, list):
        return [_short_paths(item, repo) for item in value]
    return value


def _value_text(value, repo=None):
    value = _short_paths(value, repo)
    if not isinstance(value, str):
        value = yaml.safe_dump(value, default_flow_style=True, width=10000).removesuffix("...\n").strip()
    return value.replace("\n", r"\n")


def _source_details(source, dotted, repo, settings, job=None, run=None, brief_path=None):
    if dotted == "allowed_apps":
        dotted = "app"
    layers = source.split("+")
    for index, layer in enumerate(layers):
        patch = next((data for origin, data in settings._layers if origin == layer), {})
        agent_patch = patch.get("agents", {}).get(job.name, {}) if job else {}
        configured = dotted in agent_patch or (dotted == "app" and "app" in patch)
        if run is not None and dotted in {"model", "effort"}:
            configured = configured or settings.source(f"tiers.{run.tier}.{run.app}.{dotted}") == layer
        if layer == "default":
            location = paths.package_root() / "defaults.yaml"
            label = "default"
            if run is not None and dotted in {"model", "effort"}:
                key = f"tiers.{run.tier}.{run.app}.{dotted}"
            else:
                key = dotted
        # Each config layer occurs once. A repeated "repo" starts with the
        # repo-only job's list and ends with that repo's appended patch.
        elif job is not None and layer == job.origin and (not configured or layer in layers[index + 1:]):
            location, label = job.path, layer
            key = "name" if dotted == "name" else f"consortium.{'mode' if dotted == 'sandbox' else dotted}"
        elif layer in {"user", "repo"}:
            location = paths.state_home() / "config.yaml" if layer == "user" else paths.repo_config_dir(repo) / "config.yaml"
            label = "you" if layer == "user" else "repo"
            key = dotted
            if job is not None:
                # Look at the original layer so global app and tier mappings
                # retain their actual setting paths in the explanation.
                if dotted == "app" and dotted not in patch.get("agents", {}).get(job.name, {}):
                    key = "app"
                elif dotted in {"model", "effort"} and dotted not in patch.get("agents", {}).get(job.name, {}):
                    key = f"tiers.{run.tier}.{run.app}.{dotted}"
                else:
                    key = f"agents.{job.name}.{dotted}"
        elif layer == "brief":
            location, label, key = brief_path, "brief", dotted
        else:
            location, label, key = None, layer or "unresolved", dotted
        yield label, location, key


def _path_text(path, repo, plugin=True):
    path = Path(path).resolve()
    if plugin and path.is_relative_to(paths.package_root()):
        return str(Path("<plugin>") / path.relative_to(paths.package_root()))
    if repo is not None and path.is_relative_to(repo):
        return str(path.relative_to(repo))
    home = Path.home().resolve()
    if path.is_relative_to(home):
        return str(Path("~") / path.relative_to(home))
    return str(path)


def _manager_text(manager):
    if manager is None:
        return "as seen with no manager"
    app = "Claude Code" if manager == "claude" else "Codex"
    return f"as a {app} manager sees them"


def _table(rows):
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        print("  " + "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


def _layer_label(source):
    return " + ".join("you" if layer == "user" else layer for layer in source.split("+"))


def _layers(repo, settings, brief, brief_path):
    patches = dict(settings._layers)
    layers = [
        ("default", paths.package_root() / "defaults.yaml", patches["default"]),
        ("you", paths.state_home() / "config.yaml", patches.get("user")),
        ("repo", paths.repo_config_dir(repo) / "config.yaml" if repo is not None else None, patches.get("repo")),
    ]
    if brief_path is not None:
        patch = {key: brief[key] for key in ("app", "tier", "model", "effort", "timeout_minutes", "report") if key in brief}
        layers.append(("brief", brief_path, patch))
    return layers


def _print_layers(layers, repo):
    print("\nLayers, a later one winning")
    rows = []
    for label, path, patch in layers:
        count = len(list(_leaves(patch))) if patch is not None else 0
        status = f"{count} setting{'s' if count != 1 else ''}" if patch is not None else "no file"
        rows.append((label, _path_text(path, repo) if path is not None else "not in a repository",
                     "" if label == "default" or path is None else status))
    _table(rows)


def _agent_value(field, value, repo):
    if field == "timeout_minutes":
        return f"{value} min"
    if isinstance(value, (list, tuple)):
        return ", ".join(_value_text(item, repo) for item in value) if value else "none"
    return "none" if value is None else _value_text(value, repo)


def _marked_value(field, run, job, repo, settings, brief_path):
    value = _agent_value(field, getattr(run, field), repo)
    markers = [label for label, location, key in _source_details(
        run.sources[field], field, repo, settings, job, run, brief_path)
        if label in {"you", "repo", "brief"} and location != job.path]
    return f"{value} ({markers[-1]})" if markers else value


def _print_agents(repo, settings, brief, manager, brief_path):
    registry = load_registry(repo)
    print("\nAgents")
    rows = [("agent", "mode", "app", "tier", "model", "effort", "timeout")]
    old = []
    for name, job in sorted(registry.items()):
        if not job.ready:
            old.append(name)
            continue
        label = f"{name} (repo agent)" if job.origin == "repo" else name
        try:
            run = resolve_agent(name, settings, registry, brief, manager)
            cells = [_marked_value(field, run, job, repo, settings, brief_path) for field in ("app", "tier", "model", "effort")]
            rows.append((label, run.mode, *cells, _agent_value("timeout_minutes", run.timeout_minutes, repo)))
        except ConfigError as error:
            rows.append((label, f"error: {error}", "", "", "", "", ""))
    _table(rows)
    print("(you), (repo) and (brief) mark a value your file, this repo or the brief set; unmarked values are defaults or job descriptions.")
    if old:
        print(f"Old workflow, not shown: {', '.join(old)}")


def _print_footer(repo):
    print(f"\n<plugin> = {_path_text(paths.package_root(), repo, plugin=False)}")


def _settings_text(args, repo, settings, brief):
    place = f"in {_path_text(repo, None, plugin=False)}" if repo is not None else "with no repository"
    print(f"Consortium settings {place}, {_manager_text(args.manager)}")
    layers = _layers(repo, settings, brief, args.brief)
    _print_layers(layers, repo)
    if args.all:
        print("\nSettings")
        _table([(dotted, _layer_label(settings.source(dotted)), _value_text(value, repo)) for dotted, value in _leaves(settings.values)])
    else:
        _print_agents(repo, settings, brief, args.manager, args.brief)
        headings = {"you": "you", "repo": "this repo", "brief": "this brief"}
        for label, path, patch in layers[1:]:
            if patch:
                print(f"\nSet by {headings[label]}, in {_path_text(path, repo)}")
                _table([(dotted, _value_text(value, repo)) for dotted, value in _leaves(patch)])
    _print_footer(repo)
    if not args.all:
        print("Every setting: consortium explain --all. One agent in full: consortium explain <agent>.")


def _agent_text(args, repo, settings, job, run):
    origin = "plugin" if job.origin == "plugin" else "repo-only"
    print(f"{run.name}: a {origin} agent, {run.mode}, {_manager_text(args.manager)}\n")
    rows = []
    for field in ("app", "allowed_apps", "tier", "model", "effort", "mode", "sandbox", "write_scope", "capabilities",
                  "locks", "timeout_minutes", "report", "alt_reports", "version", "notes"):
        details = list(_source_details(run.sources[field], field, repo, settings, job, run, args.brief))
        labels = " + ".join(label for label, location, key in details)
        locations = " + ".join(f"{_path_text(location, repo)}: {key}" for label, location, key in details if location is not None)
        label = "timeout" if field == "timeout_minutes" else field.replace("_", " ")
        value = "" if field == "notes" and run.notes else _agent_value(field, getattr(run, field), repo)
        rows.append((label, value, labels, locations))
    _table(rows)
    for note in run.notes:
        for line in note.splitlines():
            print(f"    {line}")
    _print_footer(repo)


def _explain(args: argparse.Namespace) -> int:
    try:
        if args.all and (args.agent is not None or args.prompt or args.notes):
            raise ConfigError("--all cannot be used with an agent, --prompt or --notes")
        repo = paths.repo_root(args.repo or Path.cwd())
        if args.repo is not None and repo is None:
            raise ConfigError(f"not a git repository: {args.repo}")
        brief, brief_text = {}, ""
        if args.brief is not None:
            try:
                brief, brief_text = parse_front_matter(args.brief.read_text())
            except (OSError, UnicodeError) as error:
                raise ConfigError(f"cannot read brief: {args.brief}") from error
        settings = load_settings(repo, brief)
        if args.agent is None:
            if args.prompt or args.notes:
                raise ConfigError("--prompt and --notes require an agent")
            if args.json:
                print(json.dumps({"values": settings.values, "sources": settings.sources}, indent=2))
            else:
                _settings_text(args, repo, settings, brief)
        else:
            registry = load_registry(repo)
            run = resolve_agent(args.agent, settings, registry, brief, args.manager)
            job = registry[args.agent]
            if args.json:
                print(json.dumps(asdict(run), indent=2))
            elif args.prompt:
                print(compose_prompt(job, run, brief_text))
            elif args.notes:
                block = _notes_block(run.notes)
                if block:
                    print(block)
            else:
                _agent_text(args, repo, settings, job, run)
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK
