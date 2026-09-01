"""
ALADIN37 - Night Shift V0 Runner
=================================

Read-only OBSERVE + PROPOSE runner. No EXECUTE, no writes to the
application database, no Anthropic API calls, no git operations.

Safety invariants (see ALADIN37 Night Shift V0 Spec, FINAL):
1. DB connection exclusively via `file:<path>?mode=ro` URI. No other
   connection path exists in this module.
2. A final findings artifact is only ever created via atomic os.rename()
   after a fully successful run.
3. An existing artifact is never overwritten - a name collision aborts
   the run instead.
4. No Anthropic API call in V0 (claude_parser is never imported/called).
5. No git command, no change to M0 baseline, no dedupe.py access.
6. Hard limits (MAX_LISTINGS, RUN_TIMEOUT_SECONDS) are plain module
   constants - there is no CLI flag, env var, or other runtime
   mechanism in this module that can change them.
7. EXECUTE does not exist in V0 - not implemented, not a disabled flag.
"""

import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# --- Hard limits: plain constants, not exposed as CLI args or env vars ---
MAX_LISTINGS = 20
RUN_TIMEOUT_SECONDS = 600

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "aladin37.db"
FINDINGS_DIR = REPO_ROOT / "NIGHT_SHIFT" / "findings"
ERRORS_DIR = FINDINGS_DIR / "errors"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence import scoring  # noqa: E402
from pipeline import decide  # noqa: E402


class NightShiftAbort(Exception):
    """Raised whenever a run must stop without producing a final artifact."""


def _open_readonly_connection(db_path: Path) -> sqlite3.Connection:
    """
    Opens an ALADIN37-style SQLite database strictly read-only.

    Safety invariant #1: this is the ONLY connection helper used in
    Night Shift V0. Any write attempt through the returned connection
    must raise sqlite3.OperationalError: attempt to write a readonly
    database - enforced by SQLite itself, not by code convention.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_listings(conn: sqlite3.Connection, limit: int) -> list:
    rows = conn.execute(
        "SELECT * FROM listings ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def _observe_and_propose(listing_row: dict) -> dict:
    """
    OBSERVE: re-runs scoring.score_listing() on already-stored data.
    PROPOSE: applies pipeline.decide() to the resulting total_score.

    No database write happens here or anywhere else in this module.
    Does not import or call dedupe.py or claude_parser.py.
    """
    normalized = {}
    if listing_row.get("normalized_json"):
        try:
            normalized = json.loads(listing_row["normalized_json"])
        except (json.JSONDecodeError, TypeError):
            normalized = {}

    listing = {
        "price": listing_row.get("price"),
        "city": listing_row.get("city"),
        "living_area": listing_row.get("living_area"),
        "_raw_text": listing_row.get("raw_text"),
    }

    score_result = scoring.score_listing(listing, normalized)
    proposed_decision = decide(score_result["total_score"])

    return {
        "listing_id": listing_row.get("id"),
        "city": listing_row.get("city"),
        "stored_decision": listing_row.get("decision"),
        "stored_total_score": listing_row.get("total_score"),
        "recomputed_total_score": score_result["total_score"],
        "recomputed_decision": proposed_decision,
        "flags": score_result["flags"],
    }


def _write_findings_atomically(run_id: str, findings: list) -> Path:
    """
    Safety invariants #2/#3: writes to a temp file first, then finalizes
    via os.rename() only after full success. Never overwrites an
    existing final artifact - a name collision raises NightShiftAbort
    instead.
    """
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp_path = FINDINGS_DIR / f".tmp-{run_id}.md"
    final_path = FINDINGS_DIR / f"{timestamp}-{run_id}.md"

    lines = [
        "# ALADIN37 Night Shift V0 - Findings",
        f"run_id: {run_id}",
        f"generated_at_utc: {timestamp}",
        f"listings_processed: {len(findings)}",
        "",
    ]
    for f in findings:
        lines.append(f"## Listing #{f['listing_id']} ({f.get('city') or 'unknown city'})")
        lines.append(f"- stored_decision: {f['stored_decision']}")
        lines.append(f"- stored_total_score: {f['stored_total_score']}")
        lines.append(f"- recomputed_total_score: {f['recomputed_total_score']}")
        lines.append(f"- recomputed_decision: {f['recomputed_decision']}")
        lines.append(f"- flags: {f['flags'] or 'none'}")
        lines.append("")

    tmp_path.write_text("\n".join(lines), encoding="utf-8")

    # Atomic finalize: os.link() atomically fails with FileExistsError if
    # final_path already exists - there is no exists()-then-write race
    # window, unlike a bare os.rename() preceded by an exists() check.
    # The tmp file is only removed after the link (or the abort) is
    # resolved, so a crash between link() and unlink() still leaves the
    # final artifact correctly in place with no data loss.
    try:
        os.link(tmp_path, final_path)
    except FileExistsError as exc:
        raise NightShiftAbort(
            f"Findings artifact collision: {final_path} already exists"
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return final_path


def _write_error_artifact(run_id: str, reason: str, processed_count: int) -> Path:
    """
    On any abort: exactly one error artifact under findings/errors/,
    never a final findings artifact.
    """
    ERRORS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    error_path = ERRORS_DIR / f"{run_id}-error.md"
    lines = [
        "# ALADIN37 Night Shift V0 - Aborted Run",
        f"run_id: {run_id}",
        f"aborted_at_utc: {timestamp}",
        f"listings_processed_before_abort: {processed_count}",
        f"reason: {reason}",
    ]
    error_path.write_text("\n".join(lines), encoding="utf-8")
    return error_path


def run() -> Path:
    """
    Single Night Shift V0 run. Returns the path to the final findings
    artifact on success. On any failure, writes an error artifact and
    raises NightShiftAbort - never leaves a partial findings artifact
    under the final name.
    """
    run_id = uuid.uuid4().hex[:12]
    start = time.monotonic()
    findings: list = []

    try:
        if not DB_PATH.exists():
            raise NightShiftAbort(f"Database not found at {DB_PATH}")

        conn = _open_readonly_connection(DB_PATH)
        try:
            listing_rows = _fetch_listings(conn, MAX_LISTINGS)

            for row in listing_rows:
                if time.monotonic() - start > RUN_TIMEOUT_SECONDS:
                    raise NightShiftAbort("Run timeout exceeded")
                findings.append(_observe_and_propose(row))
        finally:
            conn.close()

        return _write_findings_atomically(run_id, findings)

    except NightShiftAbort as exc:
        _write_error_artifact(run_id, str(exc), len(findings))
        raise
    except Exception as exc:  # noqa: BLE001 - any unexpected failure aborts, never partial-writes
        _write_error_artifact(run_id, f"Unexpected error: {exc!r}", len(findings))
        raise NightShiftAbort(str(exc)) from exc


if __name__ == "__main__":
    run()
