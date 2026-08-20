"""Two-tier poll-failure handling.

A single failure is routine — log it, skip the cycle, retry next tick, no
alert. Consecutive failures past a threshold means the upstream is likely
down, not a blip, and should alert promptly. The 3-consecutive threshold is
a starting value, not validated against real production failure patterns.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CONSECUTIVE_FAILURE_ALERT_THRESHOLD = 3


class FailureTracker:
    def __init__(self, alert_threshold: int = CONSECUTIVE_FAILURE_ALERT_THRESHOLD):
        self._alert_threshold = alert_threshold
        self._consecutive_failures = 0
        self._circuit_tripped = False

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def circuit_tripped(self) -> bool:
        return self._circuit_tripped

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_tripped = False

    def record_failure(self, error: Exception) -> bool:
        """Returns True if this failure just tripped the circuit breaker."""
        self._consecutive_failures += 1
        logger.warning(
            "poll failed (consecutive=%d): %s", self._consecutive_failures, error
        )
        if self._consecutive_failures >= self._alert_threshold and not self._circuit_tripped:
            self._circuit_tripped = True
            logger.error(
                "circuit breaker tripped: %d consecutive poll failures",
                self._consecutive_failures,
            )
            return True
        return False
