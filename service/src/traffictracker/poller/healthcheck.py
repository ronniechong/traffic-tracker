"""External dead-man's-switch ping — outside confirmation that the poller
is alive at all, for when the on-box stack can't report its own death.

Rung once per fully successful cycle, not on a failed poll — a ping that
fires even during a run of poll failures would defeat the point of having
an external dead-man's switch at all.

The check's own expected interval is configured on the monitoring
service's own dashboard, not in code — it must be set wider than the
in-process circuit breaker's alert window, so a single run of consecutive
failures alone can never trip the external alert too.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

PING_URL_ENV = "TT_DEADMAN_PING_URL"


async def ping(client: httpx.AsyncClient, url: str | None = None) -> bool:
    """Best-effort: a failed or unconfigured dead-man ping must never crash
    the poller, it's a monitoring signal, not a dependency."""
    resolved_url = url or os.environ.get(PING_URL_ENV)
    if not resolved_url:
        logger.debug("%s not set, skipping dead-man ping", PING_URL_ENV)
        return False
    try:
        response = await client.get(resolved_url, timeout=10.0)
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("dead-man ping failed: %s", exc)
        return False
