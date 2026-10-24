import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from consortium import runlog


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/codex_events.jsonl"
RUN_FIELDS = {
    "v",
    "type",
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
}


def utc_at(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def parallel_writes(statement):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "plugins/consortium/lib"), PYTHONDONTWRITEBYTECODE="1")
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", "from consortium import runlog; " + statement, str(index)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(10)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stdout + stderr


def test_new_run_ids_and_directories_use_utc_and_isolated_state():
    before = datetime.now(timezone.utc).replace(microsecond=0)
    run_id = runlog.new_run_id("implementer")
    after = datetime.now(timezone.utc)
    assert re.fullmatch(r"\d{8}-\d{6}-implementer-[0-9a-f]{4}", run_id)
    stamp = datetime.strptime(run_id[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    assert before <= stamp <= after
    directory = runlog.run_dir(run_id)
    assert directory == Path(os.environ["CONSORTIUM_HOME"]) / "runs" / run_id
    assert directory.is_dir()


def test_append_is_one_line_per_record_under_concurrency(tmp_path):
    parallel_writes("import sys; runlog.append({'id': sys.argv[1], 'text': 'line\\nbreak' * 10000})")
    lines = (Path(os.environ["CONSORTIUM_HOME"]) / "runs.jsonl").read_text().splitlines()
    assert len(lines) == 10
    assert {json.loads(line)["id"] for line in lines} == {str(index) for index in range(10)}
    assert all(json.loads(line)["text"] == "line\nbreak" * 10000 for line in lines)


def test_record_run_is_idempotent_per_id(tmp_path):
    first = runlog.record_run(id="one", agent="implementer", status="DONE")
    again = runlog.record_run(id="one", agent="different", status="FAILED")
    assert first == again
    assert set(first) == RUN_FIELDS
    assert first["v"] == 1 and first["type"] == "run"
    assert first["status"] == "DONE" and first["agent"] == "implementer"
    assert first["tokens"] is None and first["minutes"] is None
    assert runlog.read_records() == [first]


def test_record_run_is_idempotent_across_processes():
    parallel_writes("runlog.record_run(id='shared', status='DONE')")
    assert len(runlog.read_records()) == 1


def test_summary_groups_by_agent_and_tier_with_verdicts(tmp_path):
    runlog.record_run(
        id="a",
        agent="implementer",
        tier="deep",
        started=utc_at(),
        minutes=2,
        tokens={"input": 100, "cached_input": 80, "output": 20},
    )
    runlog.record_run(
        id="b",
        agent="implementer",
        tier="deep",
        started=utc_at(),
        minutes=3,
        tokens={"input": 200, "cached_input": 0, "output": 30},
    )
    runlog.record_run(id="c", agent="searcher", tier="cheap", started=utc_at(), minutes=1)
    runlog.record_run(id="old", agent="searcher", tier="deep", started=utc_at(8), minutes=99)
    runlog.record_verdict("a", False, "Superseded")
    runlog.record_verdict("a", True, "Kept after review")
    runlog.record_verdict("b", False, None)
    assert runlog.summary(runlog.read_records(), 7) == [
        {
            "agent": "implementer",
            "tier": "deep",
            "runs": 2,
            "kept": 1,
            "dropped": 1,
            "minutes": 5,
            "tokens_in": 300,
            "tokens_out": 50,
        },
        {
            "agent": "searcher",
            "tier": "cheap",
            "runs": 1,
            "kept": 0,
            "dropped": 0,
            "minutes": 1,
            "tokens_in": 0,
            "tokens_out": 0,
        },
    ]


def test_read_records_filters_runs_and_verdicts_by_utc_time():
    assert runlog.read_records() == []
    current = runlog.record_run(id="current", started=utc_at())
    runlog.record_run(id="old", started=utc_at(8))
    runlog.append({"v": 1, "type": "verdict", "id": "old", "kept": True, "note": None, "at": utc_at(8)})
    runlog.record_verdict("current", True, None)
    records = runlog.read_records(days=7)
    assert records[0] == current
    assert len(records) == 2
    assert records[1]["type"] == "verdict" and records[1]["id"] == "current"
    assert records[1]["at"].endswith("Z")


def test_tokens_from_codex_events():
    lines = FIXTURE.read_text().splitlines()
    events = [json.loads(line) for line in lines]
    usage = [event["usage"] for event in events if event["type"].endswith("completed") and "usage" in event]
    assert usage, "The captured run must include real usage."
    assert any(event.get("item", {}).get("text") == "OK" for event in events)
    assert runlog.tokens_from_codex_events(lines) == {
        "input": sum(block["input_tokens"] for block in usage),
        "cached_input": sum(block["cached_input_tokens"] for block in usage),
        "output": sum(block["output_tokens"] for block in usage),
    }
    assert runlog.tokens_from_codex_events([]) is None


def test_codex_usage_is_summed_only_inside_completed_events():
    usage = {"input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 4}
    lines = [
        json.dumps(event)
        for event in [
            {"type": "turn.started", "usage": usage},
            {"type": "turn.completed", "nested": [{"usage": usage}]},
            {"type": "item.completed", "usage": usage},
        ]
    ]
    assert runlog.tokens_from_codex_events(lines) == {"input": 24, "cached_input": 6, "output": 8}


def test_tokens_from_claude_transcript(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    first = {"input_tokens": 100, "cache_read_input_tokens": 40, "cache_creation_input_tokens": 7, "output_tokens": 10}
    second = {"input_tokens": 50, "cache_read_input_tokens": 20, "output_tokens": 5}
    events = [
        {"type": "user", "message": {"content": "Hello"}},
        # One message written as two lines (a thinking block, then text) repeats its usage; it counts once.
        {"type": "assistant", "message": {"id": "msg_1", "model": "test-model", "usage": first}},
        {"type": "assistant", "message": {"id": "msg_1", "model": "test-model", "usage": first}},
        {"type": "assistant", "message": {"id": "msg_2", "model": "test-model", "usage": second}},
        {"type": "assistant", "message": {"id": "msg_3", "model": "<synthetic>", "content": "API error"}},
    ]
    transcript.write_text("".join(json.dumps(event) + "\n" for event in events))
    assert runlog.tokens_from_claude_transcript(transcript) == (
        {"input": 100 + 40 + 7 + 50 + 20, "cached_input": 60, "output": 15},
        "test-model",
    )
    assert runlog.tokens_from_claude_transcript(tmp_path / "missing") == (None, None)
    transcript.write_text("")
    assert runlog.tokens_from_claude_transcript(transcript) == (None, None)


def test_runs_cli_summary_and_verdict(run_cli, tmp_path):
    result = run_cli("runs", "--summary")
    assert result.returncode == 0, result.stderr
    runlog.record_run(id="one", agent="implementer", tier="deep", started=utc_at(), minutes=2)
    result = run_cli("runs", "--verdict", "one", "kept", "--note", "Reviewed")
    assert result.returncode == 0, result.stderr
    verdict = runlog.read_records()[-1]
    assert {key: verdict[key] for key in ("v", "type", "id", "kept", "note")} == {
        "v": 1,
        "type": "verdict",
        "id": "one",
        "kept": True,
        "note": "Reviewed",
    }
    result = run_cli("runs", "--summary", "--days", "7", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        {
            "agent": "implementer",
            "tier": "deep",
            "runs": 1,
            "kept": 1,
            "dropped": 0,
            "minutes": 2,
            "tokens_in": 0,
            "tokens_out": 0,
        },
    ]
    result = run_cli("runs", "--verdict", "one", "dropped")
    assert result.returncode == 0, result.stderr
    assert runlog.read_records()[-1]["kept"] is False


def test_runs_cli_last_limits_run_records(run_cli):
    runlog.record_run(id="one", status="DONE")
    runlog.record_verdict("one", True, None)
    last = runlog.record_run(id="two", status="FAILED")
    result = run_cli("runs", "--last", "1", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [last]
    result = run_cli("runs", "--last", "0", "--json")
    assert result.returncode == 0 and json.loads(result.stdout) == []


def test_runs_wait_prints_the_matching_run_as_json(run_cli):
    runlog.record_verdict("waiting", True, None)
    expected = runlog.record_run(id="waiting", status="DONE")
    result = run_cli("runs", "--wait", "waiting", "--timeout", "0")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
    assert result.stderr == ""


def test_runs_wait_polls_for_a_later_record(run_cli):
    timer = threading.Timer(0.5, lambda: runlog.record_run(id="later", status="DONE"))
    timer.start()
    try:
        result = run_cli("runs", "--wait", "later", "--timeout", "0.1")
    finally:
        timer.join()
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["id"] == "later"


def test_runs_wait_timeout_reports_still_running(run_cli):
    result = run_cli("runs", "--wait", "missing", "--timeout", "0")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == "still running: missing"


@pytest.mark.parametrize("arguments", [("--last", "-1"), ("--days", "-1"), ("--wait", "x", "--timeout", "-1")])
def test_runs_rejects_negative_limits(run_cli, arguments):
    assert run_cli("runs", *arguments).returncode == 2
