from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from traffictracker.api.app import create_app
from traffictracker.geometry_cache import GeometryStatus
from traffictracker.models import SegmentRecord
from traffictracker.quality import SubstitutionTier, substitution_tier
from traffictracker.status_store import StatusStore
from traffictracker.storage import HistoryStore

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _record(
    segment_id="S1",
    published_time_utc=None,
    data_substitution=None,
    geometry=None,
    geometry_status=GeometryStatus.AVAILABLE,
    stale=False,
    has_override=False,
    condition="Light",
) -> SegmentRecord:
    return SegmentRecord(
        segment_id=segment_id,
        freeway_name="Monash Fwy",
        segment_name="Example Segment",
        direction="Inbound",
        condition=condition,
        data_substitution=data_substitution,
        substitution_tier=substitution_tier(data_substitution),
        published_time_utc=published_time_utc or NOW,
        stale=stale,
        geometry=geometry,
        geometry_status=geometry_status,
        has_override=has_override,
        override_raw={
            "overrideStartTime": None,
            "overrideEndTime": None,
            "messageRequested": None,
            "maxEndTime": None,
        },
    )


def _make_client(tmp_path, frontend_origin="https://frontend.example.invalid", rate_limit="60/minute"):
    data_dir = tmp_path / "history"
    status_db_path = tmp_path / "status.sqlite3"
    app = create_app(
        data_dir=data_dir,
        status_db_path=status_db_path,
        frontend_origin=frontend_origin,
        rate_limit=rate_limit,
    )
    return TestClient(app), data_dir, status_db_path


def test_list_segments_happy_path(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    store.write_records([_record(geometry={"type": "Point", "coordinates": [1, 2]})], polled_at_utc=NOW)
    store.close()

    response = client.get("/v1/segments")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["segment_id"] == "S1"
    assert body[0]["geometry"] == {"type": "Point", "coordinates": [1, 2]}


def test_get_segment_happy_path(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    store.write_records([_record(segment_id="S1"), _record(segment_id="S2")], polled_at_utc=NOW)
    store.close()

    response = client.get("/v1/segments/S2")
    assert response.status_code == 200
    assert response.json()["segment_id"] == "S2"


def test_get_segment_unknown_returns_404_error_contract(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    store.write_records([_record(segment_id="S1")], polled_at_utc=NOW)
    store.close()

    response = client.get("/v1/segments/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert "does-not-exist" in body["error"]["message"]


def test_two_partition_query_prefers_yesterdays_only_record(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    yesterday = NOW - timedelta(days=1)
    store.write_records(
        [_record(segment_id="S1", published_time_utc=yesterday)], polled_at_utc=yesterday
    )
    store.close()

    response = client.get("/v1/segments")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["segment_id"] == "S1"


def test_two_partition_query_prefers_todays_fresher_record(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    yesterday = NOW - timedelta(days=1)
    older_time = yesterday.replace(hour=23, minute=0)
    newer_time = NOW

    store.write_records(
        [_record(segment_id="S1", published_time_utc=older_time, condition="Heavy")],
        polled_at_utc=yesterday,
    )
    store.write_records(
        [_record(segment_id="S1", published_time_utc=newer_time, condition="Light")],
        polled_at_utc=NOW,
    )
    store.close()

    response = client.get("/v1/segments")
    body = response.json()
    assert len(body) == 1
    assert body[0]["condition"] == "Light"
    assert body[0]["published_time_utc"] == newer_time.isoformat()


def test_data_substitution_tier_matches_quality_module_across_boundaries(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    store.write_records(
        [
            _record(segment_id="S0", data_substitution=0),
            _record(segment_id="S50", data_substitution=50),
            _record(segment_id="S51", data_substitution=51),
        ],
        polled_at_utc=NOW,
    )
    store.close()

    response = client.get("/v1/segments")
    body = {row["segment_id"]: row for row in response.json()}

    assert body["S0"]["data_substitution_tier"] == substitution_tier(0).value
    assert body["S50"]["data_substitution_tier"] == substitution_tier(50).value
    assert body["S51"]["data_substitution_tier"] == substitution_tier(51).value
    assert body["S0"]["data_substitution_tier"] == SubstitutionTier.MEASURED.value
    assert body["S50"]["data_substitution_tier"] == SubstitutionTier.PARTIALLY_INTERPOLATED.value
    assert body["S51"]["data_substitution_tier"] == SubstitutionTier.MAJORITY_INTERPOLATED.value


def test_geometry_status_round_trips_non_available_value(tmp_path):
    client, data_dir, _ = _make_client(tmp_path)
    store = HistoryStore(data_dir=data_dir)
    store.write_records(
        [_record(segment_id="S1", geometry_status=GeometryStatus.NEVER_AVAILABLE, geometry=None)],
        polled_at_utc=NOW,
    )
    store.close()

    response = client.get("/v1/segments/S1")
    assert response.json()["geometry_status"] == GeometryStatus.NEVER_AVAILABLE.value


def test_status_ok_when_circuit_not_tripped(tmp_path):
    client, _, status_db_path = _make_client(tmp_path)
    status_store = StatusStore(db_path=status_db_path)
    status_store.write_status(
        consecutive_failures=0,
        circuit_tripped=False,
        traffic_baseline_stable=True,
        gis_baseline_stable=True,
        now=NOW,
    )

    response = client.get("/v1/status")
    body = response.json()
    assert body["poller_status"] == "ok"
    assert body["segment_baseline_stable"] is True
    assert body["consecutive_failures"] == 0


def test_status_degraded_when_circuit_tripped(tmp_path):
    client, _, status_db_path = _make_client(tmp_path)
    status_store = StatusStore(db_path=status_db_path)
    status_store.write_status(
        consecutive_failures=3,
        circuit_tripped=True,
        traffic_baseline_stable=True,
        gis_baseline_stable=True,
        now=NOW,
    )

    response = client.get("/v1/status")
    body = response.json()
    assert body["poller_status"] == "degraded"
    assert body["consecutive_failures"] == 3


def test_status_baseline_unstable_when_traffic_baseline_drifted(tmp_path):
    client, _, status_db_path = _make_client(tmp_path)
    status_store = StatusStore(db_path=status_db_path)
    status_store.write_status(
        consecutive_failures=0,
        circuit_tripped=False,
        traffic_baseline_stable=False,
        gis_baseline_stable=None,
        now=NOW,
    )

    response = client.get("/v1/status")
    assert response.json()["segment_baseline_stable"] is False


def test_status_baseline_stable_when_gis_not_yet_checked(tmp_path):
    client, _, status_db_path = _make_client(tmp_path)
    status_store = StatusStore(db_path=status_db_path)
    status_store.write_status(
        consecutive_failures=0,
        circuit_tripped=False,
        traffic_baseline_stable=True,
        gis_baseline_stable=None,
        now=NOW,
    )

    response = client.get("/v1/status")
    assert response.json()["segment_baseline_stable"] is True


def test_status_default_when_no_row_exists(tmp_path):
    client, _, _ = _make_client(tmp_path)

    response = client.get("/v1/status")
    body = response.json()
    assert body["poller_status"] == "unknown"
    assert body["consecutive_failures"] is None


def test_rate_limit_rejects_after_limit(tmp_path):
    client, data_dir, _ = _make_client(tmp_path, rate_limit="3/minute")
    store = HistoryStore(data_dir=data_dir)
    store.write_records([_record()], polled_at_utc=NOW)
    store.close()

    responses = [client.get("/v1/segments") for _ in range(4)]
    assert [r.status_code for r in responses[:3]] == [200, 200, 200]
    assert responses[3].status_code == 429


def test_cors_reflects_configured_origin(tmp_path):
    client, data_dir, _ = _make_client(tmp_path, frontend_origin="https://frontend.example.invalid")
    store = HistoryStore(data_dir=data_dir)
    store.write_records([_record()], polled_at_utc=NOW)
    store.close()

    response = client.get("/v1/segments", headers={"Origin": "https://frontend.example.invalid"})
    assert response.headers.get("access-control-allow-origin") == "https://frontend.example.invalid"


def test_cors_does_not_reflect_unconfigured_origin(tmp_path):
    client, data_dir, _ = _make_client(tmp_path, frontend_origin="https://frontend.example.invalid")
    store = HistoryStore(data_dir=data_dir)
    store.write_records([_record()], polled_at_utc=NOW)
    store.close()

    response = client.get("/v1/segments", headers={"Origin": "https://evil.example.invalid"})
    assert "access-control-allow-origin" not in response.headers
