"""Form-value coercion. Skeleton, not generated.

HTML forms hand you strings, always, including for a checkbox that is simply
absent when unticked. Every one of these helpers exists because the naive
version (`int(form["qty"])`, `bool(form.get("done"))`) raises or lies on an
ordinary empty submit -- and a generated route is exactly where that bug is
least likely to be noticed before a demo.
"""

from __future__ import annotations

from datetime import date, datetime


def parse_str(value: object, default: str = "") -> str:
    return str(value).strip() if value not in (None, "") else default


def parse_int(value: object, default: int | None = None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_float(value: object, default: float | None = None) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_bool(value: object) -> bool:
    # An unchecked box is not submitted at all, so absence means False.
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "on", "yes", "checked"}


def parse_date(value: object, default: date | None = None) -> date | None:
    text = parse_str(value)
    if not text:
        return default
    try:
        return date.fromisoformat(text)
    except ValueError:
        return default


def parse_datetime(value: object, default: datetime | None = None) -> datetime | None:
    text = parse_str(value)
    if not text:
        return default
    # <input type="datetime-local"> submits without seconds; fromisoformat
    # handles both shapes, but not a trailing "Z".
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return default
