from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def default_state_dir() -> Path:
    root = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "smartattend"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


class OfflineEventQueue:
    """A local queue only; the Manus managed database remains the system of record."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.path = Path(database_path) if database_path else default_state_dir() / "events.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS queued_events (
                event_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','failed')),
                attempts INTEGER NOT NULL DEFAULT 0,
                next_retry_at TEXT NOT NULL,
                last_error TEXT,
                created_at TEXT NOT NULL,
                last_attempt_at TEXT
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS ix_queued_events_state_retry ON queued_events(state, next_retry_at)")
            connection.execute("""CREATE TABLE IF NOT EXISTS event_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                error_code TEXT NOT NULL,
                http_status INTEGER,
                failed_at TEXT NOT NULL
            )""")
            connection.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def enqueue(self, payload: dict[str, Any], *, error: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        event_id = str(payload["event_id"])
        idempotency_key = str(payload["idempotency_key"])
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO queued_events(event_id,idempotency_key,payload_json,next_retry_at,last_error,created_at)
                   VALUES(?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET last_error=excluded.last_error""",
                (event_id, idempotency_key, serialized, now, (error or "")[:500] or None, now),
            )
            connection.commit()

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_id,idempotency_key,payload_json,attempts,last_error FROM queued_events WHERE state='pending' AND next_retry_at<=? ORDER BY created_at LIMIT ?",
                (now, max(1, min(limit, 1000))),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def delivered(self, event_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM queued_events WHERE event_id=?", (event_id,))
            connection.commit()

    def retryable_failure(self, event_id: str, error: str) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            row = connection.execute("SELECT attempts FROM queued_events WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                connection.commit()
                return
            attempts = int(row["attempts"]) + 1
            delay = min(2 ** min(attempts, 10), 900)
            next_retry = (now + timedelta(seconds=delay)).isoformat()
            connection.execute("UPDATE queued_events SET attempts=?,next_retry_at=?,last_error=?,last_attempt_at=? WHERE event_id=?", (attempts, next_retry, error[:500], now.isoformat(), event_id))
            connection.commit()

    def terminal_failure(self, event_id: str, error_code: str, http_status: int | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("UPDATE queued_events SET state='failed',last_error=?,last_attempt_at=? WHERE event_id=?", (error_code[:500], now, event_id))
            connection.execute("INSERT INTO event_failures(event_id,error_code,http_status,failed_at) VALUES(?,?,?,?)", (event_id, error_code[:160], http_status, now))
            connection.commit()

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute("SELECT state,COUNT(*) AS count FROM queued_events GROUP BY state").fetchall()
        counts = {"pending": 0, "failed": 0}
        counts.update({str(row["state"]): int(row["count"]) for row in rows})
        return counts
