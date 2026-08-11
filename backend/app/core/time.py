from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def business_today(now_utc: datetime | None = None):
    """Return the operating date consistently, independent of server timezone."""
    instant = now_utc or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(ZoneInfo(get_settings().business_timezone)).date()


def business_day_utc_bounds(day: date) -> tuple[datetime, datetime]:
    zone = ZoneInfo(get_settings().business_timezone)
    start = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    return start, end
