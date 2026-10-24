"""Parse and check task briefs before an agent is started."""

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from consortium import paths
from consortium.cli import EXIT_FAIL, EXIT_OK, EXIT_USAGE
from consortium.config import ConfigError, Settings, load_settings
from consortium.registry import JobDescription, load_registry, parse_front_matter, resolve_agent


@dataclass(frozen=True)
class Brief:
    front: dict
    sections: dict[str, str]
    text: str


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str


def parse_brief(text: str) -> Brief:
    front, body = parse_front_matter(text)
    sections = {}
    current = None
    fence = None
    for line in body.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            delimiter = marker[1]
            if fence is None:
                fence = delimiter
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence):
                fence = None
        heading = re.match(r"^##\s+(.+?)\s*$", line) if fence is None and not marker else None
        if heading:
            current = heading[1].strip().removesuffix(":").strip().lower()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return Brief(front, {key: "\n".join(lines).strip() for key, lines in sections.items()}, text)


def scope_entries(brief: Brief) -> list[str]:
    """Read every backticked Scope entry, including create/gone and globs."""
    return re.findall(r"`([^`]+)`", brief.sections.get("scope", ""))


def in_scope(path: str, entries: list[str], root: Path) -> bool:
    """Match an exact path, a folder's descendants, or a shared-rule glob."""
    from consortium.config import glob_match

    root = root.resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        return False
    relative = candidate.relative_to(root).as_posix()
    for entry in entries:
        target = (root / entry).resolve()
        if not target.is_relative_to(root):
            continue
        if "*" in entry:
            pattern = target.relative_to(root).as_posix()
            if glob_match(relative, pattern):
                return True
        elif candidate == target:
            return True
        elif (entry.endswith("/") or target.is_dir()) and candidate.is_relative_to(target):
            return True
    return False


_EXTENSIONS = (".py", ".dart", ".ts", ".tsx", ".js", ".sql", ".yaml", ".yml", ".json", ".md",
               ".sh", ".swift", ".kt", ".gradle", ".toml")
_LINE_SUFFIX = re.compile(r":(\d+)(?:-(\d+))?$")
_LIST_MARKER = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
# Flags that make a search start another program; a brief's search is never rerun with one.
_EXEC_FLAGS = ("--pre", "--open-files-in-pager", "-O")


def _without_marker(line: str) -> str:
    return _LIST_MARKER.sub("", line).strip()


def _path_candidates(text: str, *, created: bool = False):
    for line in text.splitlines():
        if not created and re.match(r"^(create|gone):", _without_marker(line), re.IGNORECASE):
            continue
        for match in re.finditer(r"`([^`\s]+)`", line):
            value = match[1]
            if value.startswith(("http", "~", "$", "-")) or any(char in value for char in "*?{}<>|;"):
                continue
            path = _LINE_SUFFIX.sub("", value)
            if "/" in path or path.endswith(_EXTENSIONS):
                yield value, path


def _bullets(text: str):
    current = None
    for line in text.splitlines():
        if _LIST_MARKER.match(line):
            if current is not None:
                yield current
            current = _without_marker(line)
        elif current is not None:
            current += " " + line.strip()
    if current is not None:
        yield current.strip()


def _cited(bullet: str, root: Path) -> bool:
    for match in re.finditer(r"([^\s`]+):(\d+)(?:-(\d+))?(?![\d-])", bullet):
        path, start, end = match.groups()
        try:
            count = len((root / path).read_text().splitlines())
        except (OSError, UnicodeError):
            continue
        if 1 <= int(start) <= int(end or start) <= count:
            return True
    return False


