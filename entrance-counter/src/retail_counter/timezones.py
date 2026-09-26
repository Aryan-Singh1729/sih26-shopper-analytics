from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_timezone(name: str) -> tzinfo:
    """Resolve a timezone even on minimal images that omit the tzdata package."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name in {"Asia/Calcutta", "Asia/Kolkata"}:
            return timezone(timedelta(hours=5, minutes=30), name="IST")
        if name in {"UTC", "Etc/UTC"}:
            return timezone.utc
        raise
