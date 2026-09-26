from datetime import datetime, timezone

from retail_counter.timezones import resolve_timezone


def test_ist_fallback_has_expected_offset(monkeypatch):
    class MissingZone:
        def __init__(self, _name):
            from zoneinfo import ZoneInfoNotFoundError

            raise ZoneInfoNotFoundError

    monkeypatch.setattr("retail_counter.timezones.ZoneInfo", MissingZone)
    ist = resolve_timezone("Asia/Calcutta")
    assert datetime(2026, 1, 1, tzinfo=timezone.utc).astimezone(ist).hour == 5
    assert datetime(2026, 1, 1, tzinfo=timezone.utc).astimezone(ist).minute == 30
