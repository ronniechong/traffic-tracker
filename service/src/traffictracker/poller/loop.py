"""The poll loop: ~120s cadence + jitter for `/traffic`, calling the
gateway client.

`/gis` is polled on its own, much slower cadence (see
`GIS_POLL_INTERVAL_SECONDS`) — it updates roughly every 12h per its own
docs, so polling it every ~120s `/traffic` cycle would burn rate-limiter
budget for near-zero informational gain almost all the time. Its purpose
here is reference data, not a per-cycle feed: cross-checking geometry for
segments `/traffic` never provides it for, and an independent segment-set
baseline check against `/gis`'s own feature count.

Storage is deliberately NOT wired in here yet — the schema shouldn't be
locked until a real sizing measurement runs against production write
volume. `on_poll` is a callback seam for that to plug into once sized.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import httpx

from traffictracker.gateway.client import Endpoint, GatewayClient
from traffictracker.geometry_cache import GisGeometryCache, LastKnownGeometryCache
from traffictracker.models import SegmentRecord, normalize_feature
from traffictracker.poller import healthcheck
from traffictracker.poller.baseline import check_gis_baseline, check_segment_baseline
from traffictracker.poller.failures import FailureTracker
from traffictracker.poller.metrics import (
    CONSECUTIVE_FAILURES,
    RATE_LIMITER_HEADROOM_SECONDS,
    record_poll_failure,
    record_poll_result,
)
from traffictracker.quality import SubstitutionTier

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 120.0
JITTER_RANGE_SECONDS = (5.0, 10.0)

GIS_POLL_INTERVAL_SECONDS = 24 * 60 * 60.0

OnPollCallback = Callable[[list[SegmentRecord]], Awaitable[None]]


def _jittered_interval() -> float:
    jitter = random.uniform(*JITTER_RANGE_SECONDS)
    return POLL_INTERVAL_SECONDS + random.choice([-1, 1]) * jitter


async def poll_gis(client: GatewayClient, gis_geometry_cache: GisGeometryCache) -> None:
    """Fetches `/gis`, updates the geometry cross-check cache, and runs
    `/gis`'s own independent segment-set baseline check. Failures are
    logged and left for the next scheduled `/gis` poll to retry — this is
    reference data, not on the critical path for any single `/traffic`
    cycle."""
    response = await client.fetch(Endpoint.GIS)
    body = json.loads(response.payload)
    features = body.get("features", [])

    geometry_by_segment = {f["properties"]["id"]: f.get("geometry") for f in features}
    gis_geometry_cache.record_poll(geometry_by_segment)

    check_gis_baseline(
        segment_ids={f["properties"]["id"] for f in features},
        freeway_names={f["properties"]["freewayName"] for f in features},
    )


async def poll_once(
    client: GatewayClient,
    geometry_cache: LastKnownGeometryCache,
    gis_geometry_cache: GisGeometryCache,
    now: datetime | None = None,
) -> list[SegmentRecord]:
    """`/traffic` is the more complete geometry source and the only one
    normalized into records every cycle; `/gis` is polled separately, on
    its own cadence (see `poll_gis`)."""
    traffic_response = await client.fetch(Endpoint.TRAFFIC)

    body = json.loads(traffic_response.payload)
    features = body.get("features", [])

    reference_time = now or datetime.now(timezone.utc)
    records = [
        normalize_feature(f, geometry_cache, gis_geometry_cache, now=reference_time)
        for f in features
    ]

    check_segment_baseline(
        segment_ids={r.segment_id for r in records},
        freeway_names={r.freeway_name for r in records},
    )

    return records


async def run_poll_loop(
    client: GatewayClient,
    on_poll: OnPollCallback,
    stop_event: asyncio.Event | None = None,
    healthcheck_client: httpx.AsyncClient | None = None,
) -> None:
    geometry_cache = LastKnownGeometryCache()
    gis_geometry_cache = GisGeometryCache()
    failures = FailureTracker()
    stop_event = stop_event or asyncio.Event()
    healthcheck_client = healthcheck_client or httpx.AsyncClient()

    next_gis_poll_at = 0.0  # due immediately on startup (bootstrap)

    while not stop_event.is_set():
        if time.monotonic() >= next_gis_poll_at:
            try:
                await poll_gis(client, gis_geometry_cache)
            except Exception as error:  # noqa: BLE001 - /gis failures must not crash the loop
                logger.warning("/gis poll failed, will retry next cycle: %s", error)
            else:
                next_gis_poll_at = time.monotonic() + GIS_POLL_INTERVAL_SECONDS

        try:
            records = await poll_once(client, geometry_cache, gis_geometry_cache)
        except Exception as error:  # noqa: BLE001 - poll failures must not crash the loop
            failures.record_failure(error)
            record_poll_failure()
            CONSECUTIVE_FAILURES.set(failures.consecutive_failures)
        else:
            failures.record_success()
            CONSECUTIVE_FAILURES.set(0)
            substitution_nonzero = sum(
                1 for r in records if r.substitution_tier != SubstitutionTier.MEASURED
            )
            null_geometry = sum(1 for r in records if r.geometry is None)
            record_poll_result(len(records), substitution_nonzero, null_geometry)
            RATE_LIMITER_HEADROOM_SECONDS.set(client.rate_limiter.headroom_seconds())
            await on_poll(records)
            await healthcheck.ping(healthcheck_client)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_jittered_interval())
        except asyncio.TimeoutError:
            pass
