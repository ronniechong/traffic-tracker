import logging

from traffictracker.poller.baseline import check_segment_baseline


def test_no_warning_at_baseline(caplog):
    with caplog.at_level(logging.WARNING):
        check_segment_baseline(
            segment_ids={f"seg-{i}" for i in range(226)},
            freeway_names={f"fwy-{i}" for i in range(12)},
        )
    assert caplog.records == []


def test_warns_on_segment_count_drift(caplog):
    with caplog.at_level(logging.WARNING):
        check_segment_baseline(
            segment_ids={f"seg-{i}" for i in range(200)},
            freeway_names={f"fwy-{i}" for i in range(12)},
        )
    assert any("segment count drifted" in r.message for r in caplog.records)
