"""The real poll loop: `python -m traffictracker.poller`.

Runs forever (until SIGINT/SIGTERM), storing every poll to the day-partitioned
history store and serving `/metrics` internally. The public API is a separate
process that only reads from storage — this process only polls and persists.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from traffictracker.gateway.client import GatewayClient
from traffictracker.poller.loop import run_poll_loop
from traffictracker.poller.metrics import serve_metrics
from traffictracker.status_store import StatusStore
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
    status_store = StatusStore()
    serve_metrics(host=METRICS_HOST, port=METRICS_PORT)

    async def on_poll(records):
        history.write_records(records)

    async def on_status(snapshot):
        status_store.write_status(
            consecutive_failures=snapshot.consecutive_failures,
            circuit_tripped=snapshot.circuit_tripped,
            traffic_baseline_stable=snapshot.traffic_baseline_stable,
            gis_baseline_stable=snapshot.gis_baseline_stable,
        )

    logger.info("poller starting (metrics on %s:%d, internal-only)", METRICS_HOST, METRICS_PORT)
    async with GatewayClient() as client:
        await run_poll_loop(client, on_poll, stop_event=stop_event, on_status=on_status)

    history.close()
    logger.info("poller stopped")


if __name__ == "__main__":
    asyncio.run(main())
