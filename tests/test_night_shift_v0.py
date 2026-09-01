"""
ALADIN37 - Night Shift V0 - Read-only & atomicity contract tests.

These tests do NOT touch the production database (data/aladin37.db) or
the production NIGHT_SHIFT/findings directory. They exercise the
read-only DB guarantee and the atomic-findings-write behaviour in
isolation, using pytest's tmp_path fixture and monkeypatching of the
module-level path constants.

Per Night Shift V0 Spec: does not import/call claude_parser.py, does
not import/call dedupe.py, does not touch the M0 scoring contract
tests, does not run any git command.
"""

import inspect
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from night_shift import runner  # noqa: E402


def _make_scratch_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE listings (id INTEGER PRIMARY KEY, city TEXT)")
    conn.execute("INSERT INTO listings (id, city) VALUES (1, 'santa ponsa')")
    conn.commit()
    conn.close()


def test_readonly_connection_rejects_write(tmp_path):
    """
    Safety invariant #1: a write attempt through the mode=ro connection
    MUST raise sqlite3.OperationalError, enforced by SQLite itself -
    not just avoided by convention.
    """
    db_path = tmp_path / "scratch.db"
    _make_scratch_db(db_path)

    conn = runner._open_readonly_connection(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly database"):
            conn.execute("INSERT INTO listings (id, city) VALUES (2, 'palma')")
    finally:
        conn.close()


def test_readonly_connection_allows_select(tmp_path):
    db_path = tmp_path / "scratch.db"
    _make_scratch_db(db_path)

    conn = runner._open_readonly_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM listings").fetchall()
        assert len(rows) == 1
        assert rows[0]["city"] == "santa ponsa"
    finally:
        conn.close()


def test_findings_written_atomically(tmp_path, monkeypatch):
    """
    Safety invariants #2/#3: no temp file remains after a successful
    write, exactly one final artifact exists, and its name carries the
    run_id.
    """
    findings_dir = tmp_path / "findings"
    monkeypatch.setattr(runner, "FINDINGS_DIR", findings_dir)

    findings = [{
        "listing_id": 1, "city": "santa ponsa",
        "stored_decision": "WEITERVERFOLGEN", "stored_total_score": 80.0,
        "recomputed_total_score": 80.0, "recomputed_decision": "WEITERVERFOLGEN",
        "flags": [],
    }]

    final_path = runner._write_findings_atomically("testrun123", findings)

    assert final_path.exists()
    assert "testrun123" in final_path.name
    remaining = list(findings_dir.iterdir())
    assert remaining == [final_path]  # no leftover .tmp- file


def test_findings_collision_aborts_without_overwrite(tmp_path, monkeypatch):
    """
    Safety invariant #3, TOCTOU-safe: the final artifact is protected by
    os.link()'s atomic FileExistsError, not by a separate exists()
    check followed by a write - so there is no race window between
    checking and creating. This test also confirms the temp file is
    cleaned up after an aborted (colliding) write, leaving no stray
    .tmp- file behind.
    """
    findings_dir = tmp_path / "findings"
    findings_dir.mkdir()
    monkeypatch.setattr(runner, "FINDINGS_DIR", findings_dir)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    existing = findings_dir / f"{timestamp}-collide01.md"
    existing.write_text("pre-existing content", encoding="utf-8")

    with pytest.raises(runner.NightShiftAbort, match="collision"):
        runner._write_findings_atomically("collide01", [])

    assert existing.read_text(encoding="utf-8") == "pre-existing content"
    remaining = list(findings_dir.iterdir())
    assert remaining == [existing]  # no leftover .tmp- file after the aborted link


def test_abort_writes_error_artifact_not_findings(tmp_path, monkeypatch):
    """On abort: exactly one error artifact, no final findings artifact."""
    findings_dir = tmp_path / "findings"
    errors_dir = findings_dir / "errors"
    monkeypatch.setattr(runner, "FINDINGS_DIR", findings_dir)
    monkeypatch.setattr(runner, "ERRORS_DIR", errors_dir)

    error_path = runner._write_error_artifact("aborted01", "simulated failure", 5)

    assert error_path.exists()
    assert "simulated failure" in error_path.read_text(encoding="utf-8")
    md_files_outside_errors = [
        p for p in findings_dir.glob("*.md") if p.parent != errors_dir
    ]
    assert md_files_outside_errors == []


def test_hard_limits_not_runtime_configurable():
    """
    Safety invariant #6: MAX_LISTINGS / RUN_TIMEOUT_SECONDS are plain
    constants with no CLI/env override mechanism in this module.
    """
    assert runner.MAX_LISTINGS == 20
    assert runner.RUN_TIMEOUT_SECONDS > 0

    source = inspect.getsource(runner)
    assert "argparse" not in source
    assert "sys.argv" not in source
    assert "os.environ" not in source


def test_execute_is_not_implemented():
    """Safety invariant #7: no EXECUTE-style write function exists at all."""
    exported = dir(runner)
    forbidden_substrings = ("execute", "insert", "update", "delete", "write_db")
    for name in exported:
        lowered = name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, f"Unexpected EXECUTE-like symbol: {name}"


def test_runner_does_not_import_dedupe_or_claude_parser():
    """
    Hard constraints: no actual import of dedupe.py or claude_parser.py
    in this module. Checked via the module's compiled import graph, not
    a naive substring search (docstrings mention these names on purpose
    to document the constraint).
    """
    assert "dedupe" not in runner.__dict__
    assert "claude_parser" not in runner.__dict__

    source = inspect.getsource(runner)
    forbidden_import_lines = (
        "import dedupe",
        "from intelligence import dedupe",
        "import claude_parser",
        "from intelligence import claude_parser",
    )
    for line in source.splitlines():
        stripped = line.strip()
        for forbidden in forbidden_import_lines:
            assert forbidden not in stripped, f"Forbidden import found: {stripped}"
