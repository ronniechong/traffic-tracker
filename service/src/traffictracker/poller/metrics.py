"""Poller design-gate metrics.

Bound internal-only (localhost / internal Docker network) — never through
public ingress, matching security invariant #4 (API binds localhost, the
reverse proxy is the only ingress). Public exposure/CORS is handled
elsewhere; this module only defines and serves the metrics themselves.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, start_http_server

DATA_SUBSTITUTION_NONZERO_RATIO = Gauge(
    "traffictracker_data_substitution_nonzero_ratio",
    "Fraction of segments with dataSubstitution > 0 in the latest poll",
)
NULL_GEOMETRY_RATIO = Gauge(
    "traffictracker_null_geometry_ratio",
    "Fraction of segments with null geometry in the latest poll",
)
POLL_SUCCESS_TOTAL = Counter(
    "traffictracker_poll_success_total", "Total successful polls"
)
POLL_FAILURE_TOTAL = Counter(
    "traffictracker_poll_failure_total", "Total failed polls"
)
CONSECUTIVE_FAILURES = Gauge(
    "traffictracker_consecutive_failures",
    "Current consecutive poll failure count",
)
RATE_LIMITER_HEADROOM_SECONDS = Gauge(
    "traffictracker_rate_limiter_headroom_seconds",
    "Seconds of headroom remaining before the next call is permitted by the rate limiter",
)


def serve_metrics(host: str = "127.0.0.1", port: int = 9109) -> None:
    start_http_server(port, addr=host)


def record_poll_result(records_total: int, substitution_nonzero: int, null_geometry: int) -> None:
    POLL_SUCCESS_TOTAL.inc()
    if records_total == 0:
        return
    DATA_SUBSTITUTION_NONZERO_RATIO.set(substitution_nonzero / records_total)
    NULL_GEOMETRY_RATIO.set(null_geometry / records_total)


def record_poll_failure() -> None:
    POLL_FAILURE_TOTAL.inc()
