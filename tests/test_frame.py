"""Direct tests for the row->DataFrame shaping module — no network fake needed."""

from __future__ import annotations

import pandas as pd
import pytest

from tidata.tifinance.frame import empty_frame, frame_from_rows

_ROWS = [
    {
        "date": "2024-01-03",
        "open": 187.0, "high": 190.0, "low": 185.5, "close": 189.0,
        "adj_open": 186.5, "adj_high": 189.5, "adj_low": 185.0, "adj_close": 188.5,
        "volume": 55_000_000, "adj_volume": 55_000_000,
        "dividend": 0.24, "split_ratio": 0.0,
    },
    {
        "date": "2024-01-02",
        "open": 185.0, "high": 188.5, "low": 184.0, "close": 187.0,
        "adj_open": 184.5, "adj_high": 188.0, "adj_low": 183.8, "adj_close": 186.5,
        "volume": 60_000_000, "adj_volume": 60_000_000,
        "dividend": 0.0, "split_ratio": 4.0,
    },
]

_SCHEMA = {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


def test_empty_rows_return_canonical_empty_frame():
    df = frame_from_rows([], auto_adjust=True, actions=True)
    assert len(df) == 0
    assert set(df.columns) == _SCHEMA
    assert df.index.name == "Date"


def test_empty_frame_helper_matches_schema():
    df = empty_frame()
    assert set(df.columns) == _SCHEMA
    assert isinstance(df.index, pd.DatetimeIndex)


def test_auto_adjust_true_uses_adj_values():
    df = frame_from_rows(_ROWS, auto_adjust=True, actions=True)
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(186.5)


def test_auto_adjust_false_uses_raw_values():
    df = frame_from_rows(_ROWS, auto_adjust=False, actions=True)
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(187.0)


def test_index_sorted_ascending():
    df = frame_from_rows(_ROWS, auto_adjust=True, actions=True)
    assert list(df.index) == sorted(df.index)


def test_dividends_and_splits_populated():
    df = frame_from_rows(_ROWS, auto_adjust=True, actions=True)
    assert df.loc[pd.Timestamp("2024-01-03"), "Dividends"] == pytest.approx(0.24)
    assert df.loc[pd.Timestamp("2024-01-02"), "Stock Splits"] == pytest.approx(4.0)


def test_actions_false_drops_action_columns():
    df = frame_from_rows(_ROWS, auto_adjust=True, actions=False)
    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume"}


def test_missing_dividend_field_defaults_to_zero():
    rows = [{"date": "2024-01-02", "adj_close": 100.0, "adj_open": 100.0,
             "adj_high": 100.0, "adj_low": 100.0, "adj_volume": 1}]
    df = frame_from_rows(rows, auto_adjust=True, actions=True)
    assert df.loc[pd.Timestamp("2024-01-02"), "Dividends"] == 0.0
    assert df.loc[pd.Timestamp("2024-01-02"), "Stock Splits"] == 0.0
