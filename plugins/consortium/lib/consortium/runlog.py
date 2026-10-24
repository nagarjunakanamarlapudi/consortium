"""Locked JSONL run history, verdicts, token accounting and the runs command."""

import argparse
import fcntl
import json
import math
import re
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from consortium.cli import EXIT_FAIL, EXIT_OK
from consortium.paths import state_home


RUN_FIELDS = (
    "id",
    "agent",
    "jd_version",
    "app",
    "model",
    "effort",
    "tier",
    "repo",
    "worktree",
    "branch",
    "started",
    "ended",
    "minutes",
    "status",
    "error",
    "locks",
    "tokens",
    "report",
    "scope_ok",
    "manager",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def new_run_id(agent: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", agent):
        raise ValueError("agent must be a single path component")
    return f"{_now():%Y%m%d-%H%M%S}-{agent}-{uuid.uuid4().hex[:4]}"


def run_dir(run_id) -> Path:
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", run_id):
        raise ValueError("run id must be a single path component")
    folder = state_home() / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@contextmanager
def _locked_log(mode, lock):
    with (state_home() / "runs.jsonl").open(mode, encoding="utf-8") as stream:
        fcntl.flock(stream, lock)
        try:
            yield stream
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _json_objects(lines):
    for line in lines:
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue  # An interrupted event stream may end with an incomplete line.
        if isinstance(value, dict):
            yield value


def _write_record(stream, record):
    line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
    stream.seek(0, 2)
    stream.write(line)
    stream.flush()  # Flush while still holding the lock, including for large records.


def append(record: dict) -> None:
    with _locked_log("a+", fcntl.LOCK_EX) as stream:
        _write_record(stream, record)


def record_run(**fields) -> dict:
    """Record a finished run once, atomically returning an earlier record on retry."""
    if not isinstance(fields.get("id"), str) or not fields["id"]:
        raise ValueError("a run requires an id")
    with _locked_log("a+", fcntl.LOCK_EX) as stream:
        stream.seek(0)
        for existing in _json_objects(stream):
            if existing.get("type") == "run" and existing.get("id") == fields["id"]:
                return existing
        record = {"v": 1, "type": "run", **{key: fields.get(key) for key in RUN_FIELDS}}
        _write_record(stream, record)
        return record


def record_verdict(run_id: str, kept: bool, note: str | None):
    append({"v": 1, "type": "verdict", "id": run_id, "kept": kept, "note": note, "at": _timestamp()})


def _recent(record, cutoff):
    timestamp = record.get("at") if record.get("type") == "verdict" else record.get("started") or record.get("ended")
    if not isinstance(timestamp, str):
        return False
    try:
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    return when.tzinfo is not None and when >= cutoff


def read_records(days: int | None = None) -> list[dict]:
    try:
        with _locked_log("r", fcntl.LOCK_SH) as stream:
            records = list(_json_objects(stream))
    except FileNotFoundError:
        return []
    if days is None:
        return records
    cutoff = _now() - timedelta(days=days)
    return [record for record in records if _recent(record, cutoff)]


def summary(records, days: int) -> list[dict]:
    """Group recent runs, applying the last recorded verdict for each run id."""
    records = list(records)
    verdicts = {record["id"]: record["kept"] for record in records if record.get("type") == "verdict"}
    cutoff = _now() - timedelta(days=days)
    groups = {}
    for record in records:
        if record.get("type") != "run" or not _recent(record, cutoff):
            continue
        key = (record.get("agent"), record.get("tier"))
        row = groups.setdefault(
            key,
            {
                "agent": key[0],
                "tier": key[1],
                "runs": 0,
                "kept": 0,
                "dropped": 0,
                "minutes": 0,
                "tokens_in": 0,
                "tokens_out": 0,
            },
        )
        row["runs"] += 1
        verdict = verdicts.get(record["id"])
        row["kept"] += verdict is True
        row["dropped"] += verdict is False
        row["minutes"] += record.get("minutes") or 0
        tokens = record.get("tokens") or {}
        row["tokens_in"] += tokens.get("input") or 0
        row["tokens_out"] += tokens.get("output") or 0
    return [groups[key] for key in sorted(groups, key=lambda key: tuple(value or "" for value in key))]


def _usage_blocks(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "usage" and isinstance(child, dict):
                yield child
            yield from _usage_blocks(child)
    elif isinstance(value, list):
        for child in value:
            yield from _usage_blocks(child)


def tokens_from_codex_events(lines) -> dict | None:
    totals = None
    if isinstance(lines, str):
        lines = lines.splitlines()
    for event in _json_objects(lines):
        if not str(event.get("type", "")).endswith("completed"):
            continue
        for usage in _usage_blocks(event):
            if totals is None:
                totals = {"input": 0, "cached_input": 0, "output": 0}
            for target, source in (
                ("input", "input_tokens"),
                ("cached_input", "cached_input_tokens"),
                ("output", "output_tokens"),
            ):
                totals[target] += usage.get(source) or 0
    return totals


def tokens_from_claude_transcript(path: Path) -> tuple[dict | None, str | None]:
    # Claude Code writes a message as one line per content block and repeats its usage on each line, so each message
    # id counts once. Input includes cache reads and writes, which is what Codex's input_tokens counts.
    usages, model = {}, None
    try:
        with path.open(encoding="utf-8") as stream:
            for index, event in enumerate(_json_objects(stream)):
                message = event.get("message")
                if event.get("type") != "assistant" or not isinstance(message, dict):
                    continue
                if isinstance(message.get("model"), str) and not message["model"].startswith("<"):
                    model = message["model"]  # "<synthetic>" marks a message no model wrote
                if isinstance(message.get("usage"), dict):
                    usages[message.get("id") or index] = message["usage"]
    except FileNotFoundError:
        return None, None
    if not usages:
        return None, model
    totals = {"input": 0, "cached_input": 0, "output": 0}
    for usage in usages.values():
        cached = usage.get("cache_read_input_tokens") or 0
        totals["input"] += (usage.get("input_tokens") or 0) + cached + (usage.get("cache_creation_input_tokens") or 0)
        totals["cached_input"] += cached
        totals["output"] += usage.get("output_tokens") or 0
    return totals, model


def _nonnegative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def _nonnegative_minutes(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return number


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("runs", help="show run history, summaries and review verdicts")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--summary", action="store_true")
    action.add_argument("--verdict", nargs=2, metavar=("ID", "VERDICT"))
    action.add_argument("--wait", metavar="ID")
    parser.add_argument("--last", type=_nonnegative_int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--days", type=_nonnegative_int, default=7)
    parser.add_argument("--note")
    parser.add_argument("--timeout", type=_nonnegative_minutes, metavar="MIN")
    parser.set_defaults(func=_runs)


def _wait(run_id, timeout):
    deadline = None if timeout is None else time.monotonic() + timeout * 60
    while True:
        for record in read_records():
            if record.get("type") == "run" and record.get("id") == run_id:
                print(json.dumps(record))
                return EXIT_OK
        if deadline is not None and time.monotonic() >= deadline:
            print(f"still running: {run_id}", file=sys.stderr)
            return EXIT_FAIL
        delay = 2 if deadline is None else min(2, max(0, deadline - time.monotonic()))
        time.sleep(delay)


def _runs(args: argparse.Namespace) -> int:
    if args.verdict:
        run_id, verdict = args.verdict
        if verdict not in {"kept", "dropped"}:
            print("verdict must be kept or dropped", file=sys.stderr)
            return EXIT_FAIL
        record_verdict(run_id, verdict == "kept", args.note)
        return EXIT_OK
    if args.wait is not None:
        return _wait(args.wait, args.timeout)
    records = read_records()
    if args.summary:
        rows = summary(records, args.days)
    else:
        rows = [record for record in records if record.get("type") == "run"]
        if args.last is not None:
            rows = rows[-args.last :] if args.last else []
    if args.json:
        print(json.dumps(rows, indent=2))
    elif args.summary:
        print("agent\ttier\truns\tkept\tdropped\tminutes\ttokens_in\ttokens_out")
        for row in rows:
            print("\t".join(str(value) for value in row.values()))
    else:
        for row in rows:
            print(f"{row['id']}\t{row.get('agent')}\t{row.get('tier')}\t{row.get('status')}")
    return EXIT_OK
