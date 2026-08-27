"""Geometric nearest-line join between live segment geometry and the Speed
Zones dataset: 30m buffer, ranked by overlap length rather than plain
intersection, no direction-aware filtering -- the two datasets' direction
vocabularies don't share a common mapping, and overlap-length ranking
alone is sufficient to pick the correct dominant value. Interchange
fragmentation (many short zone slices) doesn't imply genuine speed-limit
disagreement, so a simple length-weighted-majority aggregation is enough
-- no multi-value data model needed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from traffictracker.speed_limits import SpeedLimitMatch

BUFFER_METERS = 30
# Rough local degrees-per-metre at Melbourne's latitude, used only to size
# the buffer -- not a general-purpose CRS transform.
DEG_PER_METER = 1 / 111_000


class SpeedZoneIndex:
    """Spatial index over the candidate speed-zone features (already
    filtered to a coverage bbox by the caller -- this class does no
    filtering of its own)."""

    def __init__(self, zone_features: Iterable[dict[str, Any]]):
        geoms: list[BaseGeometry] = []
        limits: list[int] = []
        for feature in zone_features:
            geometry = feature.get("geometry")
            if not geometry:
                continue
            try:
                geom = shape(geometry)
            except Exception:
                continue
            if geom.is_empty:
                continue
            limit = feature.get("properties", {}).get("speed_limit")
            if limit is None:
                continue
            geoms.append(geom)
            limits.append(int(limit))

        self._geoms = geoms
        self._limits = limits
        self._tree = STRtree(geoms) if geoms else None

    def __len__(self) -> int:
        return len(self._geoms)

    def match_segment(self, segment_id: str, segment_geometry: dict[str, Any]) -> SpeedLimitMatch | None:
        """Returns the dominant speed-limit match for one segment, or None
        if nothing in the dataset falls inside the match buffer."""
        if self._tree is None:
            return None
        try:
            line = shape(segment_geometry)
        except Exception:
            return None

        buffered = line.buffer(BUFFER_METERS * DEG_PER_METER)
        overlap_by_limit: Counter[int] = Counter()
        matched_zone_count = 0

        for idx in self._tree.query(buffered):
            candidate = self._geoms[idx]
            intersection_length = buffered.intersection(candidate).length
            if intersection_length <= 0:
                continue
            matched_zone_count += 1
            overlap_by_limit[self._limits[idx]] += intersection_length

        if not overlap_by_limit:
            return None

        total_overlap = sum(overlap_by_limit.values())
        dominant_limit, dominant_overlap = max(overlap_by_limit.items(), key=lambda kv: kv[1])

        return SpeedLimitMatch(
            segment_id=segment_id,
            speed_limit_kmh=dominant_limit,
            overlap_ratio=dominant_overlap / total_overlap,
            matched_zone_count=matched_zone_count,
        )
