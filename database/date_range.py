
"""Resolve profile-page date-filter input into a concrete window.

Pure standard-library helper (no Flask imports). Turns the loose ``start`` /
``end`` / ``range`` query-string values into a ``(start, end, label)`` triple
where ``start`` and ``end`` are ``YYYY-MM-DD`` strings or ``None`` (open bound)
and ``label`` is a human-readable description for the template.

Bad input never raises: an unparseable date is treated as absent, so the caller
falls back to the unfiltered "All time" view.
"""

import calendar
from datetime import date, timedelta


def _parse(value):
    """Return a ``date`` for an ISO ``YYYY-MM-DD`` string, or ``None``."""
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _fmt(d):
    """Format a date as e.g. ``3 Jul 2026`` (no ``%-d`` — not portable to Windows)."""
    return f"{d.day} {d:%b %Y}"


def _months_ago(d, n):
    """Return the date ``n`` calendar months before ``d`` (day clamped to month end)."""
    month = d.month - n
    year = d.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _span_label(start, end):
    """Readable label for a possibly one-sided ``(start, end)`` date span."""
    if start and end:
        return f"{_fmt(start)} – {_fmt(end)}"
    if start:
        return f"From {_fmt(start)}"
    if end:
        return f"Until {_fmt(end)}"
    return "All time"


def resolve_range(start=None, end=None, preset=None, today=None):
    """Resolve filter input to ``(start, end, label)``.

    ``preset`` (the ``range`` param) takes precedence over ``start`` / ``end``.
    Without a preset, whichever of ``start`` / ``end`` parses cleanly is used
    (a one-sided window is fine); a ``start`` later than ``end`` is swapped
    rather than rejected. Unparseable or empty values are treated as absent, so
    with nothing usable left the result is ``(None, None, "All time")``.
    """
    today = today or date.today()

    if preset == "this_month":
        first = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        last = today.replace(day=last_day)
        return first.isoformat(), last.isoformat(), "This month"
    if preset == "last30":
        first = today - timedelta(days=29)
        return first.isoformat(), today.isoformat(), "Last 30 days"
    if preset == "last3m":
        first = _months_ago(today, 3)
        return first.isoformat(), today.isoformat(), "Last 3 months"
    if preset == "last6m":
        first = _months_ago(today, 6)
        return first.isoformat(), today.isoformat(), "Last 6 months"
    if preset == "all":
        return None, None, "All time"

    s, e = _parse(start), _parse(end)
    if s and e and s > e:
        s, e = e, s

    start_iso = s.isoformat() if s else None
    end_iso = e.isoformat() if e else None
    return start_iso, end_iso, _span_label(s, e)
