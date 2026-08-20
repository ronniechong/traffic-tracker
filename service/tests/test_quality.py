from datetime import datetime, timedelta, timezone

from traffictracker.quality import SubstitutionTier, is_stale, substitution_tier


def test_substitution_tier_boundaries():
    assert substitution_tier(0) == SubstitutionTier.MEASURED
    assert substitution_tier(None) == SubstitutionTier.MEASURED
    assert substitution_tier(1) == SubstitutionTier.PARTIALLY_INTERPOLATED
    assert substitution_tier(50) == SubstitutionTier.PARTIALLY_INTERPOLATED
    assert substitution_tier(50.01) == SubstitutionTier.MAJORITY_INTERPOLATED
    assert substitution_tier(100) == SubstitutionTier.MAJORITY_INTERPOLATED


def test_staleness_threshold():
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(seconds=239)
    stale = now - timedelta(seconds=241)
    assert is_stale(fresh, now=now) is False
    assert is_stale(stale, now=now) is True
