"""Sizing-only soak harness: runs the real poll loop and appends one JSON
line per poll with lightweight stats (record count, raw payload bytes,
substitution/null-geometry rates). Deliberately not the real storage
layer — this only exists to gather sizing data ahead of finalizing the
storage schema.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from pathlib import Path

from traffictracker.gateway.client import GatewayClient
from traffictracker.poller.loop import run_poll_loop
from traffictracker.quality import SubstitutionTier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "soak" / "soak.jsonl"


async def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    async def on_poll(records):
        substitution_nonzero = sum(
            1 for r in records if r.substitution_tier != SubstitutionTier.MEASURED
        )
        null_geometry = sum(1 for r in records if r.geometry is None)
        stale = sum(1 for r in records if r.stale)

        line = {
            "polled_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "substitution_nonzero": substitution_nonzero,
            "null_geometry": null_geometry,
            "stale": stale,
        }
        with OUTPUT_PATH.open("a") as f:
            f.write(json.dumps(line) + "\n")

    async with GatewayClient() as client:
        await run_poll_loop(client, on_poll, stop_event=stop_event)


if __name__ == "__main__":
    asyncio.run(main())
