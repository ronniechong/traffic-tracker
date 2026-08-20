"""Freeway Travel Time API gateway client.

The ONLY code path allowed to call the upstream VIC open data API (security
invariant #1 — exactly one upstream consumer; no per-user passthrough).

Auth is the `KeyId` header, not the `Ocp-Apim-Subscription-Key` the published
OpenAPI docs claim — verified live against the gateway (that header returns
401, "Failed to find key field: KeyId").
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

API_KEY_ENV = "VIC_TRAFFIC_API_SUBSCRIPTION_KEY"
BASE_URL_ENV = "TT_API_BASE_URL"

DEFAULT_BASE_URL = (
    "https://api.opendata.transport.vic.gov.au/opendata/roads/traffic"
    "/freeway-travel-time/v1"
)

# No observable rate-limit enforcement was found during testing (7 calls in
# ~3s all returned 200, no throttle headers), but the client self-limits
# anyway rather than relying on that leniency continuing. 5/min is the
# conservative choice against the ~120s natural update cadence, which is
# not itself checked here — pacing the *poll loop* to ~120s is a separate
# concern handled elsewhere; this just enforces a hard floor no caller can exceed.
MIN_CALL_INTERVAL_SECONDS = 12.0


class Endpoint(str, Enum):
    TRAFFIC = "traffic"
    GIS = "gis"


class GatewayError(Exception):
    """Base error for gateway failures. Subclasses must never carry a raw
    response body or header value in their message."""


class GatewayAuthError(GatewayError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"gateway rejected credentials (HTTP {status_code})")


@dataclass(frozen=True)
class EndpointResponse:
    endpoint: Endpoint
    payload: bytes


def base_url() -> str:
    return os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)


class RateLimiter:
    """Enforces a minimum spacing between calls, process-wide per client
    instance. Async-safe: concurrent callers queue behind the lock rather
    than racing the clock check."""

    def __init__(self, min_interval_seconds: float = MIN_CALL_INTERVAL_SECONDS):
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._last_call is not None:
                elapsed = now - self._last_call
                remaining = self._min_interval - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_call = time.monotonic()

    def headroom_seconds(self) -> float:
        """Seconds until the next call is permitted without waiting. 0 means
        a call could go immediately."""
        if self._last_call is None:
            return 0.0
        remaining = self._min_interval - (time.monotonic() - self._last_call)
        return max(0.0, remaining)


class GatewayClient:
    """Thin, single-purpose HTTP client for the `/traffic` and `/gis`
    endpoints. Async, since the poll loop shares an event loop with the
    API/SSE server.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url_override: str | None = None,
        timeout: float = 15.0,
        rate_limiter: RateLimiter | None = None,
    ):
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self._api_key:
            raise GatewayError(f"{API_KEY_ENV} is not set")
        self._base_url = base_url_override or base_url()
        self._client = httpx.AsyncClient(timeout=timeout)
        self._rate_limiter = rate_limiter or RateLimiter()

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GatewayClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def fetch(self, endpoint: Endpoint) -> EndpointResponse:
        await self._rate_limiter.wait()

        url = f"{self._base_url}/{endpoint.value}"
        logger.debug("gateway request: GET %s", url)  # never log headers
        response = await self._client.get(url, headers={"KeyId": self._api_key})

        if response.status_code in (401, 403):
            logger.warning(
                "gateway auth rejected (status=%d, endpoint=%s)",
                response.status_code,
                endpoint.value,
            )
            raise GatewayAuthError(response.status_code)
        response.raise_for_status()

        return EndpointResponse(endpoint=endpoint, payload=response.content)
