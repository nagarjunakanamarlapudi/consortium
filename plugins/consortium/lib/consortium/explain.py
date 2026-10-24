"""Show effective settings, an agent, or its composed prompt."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from consortium import paths
from consortium.cli import EXIT_FAIL, EXIT_OK
from consortium.config import ConfigError, load_settings
from consortium.registry import _notes_block, compose_prompt, load_registry, parse_front_matter, resolve_agent


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("explain", help="show effective settings and their sources")
    parser.add_argument("agent", nargs="?")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--prompt", action="store_true")
    output.add_argument("--notes", action="store_true")
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--manager", choices=("claude", "codex"))
    parser.set_defaults(func=_explain)


def _leaves(values, prefix=""):
    for key, value in values.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            yield from _leaves(value, dotted)
        else:
            yield dotted, value


def _value_text(value):
    if isinstance(value, str):
        return value
    return yaml.safe_dump(value, default_flow_style=True, width=10000).removesuffix("...\n").strip()


def _source_text(source, dotted, repo, settings, job=None, run=None):
    descriptions = []
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
            descriptions.append(f"brief ({dotted})")
            continue
        else:
            descriptions.append(layer or "unresolved")
            continue
        descriptions.append(f"{label} ({location}: {key})")
    return " + ".join(descriptions)


def _explain(args: argparse.Namespace) -> int:
    try:
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
                for dotted, value in _leaves(settings.values):
                    print(f"{dotted}: {_value_text(value)}  <- {_source_text(settings.source(dotted), dotted, repo, settings)}")
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
                for dotted, value in asdict(run).items():
                    if dotted != "sources":
                        source = _source_text(run.sources[dotted], dotted, repo, settings, job, run)
                        print(f"{dotted}: {_value_text(value)}  <- {source}")
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK
