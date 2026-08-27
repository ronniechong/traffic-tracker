"""Reference store for per-segment speed limits, joined from the Speed
Zones dataset by the monthly batch job.

Deliberately NOT day-partitioned like `segment_geometry` in `storage.py`:
that table is duplicated inside every day-partition file and kept fresh
only because the always-running poller re-upserts it every poll. A monthly
job has no equivalent continuous process to repopulate each new day's
partition, so this lives in its own single non-partitioned file instead,
joined against `read_current_segments()`'s result in application code.

Refresh is a full atomic replace, not an upsert: a segment with zero
matches this run must have its row cleared, not left holding a stale value
under a fresh-looking `computed_at_utc`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "speed_limits.sqlite3"

# Below this overlap-ratio share, the dominant match isn't trustworthy
# enough to present without a caveat -- freeway interchange ramps and
# tunnel sections routinely have multiple speed zones competing inside
# the match buffer.
CONFIDENCE_THRESHOLD = 0.7

SCHEMA = """
CREATE TABLE IF NOT EXISTS segment_speed_limit (
    segment_id TEXT PRIMARY KEY,
    speed_limit_kmh INTEGER NOT NULL,
    overlap_ratio REAL NOT NULL,
    matched_zone_count INTEGER NOT NULL,
    computed_at_utc TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class SpeedLimitMatch:
    segment_id: str
    speed_limit_kmh: int
    overlap_ratio: float
    matched_zone_count: int

    @property
    def confident(self) -> bool:
        return self.overlap_ratio >= CONFIDENCE_THRESHOLD


def _connect(db_path: Path, *, readonly: bool) -> sqlite3.Connection | None:
    if readonly and not db_path.exists():
        return None
    if readonly:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def replace_all(
    matches: list[SpeedLimitMatch],
    db_path: Path = DEFAULT_DB_PATH,
    computed_at_utc: datetime | None = None,
) -> None:
    """Atomically replaces the entire table's contents with `matches` in a
    single transaction -- segments with no match this run are simply
    absent afterward, never left holding a prior run's value."""
    computed_at = (computed_at_utc or datetime.now(timezone.utc)).isoformat()
    conn = _connect(db_path, readonly=False)
    assert conn is not None
    try:
        with conn:
            conn.execute("DELETE FROM segment_speed_limit")
            conn.executemany(
                """
                INSERT INTO segment_speed_limit (
                    segment_id, speed_limit_kmh, overlap_ratio,
                    matched_zone_count, computed_at_utc
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (m.segment_id, m.speed_limit_kmh, m.overlap_ratio, m.matched_zone_count, computed_at)
                    for m in matches
                ],
            )
    finally:
        conn.close()


@dataclass(frozen=True)
class SpeedLimitReference:
    speed_limit_kmh: int
    overlap_ratio: float
    confident: bool
    computed_at_utc: str


def read_all(db_path: Path = DEFAULT_DB_PATH) -> dict[str, SpeedLimitReference]:
    """Reads the full reference table keyed by segment_id. Returns an empty
    dict if the file doesn't exist yet -- the job hasn't run for the first
    time, not an error."""
    conn = _connect(db_path, readonly=True)
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT segment_id, speed_limit_kmh, overlap_ratio, computed_at_utc FROM segment_speed_limit"
        ).fetchall()
    finally:
        conn.close()

    return {
        segment_id: SpeedLimitReference(
            speed_limit_kmh=speed_limit_kmh,
            overlap_ratio=overlap_ratio,
            confident=overlap_ratio >= CONFIDENCE_THRESHOLD,
            computed_at_utc=computed_at_utc,
        )
        for segment_id, speed_limit_kmh, overlap_ratio, computed_at_utc in rows
    }


def last_refresh_age_days(db_path: Path = DEFAULT_DB_PATH, now: datetime | None = None) -> float | None:
    """Age in days of the most recent successful refresh, or None if the
    job has never run. All rows share one `computed_at_utc` per run (full
    replace), so any single row's timestamp represents the whole table."""
    reference = read_all(db_path)
    if not reference:
        return None
    computed_at = datetime.fromisoformat(next(iter(reference.values())).computed_at_utc)
    reference_now = now or datetime.now(timezone.utc)
    return (reference_now - computed_at).total_seconds() / 86400
