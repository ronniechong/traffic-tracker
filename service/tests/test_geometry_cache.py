from traffictracker.geometry_cache import LastKnownGeometryCache


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
