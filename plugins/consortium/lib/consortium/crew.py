"""Size a change's checks and keep missing agents visible as manager gates."""

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from consortium import paths
from consortium.cli import EXIT_FAIL, EXIT_OK, EXIT_USAGE
from consortium.config import ConfigError, Settings, glob_match, load_settings
from consortium.registry import JobDescription, load_registry


@dataclass(frozen=True)
class Change:
    files: list[str]
    added_lines: dict[str, list[str]]
    lines_changed: int
    new_files: list[str]


@dataclass(frozen=True)
class CrewItem:
    agent: str
    why: str


@dataclass(frozen=True)
class Crew:
    ceiling: str
    lines: int
    flags: list[tuple[str, str]]
    always: list[CrewItem]
    crew: list[CrewItem]
    gates: list[CrewItem]
    capped: list[CrewItem]


def change_from_files(files: list[str], lines: int | None) -> Change:
    """Describe predicted paths, without treating their existing contents as additions."""
    return Change(list(files), {}, lines if lines is not None else 0, [])


def _git_diff(repo: Path, rng: str, *options: str) -> str:
    if not rng or rng.startswith("-"):
        raise ConfigError("diff range must be a revision or revision range")
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotePath=false", "diff",
             "--no-ext-diff", "--no-textconv", "--no-color", *options, rng, "--"],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="surrogateescape",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise ConfigError(f"cannot read diff {rng}: {detail}") from error
    return result.stdout


def change_from_diff(repo: Path, rng: str) -> Change:
    """Read Git's counts, added lines and newly added files for the same range."""
    files, lines_changed = [], 0
    records = iter(_git_diff(repo, rng, "--numstat", "-z").split("\0"))
    for record in records:
        if not record:
            continue
        added, removed, file = record.split("\t", 2)
        if not file:  # With -z, a rename has separate old- and new-path records.
            next(records)
            file = next(records)
        files.append(file)
        if added != "-" and removed != "-":  # Binary changes have no line count.
            lines_changed += int(added) + int(removed)

    added_lines = {}
    file, in_hunk = None, False
    patch = _git_diff(repo, rng, "-U0", "--src-prefix=a/", "--dst-prefix=b/", "--submodule=short")
    for line in patch.split("\n"):
        if line.startswith("diff --git "):
            file, in_hunk = None, False
        elif not in_hunk and line.startswith("+++ "):
            # Git terminates unquoted paths containing spaces with a tab.
            # An actual tab in a filename is escaped inside a quoted header.
            header = line[4:].removesuffix("\t")
            if header.startswith('"'):
                header = ast.literal_eval(header)
            file = None if header == "/dev/null" else header[2:]
        elif line.startswith("@@ "):
            in_hunk = True
        elif in_hunk and file is not None and line.startswith("+"):
            added_lines.setdefault(file, []).append(line[1:])

    new_files = [file for file in _git_diff(repo, rng, "--name-only", "--diff-filter=A", "-z").split("\0") if file]
    return Change(files, added_lines, lines_changed, new_files)


def _risk_flags(change: Change, settings: Settings) -> list[tuple[str, str]]:
    risks, keywords = settings.get("risk", {}), settings.get("keywords", {})
    flags = []
    for flag in dict.fromkeys([*risks, *keywords]):
        evidence = next(
            (f"path: {file}" for file in change.files
             if any(glob_match(file, pattern) for pattern in risks.get(flag, []))),
            None,
        )
        if evidence is None:
            evidence = next(
                (f"keyword: {word} in {file}" for file, lines in change.added_lines.items()
                 for line in lines for word in keywords.get(flag, [])
                 if re.search(r"\b" + re.escape(word) + r"\b", line, re.IGNORECASE)),
                None,
            )
        if evidence is not None:
            flags.append((flag, evidence))
    return flags


