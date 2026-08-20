"""The poll loop: ~120s cadence + jitter, calling the gateway client.

Storage is deliberately NOT wired in here yet — the schema shouldn't be
locked until a real sizing measurement runs against production write
volume. `on_poll` is a callback seam for that to plug into once sized.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from traffictracker.gateway.client import Endpoint, GatewayClient
from traffictracker.geometry_cache import LastKnownGeometryCache
from traffictracker.models import SegmentRecord, normalize_feature
from traffictracker.poller.baseline import check_segment_baseline
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

OnPollCallback = Callable[[list[SegmentRecord]], Awaitable[None]]


def _jittered_interval() -> float:
    jitter = random.uniform(*JITTER_RANGE_SECONDS)
    return POLL_INTERVAL_SECONDS + random.choice([-1, 1]) * jitter


async def poll_once(
    client: GatewayClient,
    geometry_cache: LastKnownGeometryCache,
    now: datetime | None = None,
) -> list[SegmentRecord]:
    """Fetches both endpoints. `/traffic` is normalized into records (it's
    the more complete geometry source); `/gis`'s raw payload is fetched
    for its own state/coverage value but not otherwise processed here."""
    traffic_response = await client.fetch(Endpoint.TRAFFIC)
    await client.fetch(Endpoint.GIS)  # raw storage only, see module docstring

    body = json.loads(traffic_response.payload)
    features = body.get("features", [])

    reference_time = now or datetime.now(timezone.utc)
    records = [normalize_feature(f, geometry_cache, now=reference_time) for f in features]

    check_segment_baseline(
        segment_ids={r.segment_id for r in records},
        freeway_names={r.freeway_name for r in records},
    )

    return records


async def run_poll_loop(
    client: GatewayClient,
    on_poll: OnPollCallback,
    stop_event: asyncio.Event | None = None,
) -> None:
    geometry_cache = LastKnownGeometryCache()
    failures = FailureTracker()
    stop_event = stop_event or asyncio.Event()

    while not stop_event.is_set():
        try:
            records = await poll_once(client, geometry_cache)
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

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_jittered_interval())
        except asyncio.TimeoutError:
            pass
