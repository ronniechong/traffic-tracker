from traffictracker.geometry_cache import (
    GeometryStatus,
    GisGeometryCache,
    LastKnownGeometryCache,
    resolve_geometry_status,
)


def test_returns_live_geometry_and_caches_it():
    cache = LastKnownGeometryCache()
    geometry = {"type": "LineString", "coordinates": [[1, 2]]}
    assert cache.resolve("seg-1", geometry) == geometry
    assert len(cache) == 1


def test_falls_back_to_last_known_when_null():
    cache = LastKnownGeometryCache()
    geometry = {"type": "LineString", "coordinates": [[1, 2]]}
    cache.resolve("seg-1", geometry)
    assert cache.resolve("seg-1", None) == geometry


def test_returns_none_when_never_seen():
    cache = LastKnownGeometryCache()
    assert cache.resolve("seg-unknown", None) is None


def test_resolve_status_available_when_traffic_has_geometry():
    geometry = {"type": "LineString", "coordinates": [[1, 2]]}
    resolved, status = resolve_geometry_status(
        "seg-1", geometry, LastKnownGeometryCache(), GisGeometryCache()
    )
    assert resolved == geometry
    assert status == GeometryStatus.AVAILABLE


def test_resolve_status_stale_fallback_from_last_known_good():
    geometry = {"type": "LineString", "coordinates": [[1, 2]]}
    lkg = LastKnownGeometryCache()
    gis = GisGeometryCache()
    resolve_geometry_status("seg-1", geometry, lkg, gis)

    resolved, status = resolve_geometry_status("seg-1", None, lkg, gis)
    assert resolved == geometry
    assert status == GeometryStatus.STALE_FALLBACK


def test_resolve_status_pending_before_first_gis_poll():
    resolved, status = resolve_geometry_status(
        "seg-1", None, LastKnownGeometryCache(), GisGeometryCache()
    )
    assert resolved is None
    assert status == GeometryStatus.PENDING


def test_resolve_status_never_available_when_gis_also_null():
    gis = GisGeometryCache()
    gis.record_poll({"seg-1": None})

    resolved, status = resolve_geometry_status("seg-1", None, LastKnownGeometryCache(), gis)
    assert resolved is None
    assert status == GeometryStatus.NEVER_AVAILABLE


def test_resolve_status_stale_fallback_when_gis_has_geometry_traffic_does_not():
    geometry = {"type": "LineString", "coordinates": [[9, 9]]}
    gis = GisGeometryCache()
    gis.record_poll({"seg-1": geometry})

    resolved, status = resolve_geometry_status("seg-1", None, LastKnownGeometryCache(), gis)
    assert resolved == geometry
    assert status == GeometryStatus.STALE_FALLBACK
