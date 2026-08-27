"""Streaming download + bbox filter of the Speed Zones dataset.

The file has no attribute to pre-filter on -- every feature carries only
`speed_limit`, `zone_length`, `zone_conditions`, `direction`, no road
name/route field -- so extraction is geometry-first against the whole
~454MB file.
Streamed with `ijson` rather than loaded fully into memory, and downloaded
to a temp path that's always removed afterward, success or failure --
nothing from this multi-hundred-MB download is meant to outlive one run.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import ijson

logger = logging.getLogger(__name__)

SPEED_ZONES_URL_ENV = "TT_SPEED_ZONES_URL"
DEFAULT_SPEED_ZONES_URL = (
    "https://opendata.transport.vic.gov.au/dataset/975b80b9-e530-46e2-80a5-"
    "54002765e81a/resource/96d4309f-30a2-4ed9-ba66-5dfbd3a959c7/download/"
    "speed_zones_july_2026.geojson"
)


def download(url: str, dest: Path, timeout: float = 600.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)


def _flat_coordinates(geometry: dict[str, Any]) -> Iterator[tuple[float, float]]:
    coords = geometry.get("coordinates", [])
    if geometry.get("type") == "MultiLineString":
        for line in coords:
            yield from line
    else:
        yield from coords


def bbox_hit(geometry: dict[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    lon_min, lat_min, lon_max, lat_max = bbox
    for lon, lat in _flat_coordinates(geometry):
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return True
    return False


def stream_filter_to_bbox(
    geojson_path: Path, bbox: tuple[float, float, float, float]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    with open(geojson_path, "rb") as f:
        for feature in ijson.items(f, "features.item"):
            geometry = feature.get("geometry")
            if geometry and bbox_hit(geometry, bbox):
                candidates.append(feature)
    return candidates