def _auto_checks(language: str, repo: Path) -> list[str]:
    if language == "python":
        makefile = repo / "Makefile"
        lint = makefile.is_file() and any(
            "lint" in match[1].split()
            for match in re.finditer(r"^([^\s#:=][^:=\n]*):(?!=)", makefile.read_text(), re.MULTILINE)
        )
        return ["make lint" if lint else "ruff check .", "pytest {tests}"]
    if language == "dart":
        pubspec = repo / "pubspec.yaml"
        data = yaml.safe_load(pubspec.read_text()) if pubspec.is_file() else {}
        flutter = isinstance(data, dict) and any(
            "flutter" in (data.get(key) or {}) for key in ("dependencies", "dev_dependencies")
        )
        tool = "flutter" if flutter else "dart"
        return [f"{tool} analyze", f"{tool} test {{tests}}"]
    if language == "javascript":
        package = repo / "package.json"
        data = json.loads(package.read_text()) if package.is_file() else {}
        return (["npm run lint"] if "lint" in data.get("scripts", {}) else []) + ["npm test -- {tests}"]
    raise ConfigError(f"checks.{language}: no auto checks for this language")


def _has_command(text: str, command: str) -> bool:
    parts = command.split("{tests}")
    pattern = ""
    for index, part in enumerate(parts):
        if index:
            pattern += r"[^`\n]+?"
        pattern += re.escape(part).replace(r"\ ", r"[^\S\n]+")
    return re.search(r"(?<![\w-])" + pattern + r"(?![\w-])", text) is not None


def _test_findings(tests: str, root: Path, settings: Settings) -> list[Finding]:
    if re.fullmatch(r"none — \S[^\n]*", tests.strip()):
        return []
    found = re.findall(r"^\s*(?:[-+*]\s+)?found by:\s*(.+)$", tests, re.MULTILINE | re.IGNORECASE)
    if not found:
        return [Finding("tests-complete", "Tests needs a found by: line or none — <reason>")]
    listed = {(root / path).resolve() for _, path in _path_candidates(tests)}
    findings = []
    for line in found:
        commands = re.findall(r"`([^`]+)`", line) or [line.strip()]
        for command in commands:
            if not any(re.search(pattern, command) for pattern in settings.get("brief.search_commands", [])):
                continue
            try:
                # Execute an argument vector: a brief cannot append shell operations to a search.
                argv = shlex.split(command)
                if any(token.startswith(_EXEC_FLAGS) for token in argv[1:]):
                    raise ValueError("search would start another program")
                result = subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL,
                                        capture_output=True, text=True, timeout=10)
                if result.returncode not in (0, 1):
                    raise ValueError("search failed")
            except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
                findings.append(Finding("tests-complete", f"could not rerun: {command}"))
                continue
            for output in result.stdout.splitlines():
                # Both filename-only searches and file:line:match output identify the file.
                name = output.split(":", 1)[0]
                candidate = (root / name).resolve()
                if candidate.is_file() and candidate not in listed:
                    finding = Finding("tests-complete", f"Tests does not list {name}")
                    if finding not in findings:
                        findings.append(finding)
    return findings


