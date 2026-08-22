"""Normalizes raw `/traffic` GeoJSON features into internal records.

hasOverride's four linked fields (overrideStartTime, overrideEndTime,
messageRequested, maxEndTime) are handled purely defensively — they have
never been observed populated on a live record, so their real shape is
unverified. They are passed through as opaque, optional values; nothing
here assumes a shape it hasn't seen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from traffictracker.geometry_cache import (
    GeometryStatus,
    GisGeometryCache,
    LastKnownGeometryCache,
    resolve_geometry_status,
)
from traffictracker.quality import SubstitutionTier, is_stale, substitution_tier
from traffictracker.timeutil import parse_published_time_to_utc


@dataclass(frozen=True)
class SegmentRecord:
    segment_id: str
    freeway_name: str
    segment_name: str
    direction: str
    condition: str | None
    data_substitution: float | None
    substitution_tier: SubstitutionTier
    published_time_utc: datetime
    stale: bool
    geometry: dict[str, Any] | None
    geometry_status: GeometryStatus
    has_override: bool
    override_raw: dict[str, Any | None]


def normalize_feature(
    feature: dict[str, Any],
    geometry_cache: LastKnownGeometryCache,
    gis_geometry_cache: GisGeometryCache,
    now: datetime | None = None,
) -> SegmentRecord:
    props = feature["properties"]
    segment_id = props["id"]

    raw_geometry = feature.get("geometry")
    resolved_geometry, geometry_status = resolve_geometry_status(
        segment_id, raw_geometry, geometry_cache, gis_geometry_cache
    )

    published_time_utc = parse_published_time_to_utc(props["publishedTime"])

    return SegmentRecord(
        segment_id=segment_id,
        freeway_name=props["freewayName"],
        segment_name=props["segmentName"],
        direction=props["direction"],
        condition=props.get("condition"),
        data_substitution=props.get("dataSubstitution"),
        substitution_tier=substitution_tier(props.get("dataSubstitution")),
        published_time_utc=published_time_utc,
        stale=is_stale(published_time_utc, now=now),
        geometry=resolved_geometry,
        geometry_status=geometry_status,
        has_override=bool(props.get("hasOverride")),
        override_raw={
            "overrideStartTime": props.get("overrideStartTime"),
            "overrideEndTime": props.get("overrideEndTime"),
            "messageRequested": props.get("messageRequested"),
            "maxEndTime": props.get("maxEndTime"),
        },
    )
