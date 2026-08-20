from datetime import timezone

import pytest

from traffictracker.timeutil import parse_published_time_to_utc


def test_converts_local_offset_to_utc():
    result = parse_published_time_to_utc("2026-08-20T14:14:00.032+10:00")
    assert result.tzinfo == timezone.utc
    assert result.hour == 4
    assert result.minute == 14


def test_rejects_naive_timestamp():
    with pytest.raises(ValueError):
        parse_published_time_to_utc("2026-08-20T14:14:00.032")
