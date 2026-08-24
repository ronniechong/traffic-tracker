"""Day-partitioned history storage.

One SQLite file per UTC calendar day. The partition boundary is UTC, not
Melbourne local time, matching the UTC-everywhere storage convention —
`published_time_utc` is what's stored, so partitioning on anything but UTC
days would let a single local day span two files. Each closed file is a
complete, non-overlapping unit standing alone as its own export boundary.

`data_substitution` is stored as the raw 0-100 value only. The tier label
("measured" / "partially_interpolated" / "majority_interpolated") is a
derived view of that value, not a persisted column — computed via
`quality.substitution_tier()` at query time, so the boundary can move
without a backfill.

Geometry is static per segment (a freeway segment's shape doesn't change
poll to poll) so it's kept in its own table, upserted once per segment per
partition rather than repeated on every reading row — repeating a
~1.5KB-average GeoJSON payload across ~700 polls/day per segment would
inflate each day-partition roughly 100x for zero informational gain.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from traffictracker.models import SegmentRecord

DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "history"

SCHEMA = """
CREATE TABLE IF NOT EXISTS segment_readings (
    id INTEGER PRIMARY KEY,
    segment_id TEXT NOT NULL,
    freeway_name TEXT NOT NULL,
    segment_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    condition TEXT,
    data_substitution REAL,
    published_time_utc TEXT NOT NULL,
    polled_at_utc TEXT NOT NULL,
    stale INTEGER NOT NULL,
    geometry_status TEXT NOT NULL,
    has_override INTEGER NOT NULL,
    override_raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segment_readings_segment_time
    ON segment_readings (segment_id, published_time_utc);

CREATE TABLE IF NOT EXISTS segment_geometry (
    segment_id TEXT PRIMARY KEY,
    geometry TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);
"""


def partition_path(day: date, data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    return data_dir / f"{day.isoformat()}.sqlite3"


DEFAULT_RETENTION_DAYS = 90


def prune_partitions_older_than(
    retention_days: int = DEFAULT_RETENTION_DAYS,
    data_dir: Path = DEFAULT_DATA_DIR,
    reference_day: date | None = None,
) -> list[Path]:
    """Deletes whole day-partition files older than the retention window.

    Deliberately unconditional — deletion never checks whether a partition
    was exported to long-term storage first. The HF archive pipeline (not
    yet built) is meant to stay a fully decoupled, read-only consumer of
    closed partitions with its own failure domain: its safety net is an
    alert if an unarchived day's age exceeds `retention_days - 7` (a 7-day
    buffer), not a block on this function. Coupling deletion to upload
    success would let a broken archiver silently stall retention instead.
    """
    reference = reference_day or datetime.now(timezone.utc).date()
    cutoff = date.fromordinal(reference.toordinal() - retention_days)

    deleted = []
    for path in sorted(data_dir.glob("*.sqlite3")):
        try:
            partition_day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if partition_day < cutoff:
            path.unlink()
            deleted.append(path)
    return deleted


class HistoryStore:
    """Owns one open connection at a time, to whichever day's partition is
    currently being written. Reopens automatically when the UTC day rolls
    over mid-run, so a long-lived poller never has to restart to pick up
    the new partition."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        self._data_dir = data_dir
        self._conn: sqlite3.Connection | None = None
        self._open_day: date | None = None

    def _connection_for(self, day: date) -> sqlite3.Connection:
        if self._conn is not None and self._open_day == day:
            return self._conn
        if self._conn is not None:
            self._conn.close()

        self._data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(partition_path(day, self._data_dir))
        conn.executescript(SCHEMA)
        conn.commit()

        self._conn = conn
        self._open_day = day
        return conn

    def write_records(
        self,
        records: list[SegmentRecord],
        polled_at_utc: datetime | None = None,
    ) -> None:
        polled_at = polled_at_utc or datetime.now(timezone.utc)
        conn = self._connection_for(polled_at.date())

        conn.executemany(
            """
            INSERT INTO segment_readings (
                segment_id, freeway_name, segment_name, direction, condition,
                data_substitution, published_time_utc, polled_at_utc, stale,
                geometry_status, has_override, override_raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.segment_id,
                    r.freeway_name,
                    r.segment_name,
                    r.direction,
                    r.condition,
                    r.data_substitution,
                    r.published_time_utc.isoformat(),
                    polled_at.isoformat(),
                    int(r.stale),
                    r.geometry_status.value,
                    int(r.has_override),
                    json.dumps(r.override_raw),
                )
                for r in records
            ],
        )

        conn.executemany(
            """
            INSERT INTO segment_geometry (segment_id, geometry, updated_at_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(segment_id) DO UPDATE SET
                geometry = excluded.geometry,
                updated_at_utc = excluded.updated_at_utc
            """,
            [
                (r.segment_id, json.dumps(r.geometry), polled_at.isoformat())
                for r in records
                if r.geometry is not None
            ],
        )
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._open_day = None


@dataclass(frozen=True)
class CurrentReading:
    segment_id: str
    freeway_name: str
    segment_name: str
    direction: str
    condition: str | None
    data_substitution: float | None
    published_time_utc: str
    stale: bool
    geometry_status: str
    has_override: bool
    geometry: dict[str, Any] | None


def _open_readonly(path: Path) -> sqlite3.Connection | None:
    """Opens a partition file read-only, returning None if it doesn't exist
    yet -- a fresh deploy or an early hour of the day may not have written
    yesterday's or today's partition at all."""
    if not path.exists():
        return None
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def read_current_segments(
    data_dir: Path = DEFAULT_DATA_DIR, now: datetime | None = None
) -> list[CurrentReading]:
    """Freshest reading per segment across the current UTC day's partition
    and the previous day's -- two partitions cover the case where a segment
    hasn't reported yet today but did shortly before UTC midnight.
    """
    reference = now or datetime.now(timezone.utc)
    days = [reference.date(), reference.date() - timedelta(days=1)]

    latest_by_segment: dict[str, CurrentReading] = {}
    geometry_by_segment: dict[str, dict[str, Any]] = {}

    for day in days:
        conn = _open_readonly(partition_path(day, data_dir))
        if conn is None:
            continue
        try:
            rows = conn.execute(
                """
                SELECT segment_id, freeway_name, segment_name, direction, condition,
                       data_substitution, published_time_utc, stale, geometry_status,
                       has_override
                FROM segment_readings
                """
            ).fetchall()
            for geom_segment_id, geometry in conn.execute(
                "SELECT segment_id, geometry FROM segment_geometry"
            ).fetchall():
                geometry_by_segment.setdefault(geom_segment_id, json.loads(geometry))
        finally:
            conn.close()

        for row in rows:
            (
                segment_id,
                freeway_name,
                segment_name,
                direction,
                condition,
                data_substitution,
                published_time_utc,
                stale,
                geometry_status,
                has_override,
            ) = row
            existing = latest_by_segment.get(segment_id)
            if existing is not None and existing.published_time_utc >= published_time_utc:
                continue
            latest_by_segment[segment_id] = CurrentReading(
                segment_id=segment_id,
                freeway_name=freeway_name,
                segment_name=segment_name,
                direction=direction,
                condition=condition,
                data_substitution=data_substitution,
                published_time_utc=published_time_utc,
                stale=bool(stale),
                geometry_status=geometry_status,
                has_override=bool(has_override),
                geometry=None,
            )

    return [
        replace(r, geometry=geometry_by_segment.get(r.segment_id))
        for r in latest_by_segment.values()
    ]
