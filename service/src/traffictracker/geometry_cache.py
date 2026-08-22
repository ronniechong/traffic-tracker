"""Geometry resolution: last-known-good caching plus a `/gis` cross-check
for segments that never publish geometry at all.

Two failure modes look identical if you only track "geometry is null right
now": a segment that dropped its geometry for one cycle and will likely
have it again next cycle, versus a segment that has never had geometry on
either endpoint and never will. Only the first is what last-known-good
caching is for. Collapsing both into one falsy state hides the second
case from anything downstream (e.g. a map renderer) that needs to treat
them differently.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class GeometryStatus(str, Enum):
    AVAILABLE = "available"
    STALE_FALLBACK = "stale_fallback"
    PENDING = "pending"
    NEVER_AVAILABLE = "never_available"


class LastKnownGeometryCache:
    def __init__(self) -> None:
        self._geometry: dict[str, dict[str, Any]] = {}

    def resolve(self, segment_id: str, geometry: dict[str, Any] | None) -> dict[str, Any] | None:
        """Returns `geometry` if present, updating the cache; otherwise
        returns the last cached geometry for this segment, if any."""
        if geometry is not None:
            self._geometry[segment_id] = geometry
            return geometry
        return self._geometry.get(segment_id)

    def __len__(self) -> int:
        return len(self._geometry)


class GisGeometryCache:
    """Tracks each segment's geometry as last seen on `/gis`, polled on its
    own slow cadence (see `poller/loop.py`) decoupled from the `/traffic`
    loop -- this is reference data for the rare structural-null case, not
    a per-cycle fallback source (`/gis` has a materially worse null rate
    in aggregate, per M00)."""

    def __init__(self) -> None:
        self._geometry: dict[str, dict[str, Any] | None] = {}

    def record_poll(self, geometry_by_segment: dict[str, dict[str, Any] | None]) -> None:
        self._geometry.update(geometry_by_segment)

    @property
    def polled_at_least_once(self) -> bool:
        return bool(self._geometry)

    def geometry_for(self, segment_id: str) -> dict[str, Any] | None:
        return self._geometry.get(segment_id)


def resolve_geometry_status(
    segment_id: str,
    traffic_geometry: dict[str, Any] | None,
    lkg_cache: LastKnownGeometryCache,
    gis_cache: GisGeometryCache,
) -> tuple[dict[str, Any] | None, GeometryStatus]:
    """Resolves a segment's geometry and classifies why.

    `pending` only occurs before the first `/gis` poll completes (the
    bootstrap window) -- after that, every segment settles permanently
    into available/stale_fallback/never_available, since the segment set
    is static for v1.
    """
    resolved = lkg_cache.resolve(segment_id, traffic_geometry)
    if traffic_geometry is not None:
        return resolved, GeometryStatus.AVAILABLE
    if resolved is not None:
        return resolved, GeometryStatus.STALE_FALLBACK
    if not gis_cache.polled_at_least_once:
        return None, GeometryStatus.PENDING
    gis_geometry = gis_cache.geometry_for(segment_id)
    if gis_geometry is not None:
        lkg_cache.resolve(segment_id, gis_geometry)
        return gis_geometry, GeometryStatus.STALE_FALLBACK
    return None, GeometryStatus.NEVER_AVAILABLE
