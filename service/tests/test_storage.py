import sqlite3
from datetime import date, datetime, timedelta, timezone

from traffictracker.geometry_cache import GeometryStatus
from traffictracker.models import SegmentRecord
from traffictracker.quality import SubstitutionTier
from traffictracker.storage import (
    HistoryStore,
    find_blank_since,
    partition_path,
    prune_partitions_older_than,
)


def _record(
    segment_id="S1",
    data_substitution=None,
    geometry=None,
    condition="Light",
    published_time_utc=None,
) -> SegmentRecord:
    return SegmentRecord(
        segment_id=segment_id,
        freeway_name="Monash Fwy",
        segment_name="Example Segment",
        direction="Inbound",
        condition=condition,
        data_substitution=data_substitution,
        substitution_tier=SubstitutionTier.MEASURED,
        published_time_utc=published_time_utc or datetime(2026, 8, 20, 7, 3, 0, tzinfo=timezone.utc),
        stale=False,
        geometry=geometry,
        geometry_status=GeometryStatus.AVAILABLE if geometry else GeometryStatus.PENDING,
        has_override=False,
        override_raw={
            "overrideStartTime": None,
            "overrideEndTime": None,
            "messageRequested": None,
            "maxEndTime": None,
        },
    )


def test_write_records_creates_day_partition_file(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    polled_at = datetime(2026, 8, 20, 7, 3, 0, tzinfo=timezone.utc)

    store.write_records([_record()], polled_at_utc=polled_at)

    expected_path = partition_path(polled_at.date(), tmp_path)
    assert expected_path.exists()

    conn = sqlite3.connect(expected_path)
    rows = conn.execute("SELECT segment_id, data_substitution FROM segment_readings").fetchall()
    assert rows == [("S1", None)]


def test_write_records_rolls_over_to_new_partition_on_day_change(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    day_one = datetime(2026, 8, 20, 23, 59, 0, tzinfo=timezone.utc)
    day_two = datetime(2026, 8, 21, 0, 1, 0, tzinfo=timezone.utc)

    store.write_records([_record(segment_id="S1")], polled_at_utc=day_one)
    store.write_records([_record(segment_id="S2")], polled_at_utc=day_two)

    assert partition_path(day_one.date(), tmp_path).exists()
    assert partition_path(day_two.date(), tmp_path).exists()

    conn_one = sqlite3.connect(partition_path(day_one.date(), tmp_path))
    conn_two = sqlite3.connect(partition_path(day_two.date(), tmp_path))
    assert conn_one.execute("SELECT segment_id FROM segment_readings").fetchall() == [("S1",)]
    assert conn_two.execute("SELECT segment_id FROM segment_readings").fetchall() == [("S2",)]


def test_override_stored_as_json(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    polled_at = datetime(2026, 8, 20, 7, 3, 0, tzinfo=timezone.utc)

    store.write_records([_record()], polled_at_utc=polled_at)

    conn = sqlite3.connect(partition_path(polled_at.date(), tmp_path))
    row = conn.execute("SELECT override_raw FROM segment_readings").fetchone()
    assert "overrideStartTime" in row[0]


def test_geometry_stored_once_per_segment_not_per_reading(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    polled_at = datetime(2026, 8, 20, 7, 3, 0, tzinfo=timezone.utc)
    geometry = {"type": "LineString", "coordinates": [[144.9, -37.8], [144.95, -37.85]]}

    for _ in range(3):
        store.write_records([_record(geometry=geometry)], polled_at_utc=polled_at)

    conn = sqlite3.connect(partition_path(polled_at.date(), tmp_path))
    readings = conn.execute("SELECT COUNT(*) FROM segment_readings").fetchone()[0]
    geometries = conn.execute("SELECT segment_id, geometry FROM segment_geometry").fetchall()

    assert readings == 3
    assert len(geometries) == 1
    assert "LineString" in geometries[0][1]


def test_write_records_omits_geometry_column_from_readings(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    polled_at = datetime(2026, 8, 20, 7, 3, 0, tzinfo=timezone.utc)

    store.write_records([_record(geometry={"type": "Point", "coordinates": [1, 2]})], polled_at_utc=polled_at)

    conn = sqlite3.connect(partition_path(polled_at.date(), tmp_path))
    columns = {row[1] for row in conn.execute("PRAGMA table_info(segment_readings)")}
    assert "geometry" not in columns


def test_prune_partitions_older_than_deletes_only_stale_files(tmp_path):
    for day in ["2026-06-01", "2026-07-01", "2026-08-19", "2026-08-20"]:
        partition_path(date.fromisoformat(day), tmp_path).touch()

    deleted = prune_partitions_older_than(
        retention_days=60, data_dir=tmp_path, reference_day=date(2026, 8, 20)
    )

    remaining = {p.name for p in tmp_path.glob("*.sqlite3")}
    assert {p.name for p in deleted} == {"2026-06-01.sqlite3"}
    assert remaining == {"2026-07-01.sqlite3", "2026-08-19.sqlite3", "2026-08-20.sqlite3"}


def test_find_blank_since_stops_at_first_non_blank_reading(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    base = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    readings = [
        (base, "Light"),
        (base + timedelta(minutes=2), "Blank"),
        (base + timedelta(minutes=4), "Blank"),
        (base + timedelta(minutes=6), "Blank"),
    ]
    for published_time_utc, condition in readings:
        store.write_records(
            [_record(published_time_utc=published_time_utc, condition=condition)],
            polled_at_utc=published_time_utc,
        )
    store.close()

    since = find_blank_since("S1", before=readings[-1][0], data_dir=tmp_path)
    assert since == readings[1][0]


def test_find_blank_since_walks_back_across_day_partitions(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    day_one_start = datetime(2026, 8, 19, 23, 0, 0, tzinfo=timezone.utc)
    day_two_reading = datetime(2026, 8, 20, 1, 0, 0, tzinfo=timezone.utc)

    store.write_records(
        [_record(published_time_utc=day_one_start, condition="Blank")],
        polled_at_utc=day_one_start,
    )
    store.write_records(
        [_record(published_time_utc=day_two_reading, condition="Blank")],
        polled_at_utc=day_two_reading,
    )
    store.close()

    since = find_blank_since("S1", before=day_two_reading, data_dir=tmp_path)
    assert since == day_one_start


def test_find_blank_since_none_when_no_history(tmp_path):
    since = find_blank_since("unknown", before=datetime(2026, 8, 20, tzinfo=timezone.utc), data_dir=tmp_path)
    assert since is None


def test_find_blank_since_none_when_latest_is_not_blank(tmp_path):
    store = HistoryStore(data_dir=tmp_path)
    published = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    store.write_records(
        [_record(published_time_utc=published, condition="Light")], polled_at_utc=published
    )
    store.close()

    since = find_blank_since("S1", before=published, data_dir=tmp_path)
    assert since is None
