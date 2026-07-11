"""SQLite persistence for evaluation traces."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_db_lock = threading.Lock()


def default_db_path() -> Path:
    configured = os.environ.get("AGENTCHECK_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "agentcheck.db"


def _resolve_db_path(db_path: Path | None = None) -> Path:
    if db_path is not None:
        return db_path
    return default_db_path()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id TEXT NOT NULL,
            run_number INTEGER NOT NULL,
            agent_type TEXT,
            created_at TEXT NOT NULL,
            trace_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            example_id TEXT,
            agent_spec_json TEXT NOT NULL,
            fault_spec_json TEXT NOT NULL,
            injection_point_json TEXT NOT NULL,
            clean_trajectory_json TEXT NOT NULL,
            faulted_trajectory_json TEXT NOT NULL,
            mitigated_trajectory_json TEXT,
            divergence_json TEXT,
            leg_a_json TEXT,
            leg_b_json TEXT,
            fix_confirmed INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    _ensure_columns(
        conn,
        "comparisons",
        {
            "leg_a_faulted_json": "TEXT",
            "leg_b_faulted_json": "TEXT",
            "leg_a_mitigated_json": "TEXT",
            "leg_b_mitigated_json": "TEXT",
        },
    )
    conn.commit()
    return conn


def save_trace(trace: dict, db_path: Path | None = None) -> None:
    """Persist a completed trace record to SQLite."""
    with _db_lock:
        conn = _connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO traces (scenario_id, run_number, agent_type, created_at, trace_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    trace.get("scenario_id", ""),
                    trace.get("run_number", 1),
                    trace.get("agent_type", ""),
                    trace.get("completed_at")
                    or datetime.now(timezone.utc).isoformat(),
                    json.dumps(trace),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def save_comparison(
    comparison: dict,
    example_id: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Persist a completed controlled comparison (clean/faulted/mitigated + scoring).

    ``comparison`` is expected to be a plain, JSON-serializable dict containing
    the trajectories, divergence, Leg A/Leg B results, and optional mitigation
    outcome for one bundled or live workbench comparison.
    """
    with _db_lock:
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO comparisons (
                    example_id, agent_spec_json, fault_spec_json, injection_point_json,
                    clean_trajectory_json, faulted_trajectory_json, mitigated_trajectory_json,
                    divergence_json, leg_a_json, leg_b_json,
                    leg_a_faulted_json, leg_b_faulted_json, leg_a_mitigated_json, leg_b_mitigated_json,
                    fix_confirmed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    example_id,
                    json.dumps(comparison.get("agent_spec")),
                    json.dumps(comparison.get("fault_spec")),
                    json.dumps(comparison.get("injection_point")),
                    json.dumps(comparison.get("clean_trajectory")),
                    json.dumps(comparison.get("faulted_trajectory")),
                    json.dumps(comparison.get("mitigated_trajectory"))
                    if comparison.get("mitigated_trajectory") is not None
                    else None,
                    json.dumps(comparison.get("divergence")),
                    json.dumps(comparison.get("leg_a_faulted", comparison.get("leg_a"))),
                    json.dumps(comparison.get("leg_b_faulted", comparison.get("leg_b"))),
                    json.dumps(comparison.get("leg_a_faulted", comparison.get("leg_a"))),
                    json.dumps(comparison.get("leg_b_faulted", comparison.get("leg_b"))),
                    json.dumps(comparison.get("leg_a_mitigated")),
                    json.dumps(comparison.get("leg_b_mitigated")),
                    int(bool(comparison.get("fix_confirmed")))
                    if comparison.get("fix_confirmed") is not None
                    else None,
                    comparison.get("created_at") or datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()


def load_comparison(comparison_id: int, db_path: Path | None = None) -> dict | None:
    with _db_lock:
        conn = _connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM comparisons WHERE id = ?", (comparison_id,)
            ).fetchone()
            if row is None:
                return None
            columns = [c[0] for c in conn.execute("SELECT * FROM comparisons LIMIT 0").description]
            return _row_to_comparison_dict(dict(zip(columns, row)))
        finally:
            conn.close()


def list_comparisons(
    example_id: str | None = None,
    db_path: Path | None = None,
) -> list[dict]:
    with _db_lock:
        conn = _connect(db_path)
        try:
            if example_id is not None:
                rows = conn.execute(
                    "SELECT * FROM comparisons WHERE example_id = ? ORDER BY id DESC",
                    (example_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM comparisons ORDER BY id DESC").fetchall()
            columns = [c[0] for c in conn.execute("SELECT * FROM comparisons LIMIT 0").description]
            return [_row_to_comparison_dict(dict(zip(columns, row))) for row in rows]
        finally:
            conn.close()


def _row_to_comparison_dict(row: dict) -> dict:
    def _load(key: str):
        value = row.get(key)
        return json.loads(value) if value is not None else None

    return {
        "id": row["id"],
        "example_id": row.get("example_id"),
        "agent_spec": _load("agent_spec_json"),
        "fault_spec": _load("fault_spec_json"),
        "injection_point": _load("injection_point_json"),
        "clean_trajectory": _load("clean_trajectory_json"),
        "faulted_trajectory": _load("faulted_trajectory_json"),
        "mitigated_trajectory": _load("mitigated_trajectory_json"),
        "divergence": _load("divergence_json"),
        "leg_a_faulted": _load("leg_a_faulted_json") or _load("leg_a_json"),
        "leg_b_faulted": _load("leg_b_faulted_json") or _load("leg_b_json"),
        "leg_a_mitigated": _load("leg_a_mitigated_json"),
        "leg_b_mitigated": _load("leg_b_mitigated_json"),
        "fix_confirmed": bool(row["fix_confirmed"]) if row.get("fix_confirmed") is not None else None,
        "created_at": row.get("created_at"),
    }
