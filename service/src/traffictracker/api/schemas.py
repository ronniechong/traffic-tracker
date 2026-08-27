"""Response shapes for the public API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SegmentReading(BaseModel):
    segment_id: str
    freeway_name: str
    segment_name: str
    direction: str
    condition: str | None
    data_substitution: float | None
    data_substitution_tier: str
    published_time_utc: str
    is_stale: bool
    geometry_status: str
    geometry: dict[str, Any] | None
    has_override: bool
    blank_since_utc: str | None
    persistent_blank: bool
    speed_limit_kmh: int | None
    speed_limit_confident: bool | None
    speed_limit_computed_at_utc: str | None


class StatusResponse(BaseModel):
    poller_status: str
    segment_baseline_stable: bool
    consecutive_failures: int | None
    updated_at_utc: str | None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
