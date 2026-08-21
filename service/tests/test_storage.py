import sqlite3
from datetime import date, datetime, timezone

from traffictracker.models import SegmentRecord
from traffictracker.quality import SubstitutionTier
from traffictracker.storage import HistoryStore, partition_path, prune_partitions_older_than


def _record(segment_id="S1", data_substitution=None, geometry=None) -> SegmentRecord:
    return SegmentRecord(
        segment_id=segment_id,
        freeway_name="Monash Fwy",
        segment_name="Example Segment",
        direction="Inbound",
        condition="Light",
        data_substitution=data_substitution,
        substitution_tier=SubstitutionTier.MEASURED,
        published_time_utc=datetime(2026, 8, 20, 7, 3, 0, tzinfo=timezone.utc),
        stale=False,
        geometry=geometry,
        geometry_is_fallback=False,
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
