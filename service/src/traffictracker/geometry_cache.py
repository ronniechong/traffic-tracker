"""Last-known-good geometry cache for segments with null geometry.

`/gis` has a materially worse null-geometry rate than `/traffic`, so it
isn't a reliable cross-endpoint fallback — the fallback here is instead
each segment's own last successfully observed geometry.
"""

from __future__ import annotations

from typing import Any


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
