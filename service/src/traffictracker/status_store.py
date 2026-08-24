"""Poller status persistence: a single non-partitioned SQLite file holding a
single-row snapshot of the poller's in-process state, upserted every poll
cycle.

Storage is the only interface between the poller process and any reader
process (e.g. the API) -- there is no other IPC. A single-row upsert keeps
the read side to one cheap SELECT with no caching needed at this scale.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATUS_DB_PATH = Path(__file__).parent.parent.parent / "data" / "status.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS poller_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    consecutive_failures INTEGER NOT NULL,
    circuit_tripped INTEGER NOT NULL,
    traffic_baseline_stable INTEGER NOT NULL,
    gis_baseline_stable INTEGER,
    updated_at_utc TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class StatusSnapshot:
    consecutive_failures: int
    circuit_tripped: bool
    traffic_baseline_stable: bool
    gis_baseline_stable: bool | None
    updated_at_utc: str


class StatusStore:
    def __init__(self, db_path: Path = DEFAULT_STATUS_DB_PATH) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.executescript(SCHEMA)
        return conn

    def write_status(
        self,
        consecutive_failures: int,
        circuit_tripped: bool,
        traffic_baseline_stable: bool,
        gis_baseline_stable: bool | None,
        now: datetime | None = None,
    ) -> None:
        updated_at = (now or datetime.now(timezone.utc)).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO poller_status (
                    id, consecutive_failures, circuit_tripped,
                    traffic_baseline_stable, gis_baseline_stable, updated_at_utc
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    consecutive_failures = excluded.consecutive_failures,
                    circuit_tripped = excluded.circuit_tripped,
                    traffic_baseline_stable = excluded.traffic_baseline_stable,
                    gis_baseline_stable = excluded.gis_baseline_stable,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    consecutive_failures,
                    int(circuit_tripped),
                    int(traffic_baseline_stable),
                    None if gis_baseline_stable is None else int(gis_baseline_stable),
                    updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def read_status(self) -> StatusSnapshot | None:
        if not self._db_path.exists():
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT consecutive_failures, circuit_tripped,
                       traffic_baseline_stable, gis_baseline_stable, updated_at_utc
                FROM poller_status WHERE id = 1
                """
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return StatusSnapshot(
            consecutive_failures=row[0],
            circuit_tripped=bool(row[1]),
            traffic_baseline_stable=bool(row[2]),
            gis_baseline_stable=None if row[3] is None else bool(row[3]),
            updated_at_utc=row[4],
        )