def check_brief(brief: Brief, job: JobDescription, mode: str, repo: Path, settings: Settings) -> list[Finding]:
    sections = brief.sections
    worktree = brief.front.get("worktree")
    if worktree is not None and (not isinstance(worktree, str) or not worktree):
        raise ConfigError("worktree: expected a nonempty path")
    root = Path(worktree).expanduser() if worktree else repo
    findings = []

    for section in settings.get(f"brief.sections.{mode}", []):
        if not sections.get(section.lower(), "").strip():
            findings.append(Finding("structure", f"missing or empty section: {section}"))
    report = sections.get("report", "")
    schemas = [job.meta["report"], *job.meta["alt_reports"]]
    # "none" is a report with no payload, so there is no schema for the section to name.
    if report.strip() and "none" not in schemas and not any(
        re.search(r"(?<![\w.-])" + re.escape(schema) + r"(?![\w-]|\.[\w-])", report)
        for schema in schemas
    ):
        findings.append(Finding("structure", "Report must name " + " or ".join(schemas)))

    for value, path in dict(_path_candidates(brief.text)).items():
        if not (root / path).exists():
            findings.append(Finding("paths-exist", f"path does not exist: {value}"))

    for bullet in _bullets(sections.get("premises", "")):
        if bullet != "none" and not _cited(bullet, root):
            findings.append(Finding("premises-cited", f"premise needs an existing path:line in range: {bullet}"))

    numbers = "|".join(re.escape(word) for word in settings.get("brief.word_numbers", []))
    count = r"\b(?:exactly|expect|must be|\d+" + ("|" + numbers if numbers else "") + r")\b"
    for line in brief.text.splitlines():
        if (re.search(count, line, re.IGNORECASE)
                and re.search(r"\b(?:stop|halt|abort|different number)\b", line, re.IGNORECASE)
                and not re.search(r"\b(?:about|roughly|approximately)\b|~", line, re.IGNORECASE)):
            findings.append(Finding("no-exact-count-stop", f"exact count used with a stop signal: {line.strip()}"))

    # A file the task creates or deletes still brings its language's checks.
    scope = [path for _, path in _path_candidates(sections.get("scope", ""), created=True)]
    for language, extensions in settings.get("languages", {}).items():
        if not any(Path(path).suffix in extensions for path in scope):
            continue
        commands = settings.get(f"checks.{language}", [])
        if commands == "auto":
            commands = _auto_checks(language, repo)
        if isinstance(commands, str):
            commands = [commands]
        for command in commands:
            if not _has_command(sections.get("done means", ""), command):
                findings.append(Finding("checks-per-language", f"Done means needs {language} check: {command}"))

    if sections.get("tests", "").strip():
        findings.extend(_test_findings(sections["tests"], root, settings))

    dictated = brief.front.get("dictated", [])
    if not isinstance(dictated, list) or not all(isinstance(value, str) for value in dictated):
        raise ConfigError("dictated: expected a list of strings")
    for value in dictated:
        if value not in sections.get("do not change", ""):
            findings.append(Finding("dictated-verbatim", f"Do not change must include verbatim: {value}"))

    if mode in {"worktree-write", "operate"}:
        for word in ("commit", "push"):
            if not re.search(r"\b" + word + r"\b", sections.get("forbidden", ""), re.IGNORECASE):
                findings.append(Finding("forbidden-and-stop", f"Forbidden must name {word}"))
        if not re.search(r"\bNEEDS_CONTEXT\b", sections.get("stop when", "")):
            findings.append(Finding("forbidden-and-stop", "Stop when must name NEEDS_CONTEXT"))

    for pattern in settings.get("brief.raw_commands", []):
        if re.search(pattern, brief.text):
            findings.append(Finding("locks-and-devices", f"raw command matches forbidden pattern: {pattern}"))
    if "device" in job.meta["capabilities"] and not brief.front.get("device"):
        findings.append(Finding("locks-and-devices", "device capability needs device: in front matter"))
    return findings


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("brief-check", help="check an agent brief before dispatch")
    parser.add_argument("file", metavar="FILE|-")
    parser.add_argument("--agent")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=_brief_check)


def _brief_check(args: argparse.Namespace) -> int:
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
        brief = parse_brief(text)
        repo = args.repo if args.repo is not None else paths.repo_root(Path.cwd())
        if repo is None:
            raise ConfigError("brief-check needs --repo outside a git repository")
        name = args.agent or brief.front.get("agent")
        if not isinstance(name, str) or not name:
            raise ConfigError("brief-check needs --agent or agent: in front matter")
        settings = load_settings(repo, brief.front)
        registry = load_registry(repo)
        run = resolve_agent(name, settings, registry, brief=brief.front)
        findings = check_brief(brief, registry[name], run.mode, repo, settings)
    except (ConfigError, OSError, UnicodeError, yaml.YAMLError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_USAGE
    if args.json:
        print(json.dumps([asdict(finding) for finding in findings]))
    else:
        for finding in findings:
            print(f"{finding.rule}: {finding.message}")
    return EXIT_FAIL if findings else EXIT_OK
