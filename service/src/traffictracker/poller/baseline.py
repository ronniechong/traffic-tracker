"""Segment-set baseline checks.

Dynamic add/remove handling is explicitly out of scope for v1 — the segment
set is assumed static. This only logs a warning on mismatch for
visibility; a warning firing in production is the trigger to actually
scope real handling, not a signal to build it preemptively.

The two endpoints report different feature counts, so each gets its own
baseline: 226 for `/traffic` (checked every poll cycle), 246 for `/gis`
(checked on `/gis`'s own slower poll cadence). Checking both independently
means a drift confined to one endpoint's underlying data still gets
caught, rather than only drift visible through whichever endpoint records
happen to be sourced from.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

BASELINE_SEGMENT_COUNT = 226
BASELINE_FREEWAY_COUNT = 12

GIS_BASELINE_SEGMENT_COUNT = 246
GIS_BASELINE_FREEWAY_COUNT = 12


def check_segment_baseline(segment_ids: set[str], freeway_names: set[str]) -> bool:
    stable = True
    if len(segment_ids) != BASELINE_SEGMENT_COUNT:
        logger.warning(
            "segment count drifted from baseline: expected %d, got %d",
            BASELINE_SEGMENT_COUNT,
            len(segment_ids),
        )
        stable = False
    if len(freeway_names) != BASELINE_FREEWAY_COUNT:
        logger.warning(
            "freeway count drifted from baseline: expected %d, got %d",
            BASELINE_FREEWAY_COUNT,
            len(freeway_names),
        )
        stable = False
    return stable


def check_gis_baseline(segment_ids: set[str], freeway_names: set[str]) -> bool:
    stable = True
    if len(segment_ids) != GIS_BASELINE_SEGMENT_COUNT:
        logger.warning(
            "/gis segment count drifted from baseline: expected %d, got %d",
            GIS_BASELINE_SEGMENT_COUNT,
            len(segment_ids),
        )
        stable = False
    if len(freeway_names) != GIS_BASELINE_FREEWAY_COUNT:
        logger.warning(
            "/gis freeway count drifted from baseline: expected %d, got %d",
            GIS_BASELINE_FREEWAY_COUNT,
            len(freeway_names),
        )
        stable = False
    return stable
