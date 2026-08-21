"""The real poll loop: `python -m traffictracker.poller`.

Runs forever (until SIGINT/SIGTERM), storing every poll to the day-partitioned
history store and serving `/metrics` internally. The public API (M03) is a
separate, not-yet-built concern — this process only polls and persists.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from traffictracker.gateway.client import GatewayClient
from traffictracker.poller.loop import run_poll_loop
from traffictracker.poller.metrics import serve_metrics
from traffictracker.storage import HistoryStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

METRICS_HOST = "127.0.0.1"
METRICS_PORT = 9109


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    history = HistoryStore()
    serve_metrics(host=METRICS_HOST, port=METRICS_PORT)

    async def on_poll(records):
        history.write_records(records)

    logger.info("poller starting (metrics on %s:%d, internal-only)", METRICS_HOST, METRICS_PORT)
    async with GatewayClient() as client:
        await run_poll_loop(client, on_poll, stop_event=stop_event)

    history.close()
    logger.info("poller stopped")


if __name__ == "__main__":
    asyncio.run(main())
