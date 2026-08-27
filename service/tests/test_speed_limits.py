from datetime import datetime, timedelta, timezone
from pathlib import Path

from traffictracker.speed_limits import (
    SpeedLimitMatch,
    last_refresh_age_days,
    read_all,
    replace_all,
)


def test_replace_all_then_read(tmp_path: Path) -> None:
    db_path = tmp_path / "speed_limits.sqlite3"
    matches = [
        SpeedLimitMatch(segment_id="S1", speed_limit_kmh=100, overlap_ratio=0.95, matched_zone_count=2),
        SpeedLimitMatch(segment_id="S2", speed_limit_kmh=80, overlap_ratio=0.55, matched_zone_count=6),
    ]
    replace_all(matches, db_path=db_path, computed_at_utc=datetime(2026, 8, 28, tzinfo=timezone.utc))

    reference = read_all(db_path=db_path)
    assert reference["S1"].speed_limit_kmh == 100
    assert reference["S1"].confident is True
    assert reference["S2"].overlap_ratio == 0.55
    assert reference["S2"].confident is False


def test_replace_all_clears_stale_segments(tmp_path: Path) -> None:
    db_path = tmp_path / "speed_limits.sqlite3"
    replace_all(
        [SpeedLimitMatch(segment_id="S1", speed_limit_kmh=100, overlap_ratio=0.9, matched_zone_count=1)],
        db_path=db_path,
    )
    # A segment present in the first run but absent from the second run's
    # matches must not survive as a stale row under a fresh-looking replace.
    replace_all(
        [SpeedLimitMatch(segment_id="S2", speed_limit_kmh=60, overlap_ratio=0.9, matched_zone_count=1)],
        db_path=db_path,
    )

    reference = read_all(db_path=db_path)
    assert "S1" not in reference
    assert "S2" in reference


def test_read_all_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_all(db_path=tmp_path / "does-not-exist.sqlite3") == {}


def test_last_refresh_age_days(tmp_path: Path) -> None:
    db_path = tmp_path / "speed_limits.sqlite3"
    computed_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    replace_all(
        [SpeedLimitMatch(segment_id="S1", speed_limit_kmh=100, overlap_ratio=0.9, matched_zone_count=1)],
        db_path=db_path,
        computed_at_utc=computed_at,
    )

    age = last_refresh_age_days(db_path=db_path, now=computed_at + timedelta(days=10))
    assert age is not None
    assert 9.9 < age < 10.1


def test_last_refresh_age_days_never_run(tmp_path: Path) -> None:
    assert last_refresh_age_days(db_path=tmp_path / "does-not-exist.sqlite3") is None