def size_crew(
    change: Change,
    settings: Settings,
    registry: dict[str, JobDescription],
    *,
    implementers=1,
    dictated=False,
    hard_to_undo=False,
    new_api=False,
    ceiling=None,
) -> Crew:
    ceiling = settings.get("ceiling") if ceiling is None else ceiling
    if ceiling not in {"lean", "normal", "full"}:
        raise ConfigError("ceiling: expected lean, normal or full")
    flags = _risk_flags(change, settings)
    checks = {}

    def add(agent, why):
        checks.setdefault(agent, [])
        if why not in checks[agent]:
            checks[agent].append(why)

    if dictated:
        add("spec-gate", "dictated value")
    if implementers >= 2:
        add("spec-gate", f"{implementers} implementers")
    for flag, why in flags:
        agent = settings.get(f"crew.{flag}")
        if not agent:
            raise ConfigError(f"crew.{flag}: no check configured for risk flag")
        add(agent, f"{flag}: {why}")

    # Rules are independent: the 200-line minimum does not veto a risk, module,
    # API, dictated-value or multi-implementer check.
    threshold = settings.get("thresholds.code_reviewer_lines")
    if change.lines_changed > threshold:
        add("code-reviewer", f"more than {threshold} changed lines")
    for file in change.new_files:
        if Path(file).name in settings.get("module_markers", []):
            add("code-reviewer", f"new module: {file}")
    if new_api:
        add("code-reviewer", "new API requested")
    try:
        patterns = [re.compile(pattern) for pattern in settings.get("api_patterns", [])]
    except re.error as error:
        raise ConfigError(f"api_patterns: {error}") from error
    for file, lines in change.added_lines.items():
        if any(pattern.search(line) for line in lines for pattern in patterns):
            add("code-reviewer", f"new API: {file}")
    if hard_to_undo:
        add("bar-raiser", "hard to undo")
    if any(flag == "schema" for flag, _ in flags):
        add("bar-raiser", "schema change")
    if ceiling == "full":
        add("code-reviewer", "full ceiling")

    crew, gates, capped = [], [], []
    for agent, reasons in checks.items():
        why = "; ".join(reasons)
        job = registry.get(agent)
        if job is None or not job.ready:
            gates.append(CrewItem(agent, f"manager gate: {agent} is not available yet"))
        elif ceiling == "lean" and agent != "spec-gate":
            capped.append(CrewItem(agent, f"lean ceiling: {why}"))
        else:
            crew.append(CrewItem(agent, why))
    return Crew(
        ceiling, change.lines_changed, flags,
        [CrewItem("implementer", "its own tests"), CrewItem("ci-gate", "the full test, run by consortium gate")],
        crew, gates, capped,
    )


def _nonnegative(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a nonnegative integer") from error
    if number < 0:
        raise argparse.ArgumentTypeError("expected a nonnegative integer")
    return number


def _positive(value: str) -> int:
    number = _nonnegative(value)
    if number == 0:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("checks", help="size the crew for predicted files or a real diff")
    change = parser.add_mutually_exclusive_group(required=True)
    change.add_argument("--diff", metavar="RANGE")
    change.add_argument("--files", nargs="+", metavar="PATH")
    parser.add_argument("--lines", type=_nonnegative)
    parser.add_argument("--implementers", type=_positive, default=1)
    parser.add_argument("--dictated", action="store_true")
    parser.add_argument("--hard-to-undo", action="store_true")
    parser.add_argument("--new-api", action="store_true")
    parser.add_argument("--ceiling", choices=("lean", "normal", "full"))
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=_checks)


def _checks(args: argparse.Namespace) -> int:
    if args.diff is not None and args.lines is not None:
        print("--lines requires --files", file=sys.stderr)
        return EXIT_USAGE
    try:
        start = (args.repo or Path.cwd()).resolve()
        repo = paths.repo_root(start) or start
        settings = load_settings(repo)
        registry = load_registry(repo)
        change = change_from_diff(repo, args.diff) if args.diff is not None else change_from_files(args.files, args.lines)
        result = size_crew(
            change, settings, registry, implementers=args.implementers, dictated=args.dictated,
            hard_to_undo=args.hard_to_undo, new_api=args.new_api, ceiling=args.ceiling,
        )
        if args.json:
            print(json.dumps(asdict(result), indent=2))
        else:
            print(f"Ceiling: {result.ceiling}; changed lines: {result.lines}")
            for flag, why in result.flags:
                print(f"Flag {flag}: {why}")
            for group in ("always", "crew", "gates", "capped"):
                print(f"{group}:")
                for item in getattr(result, group):
                    print(f"  {item.agent}: {item.why}")
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK
