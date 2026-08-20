from datetime import datetime, timezone

from traffictracker.geometry_cache import LastKnownGeometryCache
from traffictracker.models import normalize_feature
from traffictracker.quality import SubstitutionTier

NOW = datetime(2026, 8, 20, 4, 15, 0, tzinfo=timezone.utc)


def make_feature(**overrides):
    props = {
        "id": "Streams:897723",
        "freewayName": "West Gate Fwy",
        "segmentName": "Kingsway to Montague St",
        "direction": "Outbound",
        "publishedTime": "2026-08-20T14:14:00.032+10:00",
        "condition": "Heavy",
        "dataSubstitution": 27.35,
        "hasOverride": False,
    }
    props.update(overrides)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[144.0, -37.0]]},
        "properties": props,
    }


def test_normalizes_a_typical_feature():
    cache = LastKnownGeometryCache()
    record = normalize_feature(make_feature(), cache, now=NOW)

    assert record.segment_id == "Streams:897723"
    assert record.published_time_utc == datetime(2026, 8, 20, 4, 14, 0, 32000, tzinfo=timezone.utc)
    assert record.substitution_tier == SubstitutionTier.PARTIALLY_INTERPOLATED
    assert record.stale is False
    assert record.geometry_is_fallback is False
    assert record.has_override is False
    assert record.override_raw["overrideStartTime"] is None


def test_falls_back_to_cached_geometry_on_null():
    cache = LastKnownGeometryCache()
    normalize_feature(make_feature(), cache, now=NOW)

    feature_without_geometry = make_feature()
    feature_without_geometry["geometry"] = None
    record = normalize_feature(feature_without_geometry, cache, now=NOW)

    assert record.geometry is not None
    assert record.geometry_is_fallback is True
