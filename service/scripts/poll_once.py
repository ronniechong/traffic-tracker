"""Single authenticated poll of both endpoints, from inside the real repo
structure — proves the gateway client works outside the spike repo."""

from __future__ import annotations

import asyncio
import json

from traffictracker.gateway.client import Endpoint, GatewayClient


async def main() -> None:
    async with GatewayClient() as client:
        for endpoint in Endpoint:
            response = await client.fetch(endpoint)
            body = json.loads(response.payload)
            feature_count = len(body.get("features", []))
            print(f"{endpoint.value}: {feature_count} features")


if __name__ == "__main__":
    asyncio.run(main())
