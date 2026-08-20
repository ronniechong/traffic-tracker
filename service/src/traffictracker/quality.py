"""Data-quality classification for freeway segments.

Tier boundaries and the staleness threshold are provisional, based on a
short sample window — both are due for re-validation against a longer,
representative window before being treated as final.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

STALENESS_THRESHOLD_SECONDS = 240  # 2x the measured ~120s cadence


class SubstitutionTier(str, Enum):
    MEASURED = "measured"
    PARTIALLY_INTERPOLATED = "partially_interpolated"
    MAJORITY_INTERPOLATED = "majority_interpolated"


def substitution_tier(data_substitution: float | None) -> SubstitutionTier:
    """Classifies a segment's `dataSubstitution` percentage (0-100).

    A `None` value is treated as fully measured (0) rather than raising —
    a missing value hasn't been observed on a real record, but a
    defensive caller shouldn't crash on it either.
    """
    value = data_substitution or 0.0
    if value <= 0:
        return SubstitutionTier.MEASURED
    if value <= 50:
        return SubstitutionTier.PARTIALLY_INTERPOLATED
    return SubstitutionTier.MAJORITY_INTERPOLATED


def is_stale(
    published_time_utc: datetime,
    now: datetime | None = None,
    threshold_seconds: int = STALENESS_THRESHOLD_SECONDS,
) -> bool:
    """A single global threshold, not per-segment — the upstream's publish
    cadence is uniform across all segments."""
    reference = now or datetime.now(timezone.utc)
    age = (reference - published_time_utc).total_seconds()
    return age > threshold_seconds
