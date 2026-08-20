import time

import httpx
import pytest

from traffictracker.gateway.client import (
    Endpoint,
    GatewayAuthError,
    GatewayClient,
    GatewayError,
    RateLimiter,
)


def test_missing_api_key_raises():
    with pytest.raises(GatewayError):
        GatewayClient(api_key=None, base_url_override="https://example.invalid")


async def test_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    client = GatewayClient(api_key="fake", base_url_override="https://example.invalid")
    client._client = httpx.AsyncClient(transport=transport)

    with pytest.raises(GatewayAuthError):
        await client.fetch(Endpoint.TRAFFIC)


async def test_fetch_returns_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["KeyId"] == "fake"
        return httpx.Response(200, json={"features": []})

    transport = httpx.MockTransport(handler)
    client = GatewayClient(api_key="fake", base_url_override="https://example.invalid")
    client._client = httpx.AsyncClient(transport=transport)

    response = await client.fetch(Endpoint.GIS)
    assert response.endpoint == Endpoint.GIS
    assert response.payload == b'{"features":[]}'


async def test_rate_limiter_enforces_min_interval():
    limiter = RateLimiter(min_interval_seconds=0.2)
    start = time.monotonic()
    await limiter.wait()
    await limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.2
