"""Monthly speed-limit reference refresh -- a one-shot job (`docker compose
run --rm`, host-cron scheduled), not part of the always-on poller.

Failure policy (no retry/backoff in v1): any exception here propagates and
exits non-zero. The healthchecks.io dead-man's-switch ping only fires on a
fully successful run, so a download failure, an unreachable host, or an
upstream schema change all trip the same external alert -- the next
scheduled monthly run is the retry, deliberately not anything automatic.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path

import httpx

from traffictracker.poller import healthcheck
from traffictracker.speed_limits import DEFAULT_DB_PATH, SpeedLimitMatch, replace_all
from traffictracker.speedlimit_job.download import (
    DEFAULT_SPEED_ZONES_URL,
    SPEED_ZONES_URL_ENV,
    download,
    stream_filter_to_bbox,
)
from traffictracker.speedlimit_job.join import SpeedZoneIndex
from traffictracker.storage import DEFAULT_DATA_DIR, read_current_segments

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEADMAN_PING_URL_ENV = "TT_SPEEDLIMIT_DEADMAN_PING_URL"

# Loose metro Melbourne bbox (lon_min, lat_min, lon_max, lat_max) -- wide
# enough to comfortably contain all 12 covered freeways.
METRO_BBOX = (144.4, -38.5, 145.6, -37.5)


def run(
    data_dir: Path = DEFAULT_DATA_DIR,
    speed_limits_db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Returns the number of segments matched. Raises on any failure --
    callers must not swallow exceptions, per the no-retry failure policy."""
    t0 = time.monotonic()

    segments = read_current_segments(data_dir=data_dir)
    logger.info("read %d current segments from local storage", len(segments))

    url = os.environ.get(SPEED_ZONES_URL_ENV, DEFAULT_SPEED_ZONES_URL)
    with tempfile.TemporaryDirectory() as tmp:
        download_path = Path(tmp) / "speed_zones.geojson"
        logger.info("downloading speed zones dataset...")
        download(url, download_path)

        logger.info("streaming + filtering to metro bbox...")
        candidates = stream_filter_to_bbox(download_path, METRO_BBOX)
        logger.info("candidate speed zones after bbox filter: %d", len(candidates))

    index = SpeedZoneIndex(candidates)

    matches: list[SpeedLimitMatch] = []
    skipped_no_geometry = 0
    skipped_zero_match = 0

    for segment in segments:
        if segment.geometry_status != "available" or segment.geometry is None:
            skipped_no_geometry += 1
            continue
        match = index.match_segment(segment.segment_id, segment.geometry)
        if match is None:
            skipped_zero_match += 1
            continue
        matches.append(match)

    replace_all(matches, db_path=speed_limits_db_path)

    elapsed = time.monotonic() - t0
    logger.info(
        "done: matched=%d no_geometry=%d zero_match=%d elapsed=%.1fs",
        len(matches),
        skipped_no_geometry,
        skipped_zero_match,
        elapsed,
    )
    return len(matches)


async def _ping_deadman() -> None:
    async with httpx.AsyncClient() as client:
        await healthcheck.ping(client, url=os.environ.get(DEADMAN_PING_URL_ENV))


def main() -> None:
    run()
    # Only reached on success -- an exception above exits non-zero before
    # this, so a failed run never trips a false "alive" signal.
    asyncio.run(_ping_deadman())


if __name__ == "__main__":
    main()
