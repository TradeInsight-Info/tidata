"""Resolve period/start/end into a concrete date window for the API.

Pure module: ``today`` is injected, so resolution is deterministic and
testable without a network fake or a dependency on the wall clock.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

from .exceptions import InvalidParameterError

_PERIOD_DELTAS: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "1mo": timedelta(days=30),
    "3mo": timedelta(days=91),
    "6mo": timedelta(days=182),
    "1y": timedelta(days=365),
    "2y": timedelta(days=730),
    "5y": timedelta(days=1825),
    "10y": timedelta(days=3650),
}

# "max" and "ytd" resolve specially rather than via a fixed delta.
_MAX_START = "1900-01-01"  # floor; the API returns whatever history it has
_VALID_PERIODS = frozenset(_PERIOD_DELTAS) | {"ytd", "max"}


class Window(NamedTuple):
    """Inclusive (start, end) date pair as ISO strings, ready for the API."""

    start: str
    end: str


def _parse_date(s: str, param_name: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise InvalidParameterError(
            "INVALID_PARAMETER",
            f"Invalid date for '{param_name}': {s!r}. Expected YYYY-MM-DD.",
        )


def resolve_window(
    period: str | None,
    start: str | None,
    end: str | None,
    today: date,
) -> Window:
    """Convert period/start/end to an inclusive :class:`Window` for the API.

    yfinance callers pass ``end`` as exclusive when they supply it explicitly —
    we subtract 1 day. Internally computed ends use ``today`` as-is (inclusive).
    """
    if period is not None and start is not None and end is not None:
        raise ValueError(
            "Setting period, start and end is nonsense. Set maximum 2 of them."
        )

    if period is not None:
        p = period.lower()
        if p not in _VALID_PERIODS:
            raise InvalidParameterError(
                "INVALID_PARAMETER",
                f"Invalid period '{period}'. Valid: {', '.join(sorted(_VALID_PERIODS))}",
            )

        if p == "ytd":
            return Window(date(today.year, 1, 1).isoformat(), today.isoformat())

        if p == "max":
            return Window(_MAX_START, today.isoformat())

        delta = _PERIOD_DELTAS[p]

        if end is not None:
            end_d = _parse_date(end, "end") - timedelta(days=1)  # exclusive -> inclusive
            return Window(
                (end_d - delta + timedelta(days=1)).isoformat(), end_d.isoformat()
            )
        elif start is not None:
            start_d = _parse_date(start, "start")
            end_d = min(start_d + delta - timedelta(days=1), today)
            if end_d < start_d:
                raise InvalidParameterError(
                    "INVALID_PARAMETER",
                    f"'start' ({start}) is in the future; no data available.",
                )
            return Window(start_d.isoformat(), end_d.isoformat())
        else:
            return Window((today - delta).isoformat(), today.isoformat())

    if start is None:
        raise ValueError("Provide 'period' or 'start'.")

    start_d = _parse_date(start, "start")
    if end is None:
        return Window(start_d.isoformat(), today.isoformat())
    else:
        end_d = _parse_date(end, "end") - timedelta(days=1)  # exclusive -> inclusive
        return Window(start_d.isoformat(), end_d.isoformat())
