"""Segment-set baseline check.

Dynamic add/remove handling is explicitly out of scope for v1 — the segment
set observed via `/traffic` (the endpoint records are actually sourced
from) is assumed static. This only logs a warning on mismatch for
visibility; a warning firing in production is the trigger to actually
scope real handling, not a signal to build it preemptively.

The two endpoints report different feature counts, so this baseline is
226 (matching `/traffic`), not `/gis`'s count — it must match whichever
endpoint is actually the source of the records being checked.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

BASELINE_SEGMENT_COUNT = 226
BASELINE_FREEWAY_COUNT = 12


def check_segment_baseline(segment_ids: set[str], freeway_names: set[str]) -> None:
    if len(segment_ids) != BASELINE_SEGMENT_COUNT:
        logger.warning(
            "segment count drifted from baseline: expected %d, got %d",
            BASELINE_SEGMENT_COUNT,
            len(segment_ids),
        )
    if len(freeway_names) != BASELINE_FREEWAY_COUNT:
        logger.warning(
            "freeway count drifted from baseline: expected %d, got %d",
            BASELINE_FREEWAY_COUNT,
            len(freeway_names),
        )
