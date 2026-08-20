from traffictracker.poller.failures import FailureTracker


def test_single_failure_does_not_trip():
    tracker = FailureTracker(alert_threshold=3)
    tripped = tracker.record_failure(RuntimeError("boom"))
    assert tripped is False
    assert tracker.consecutive_failures == 1
    assert tracker.circuit_tripped is False


def test_trips_at_threshold():
    tracker = FailureTracker(alert_threshold=3)
    tracker.record_failure(RuntimeError("1"))
    tracker.record_failure(RuntimeError("2"))
    tripped = tracker.record_failure(RuntimeError("3"))
    assert tripped is True
    assert tracker.circuit_tripped is True


def test_success_resets():
    tracker = FailureTracker(alert_threshold=3)
    tracker.record_failure(RuntimeError("1"))
    tracker.record_failure(RuntimeError("2"))
    tracker.record_success()
    assert tracker.consecutive_failures == 0
    assert tracker.circuit_tripped is False
