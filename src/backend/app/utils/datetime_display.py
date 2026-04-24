from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def format_display_datetime(value: datetime, client_timezone: str | None = None) -> str:
    display_value = value
    if display_value.tzinfo is None:
        display_value = display_value.replace(tzinfo=timezone.utc)

    if client_timezone:
        try:
            display_value = display_value.astimezone(ZoneInfo(client_timezone))
        except ZoneInfoNotFoundError:
            display_value = display_value.astimezone()
    else:
        display_value = display_value.astimezone()

    return _format_portable_datetime(display_value)


def parse_display_datetime(value: str | datetime, client_timezone: str | None = None) -> str:
    if isinstance(value, datetime):
        return format_display_datetime(value, client_timezone)

    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return format_display_datetime(parsed, client_timezone)


def _format_portable_datetime(value: datetime) -> str:
    month = value.strftime("%b")
    day = value.day
    year = value.year
    hour = value.hour % 12 or 12
    minute = value.minute
    am_pm = "AM" if value.hour < 12 else "PM"
    tz_name = value.tzname()
    tz_suffix = f" {tz_name}" if tz_name else ""
    return f"{month} {day}, {year} at {hour}:{minute:02d} {am_pm}{tz_suffix}"
