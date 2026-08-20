"""Time conversion at the ingestion boundary.

The upstream API publishes `publishedTime` in Victorian local time (with a
UTC offset suffix, e.g. `+10:00` or `+11:00` across DST), unlike train-tracker's
GTFS-R feeds which are UTC natively. Every other traffictracker module must
only ever see UTC — conversion happens here, once, at ingestion, not scattered
across callers.
"""

from __future__ import annotations

from datetime import datetime, timezone


def parse_published_time_to_utc(raw: str) -> datetime:
    """Parses an ISO-8601 timestamp with a UTC offset (as published by the
    upstream API) and returns an equivalent timezone-aware UTC datetime.

    Never returns a naive datetime — a naive value here would silently
    reintroduce the local-vs-UTC ambiguity this function exists to remove.
    """
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError(f"published time has no UTC offset, cannot convert safely: {raw!r}")
    return parsed.astimezone(timezone.utc)
