"""Direct tests for date-window resolution — today injected, no network, no clock."""

from __future__ import annotations

from datetime import date

import pytest

from tidata.tifinance.exceptions import InvalidParameterError
from tidata.tifinance.window import Window, resolve_window

_TODAY = date(2024, 6, 15)


def test_period_end_at_today():
    # 365-day delta crossing leap day 2024-02-29 -> start is 06-16, not 06-15
    w = resolve_window("1y", None, None, _TODAY)
    assert w == Window("2023-06-16", "2024-06-15")


def test_ytd_starts_jan_1():
    w = resolve_window("ytd", None, None, _TODAY)
    assert w == Window("2024-01-01", "2024-06-15")


def test_period_with_end_sets_start():
    # end exclusive 2023-01-01 -> inclusive 2022-12-31, back 1y
    w = resolve_window("1y", None, "2023-01-01", _TODAY)
    assert w == Window("2022-01-01", "2022-12-31")


def test_period_with_start_clamps_end_to_today():
    w = resolve_window("1y", "2024-01-01", None, _TODAY)
    assert w == Window("2024-01-01", "2024-06-15")  # clamped: start+1y would exceed today


def test_max_equals_10y():
    assert resolve_window("max", None, None, _TODAY) == resolve_window("10y", None, None, _TODAY)


def test_start_only_ends_today():
    w = resolve_window(None, "2020-01-01", None, _TODAY)
    assert w == Window("2020-01-01", "2024-06-15")


def test_explicit_end_is_made_inclusive():
    w = resolve_window(None, "2020-01-01", "2020-02-01", _TODAY)
    assert w == Window("2020-01-01", "2020-01-31")


def test_invalid_period_raises():
    with pytest.raises(InvalidParameterError):
        resolve_window("3y", None, None, _TODAY)


def test_all_three_raises():
    with pytest.raises(ValueError, match="nonsense"):
        resolve_window("1y", "2022-01-01", "2023-01-01", _TODAY)


def test_future_start_raises():
    with pytest.raises(InvalidParameterError, match="future"):
        resolve_window("1y", "2025-01-01", None, _TODAY)


def test_bad_date_string_raises():
    with pytest.raises(InvalidParameterError, match="Invalid date"):
        resolve_window(None, "not-a-date", None, _TODAY)
