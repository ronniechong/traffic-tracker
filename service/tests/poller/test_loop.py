import asyncio
import json
from datetime import datetime, timezone

import httpx

from traffictracker.gateway.client import GatewayClient, RateLimiter
from traffictracker.geometry_cache import GisGeometryCache, LastKnownGeometryCache
from traffictracker.poller.loop import poll_gis, poll_once, run_poll_loop

NOW = datetime(2026, 8, 20, 4, 15, 0, tzinfo=timezone.utc)


def _feature(segment_id: str):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[144.0, -37.0]]},
        "properties": {
            "id": segment_id,
            "freewayName": "Monash Fwy",
            "segmentName": "test",
            "direction": "Outbound",
            "publishedTime": "2026-08-20T14:14:00.032+10:00",
            "condition": "Light",
            "dataSubstitution": 0,
            "hasOverride": False,
        },
    }


def _client_with_response(body: dict, rate_limiter: RateLimiter | None = None) -> GatewayClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = GatewayClient(
        api_key="fake",
        base_url_override="https://example.invalid",
        rate_limiter=rate_limiter or RateLimiter(min_interval_seconds=0.0),
    )
    client._client = httpx.AsyncClient(transport=transport)
    return client


async def test_poll_once_normalizes_traffic_features():
    body = {"features": [_feature("seg-1"), _feature("seg-2")]}
    client = _client_with_response(body)
    cache = LastKnownGeometryCache()
    gis_cache = GisGeometryCache()

    records, traffic_baseline_stable = await poll_once(client, cache, gis_cache, now=NOW)

    assert len(records) == 2
    assert {r.segment_id for r in records} == {"seg-1", "seg-2"}
    assert traffic_baseline_stable is False  # only 2 segments, baseline expects 226


async def test_poll_gis_updates_geometry_cache_and_baseline():
    body = {"features": [_feature("seg-1")]}
    client = _client_with_response(body)
    gis_cache = GisGeometryCache()

    gis_baseline_stable = await poll_gis(client, gis_cache)

    assert gis_cache.polled_at_least_once
    assert gis_cache.geometry_for("seg-1") == _feature("seg-1")["geometry"]
    assert gis_baseline_stable is False  # only 1 segment, baseline expects 246


async def test_run_poll_loop_calls_on_poll_and_stops():
    body = {"features": [_feature("seg-1")]}
    client = _client_with_response(body)

    calls = []

    async def on_poll(records):
        calls.append(records)

    stop_event = asyncio.Event()

    async def stop_after_first():
        while not calls:
            await asyncio.sleep(0.01)
        stop_event.set()

    await asyncio.gather(
        run_poll_loop(client, on_poll, stop_event=stop_event),
        stop_after_first(),
    )

    assert len(calls) == 1
    assert calls[0][0].segment_id == "seg-1"


async def test_run_poll_loop_calls_on_status_on_success():
    body = {"features": [_feature("seg-1")]}
    client = _client_with_response(body)

    status_calls = []

    async def on_poll(records):
        pass

    async def on_status(snapshot):
        status_calls.append(snapshot)

    stop_event = asyncio.Event()

    async def stop_after_first():
        while not status_calls:
            await asyncio.sleep(0.01)
        stop_event.set()

    await asyncio.gather(
        run_poll_loop(client, on_poll, stop_event=stop_event, on_status=on_status),
        stop_after_first(),
    )

    assert len(status_calls) == 1
    snapshot = status_calls[0]
    assert snapshot.consecutive_failures == 0
    assert snapshot.circuit_tripped is False
    assert snapshot.traffic_baseline_stable is False  # only 1 segment vs 226 baseline
    assert snapshot.gis_baseline_stable is False  # only 1 segment vs 246 baseline


async def test_run_poll_loop_calls_on_status_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = GatewayClient(
        api_key="fake",
        base_url_override="https://example.invalid",
        rate_limiter=RateLimiter(min_interval_seconds=0.0),
    )
    client._client = httpx.AsyncClient(transport=transport)

    status_calls = []

    async def on_poll(records):
        pass

    async def on_status(snapshot):
        status_calls.append(snapshot)

    stop_event = asyncio.Event()

    async def stop_after_first():
        while not status_calls:
            await asyncio.sleep(0.01)
        stop_event.set()

    await asyncio.gather(
        run_poll_loop(client, on_poll, stop_event=stop_event, on_status=on_status),
        stop_after_first(),
    )

    assert len(status_calls) == 1
    snapshot = status_calls[0]
    assert snapshot.consecutive_failures == 1
    assert snapshot.circuit_tripped is False
