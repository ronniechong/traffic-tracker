"""FastAPI app: read-only public surface over the poller's SQLite storage.

Every route here only ever reads from `HistoryStore`/`StatusStore` -- it
must never import or call the gateway client. The poller process is the
sole upstream consumer.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from traffictracker import quality
from traffictracker.api.schemas import ErrorDetail, ErrorResponse, SegmentReading, StatusResponse
from traffictracker.speed_limits import DEFAULT_DB_PATH as DEFAULT_SPEED_LIMITS_DB_PATH
from traffictracker.speed_limits import read_all as read_speed_limits
from traffictracker.status_store import DEFAULT_STATUS_DB_PATH, StatusStore
from traffictracker.storage import DEFAULT_DATA_DIR, find_blank_since, read_current_segments

FRONTEND_ORIGIN_ENV = "FRONTEND_ORIGIN"
DEFAULT_FRONTEND_ORIGIN = "https://example-placeholder.invalid"

# Provisional: 60 requests/min/IP hasn't been validated against real
# traffic patterns yet, just a conservative starting point.
RATE_LIMIT = "60/minute"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def create_app(
    data_dir: Path = DEFAULT_DATA_DIR,
    status_db_path: Path = DEFAULT_STATUS_DB_PATH,
    speed_limits_db_path: Path = DEFAULT_SPEED_LIMITS_DB_PATH,
    frontend_origin: str | None = None,
    rate_limit: str = RATE_LIMIT,
) -> FastAPI:
    origin = frontend_origin or os.environ.get(FRONTEND_ORIGIN_ENV, DEFAULT_FRONTEND_ORIGIN)
    status_store = StatusStore(db_path=status_db_path)

    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(title="traffic-tracker API")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "error"
        return _error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(422, "invalid_request", "request validation failed")

    def _to_segment_reading(reading, speed_limits: dict) -> SegmentReading:
        # Recomputed at query time (not read from the stored `stale` column)
        # so staleness reflects "as of now", not "as of the poll that wrote
        # this row" -- a reading served minutes after being written should
        # be able to go stale between polls, not just at write time.
        published = datetime.fromisoformat(reading.published_time_utc)
        now = datetime.now(timezone.utc)
        is_stale = quality.is_stale(published, now=now)
        tier = quality.substitution_tier(reading.data_substitution)

        # Only Blank segments need a history walk -- the vast majority of
        # segments never pay this cost.
        blank_since = None
        persistent_blank = False
        if reading.condition == "Blank":
            blank_since = find_blank_since(reading.segment_id, before=published, data_dir=data_dir)
            persistent_blank = quality.is_persistent_blank(blank_since, now=now)

        return SegmentReading(
            segment_id=reading.segment_id,
            freeway_name=reading.freeway_name,
            segment_name=reading.segment_name,
            direction=reading.direction,
            condition=reading.condition,
            data_substitution=reading.data_substitution,
            data_substitution_tier=tier.value,
            published_time_utc=reading.published_time_utc,
            is_stale=is_stale,
            geometry_status=reading.geometry_status,
            geometry=reading.geometry,
            has_override=reading.has_override,
            blank_since_utc=blank_since.isoformat() if blank_since else None,
            persistent_blank=persistent_blank,
            # No reference-table row (zero-match or no-geometry segments)
            # omits the speed-limit line entirely -- never a placeholder
            # implying a value was attempted and failed.
            speed_limit_kmh=speed_limits[reading.segment_id].speed_limit_kmh
            if reading.segment_id in speed_limits
            else None,
            speed_limit_confident=speed_limits[reading.segment_id].confident
            if reading.segment_id in speed_limits
            else None,
            speed_limit_computed_at_utc=speed_limits[reading.segment_id].computed_at_utc
            if reading.segment_id in speed_limits
            else None,
        )

    @app.get("/v1/segments", response_model=list[SegmentReading])
    @limiter.limit(rate_limit)
    async def list_segments(request: Request) -> list[SegmentReading]:
        readings = read_current_segments(data_dir=data_dir)
        speed_limits = read_speed_limits(db_path=speed_limits_db_path)
        return [_to_segment_reading(r, speed_limits) for r in readings]

    @app.get("/v1/segments/{segment_id}", response_model=SegmentReading)
    @limiter.limit(rate_limit)
    async def get_segment(request: Request, segment_id: str) -> SegmentReading:
        readings = read_current_segments(data_dir=data_dir)
        speed_limits = read_speed_limits(db_path=speed_limits_db_path)
        for r in readings:
            if r.segment_id == segment_id:
                return _to_segment_reading(r, speed_limits)
        raise HTTPException(status_code=404, detail=f"unknown segment_id: {segment_id}")

    @app.get("/v1/status", response_model=StatusResponse)
    @limiter.limit(rate_limit)
    async def get_status(request: Request) -> StatusResponse:
        snapshot = status_store.read_status()
        if snapshot is None:
            return StatusResponse(
                poller_status="unknown",
                segment_baseline_stable=True,
                consecutive_failures=None,
                updated_at_utc=None,
            )
        poller_status = "degraded" if snapshot.circuit_tripped else "ok"
        # True unless something has actually been observed unstable: an
        # unchecked baseline (None, on either endpoint) must not read as
        # instability, only a confirmed drift (False) should.
        segment_baseline_stable = (
            snapshot.traffic_baseline_stable is not False
            and snapshot.gis_baseline_stable is not False
        )
        return StatusResponse(
            poller_status=poller_status,
            segment_baseline_stable=segment_baseline_stable,
            consecutive_failures=snapshot.consecutive_failures,
            updated_at_utc=snapshot.updated_at_utc,
        )

    return app
