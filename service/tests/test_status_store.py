from datetime import datetime, timezone

from traffictracker.status_store import StatusStore

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def test_read_status_returns_none_when_file_missing(tmp_path):
    store = StatusStore(db_path=tmp_path / "status.sqlite3")
    assert store.read_status() is None


def test_write_then_read_round_trips(tmp_path):
    store = StatusStore(db_path=tmp_path / "status.sqlite3")
    store.write_status(
        consecutive_failures=2,
        circuit_tripped=False,
        traffic_baseline_stable=True,
        gis_baseline_stable=None,
        now=NOW,
    )

    snapshot = store.read_status()
    assert snapshot.consecutive_failures == 2
    assert snapshot.circuit_tripped is False
    assert snapshot.traffic_baseline_stable is True
    assert snapshot.gis_baseline_stable is None
    assert snapshot.updated_at_utc == NOW.isoformat()


def test_write_status_upserts_single_row(tmp_path):
    store = StatusStore(db_path=tmp_path / "status.sqlite3")
    store.write_status(
        consecutive_failures=1,
        circuit_tripped=False,
        traffic_baseline_stable=True,
        gis_baseline_stable=True,
        now=NOW,
    )
    store.write_status(
        consecutive_failures=5,
        circuit_tripped=True,
        traffic_baseline_stable=False,
        gis_baseline_stable=False,
        now=NOW,
    )

    snapshot = store.read_status()
    assert snapshot.consecutive_failures == 5
    assert snapshot.circuit_tripped is True
    assert snapshot.traffic_baseline_stable is False
    assert snapshot.gis_baseline_stable is False
