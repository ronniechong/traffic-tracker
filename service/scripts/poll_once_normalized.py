"""Manual smoke check: one real poll through the normalization path."""

from __future__ import annotations

import asyncio
from collections import Counter

from traffictracker.gateway.client import GatewayClient
from traffictracker.geometry_cache import GisGeometryCache, LastKnownGeometryCache
from traffictracker.poller.loop import poll_once


async def main() -> None:
    cache = LastKnownGeometryCache()
    gis_cache = GisGeometryCache()
    async with GatewayClient() as client:
        records, _ = await poll_once(client, cache, gis_cache)

    print(f"{len(records)} segments normalized")
    print("tiers:", Counter(r.substitution_tier.value for r in records))
    print("null geometry:", sum(1 for r in records if r.geometry is None))
    print("stale:", sum(1 for r in records if r.stale))
    print("sample:", records[0])


if __name__ == "__main__":
    asyncio.run(main())
