"""Pytest suite for tidata.tifinance.Ticker.history()."""

from __future__ import annotations

import json

import pandas as pd
import pytest
import responses as resp_lib

from tidata.tifinance import Ticker
from tidata.tifinance.exceptions import (
    APIError,
    AuthenticationError,
    InvalidParameterError,
    RateLimitError,
    TickerNotFoundError,
)

BASE_URL = "https://api.tradeinsight.info/trading-data/v1"
OHLC_URL = f"{BASE_URL}/ohlc"

# Dummy key used only in tests — never a real credential
_TEST_API_KEY = "test-key-for-pytest"  # noqa: S105

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_THREE_ROWS = [
    {
        "date": "2024-01-02",
        "open": 185.0,
        "high": 188.5,
        "low": 184.0,
        "close": 187.0,
        "adj_open": 184.5,
        "adj_high": 188.0,
        "adj_low": 183.8,
        "adj_close": 186.5,
        "volume": 60_000_000,
        "adj_volume": 60_000_000,
        "dividend": 0.0,
        "split_ratio": 0.0,
    },
    {
        "date": "2024-01-03",
        "open": 187.0,
        "high": 190.0,
        "low": 185.5,
        "close": 189.0,
        "adj_open": 186.5,
        "adj_high": 189.5,
        "adj_low": 185.0,
        "adj_close": 188.5,
        "volume": 55_000_000,
        "adj_volume": 55_000_000,
        "dividend": 0.24,
        "split_ratio": 0.0,
    },
    {
        "date": "2024-01-04",
        "open": 189.0,
        "high": 192.0,
        "low": 187.0,
        "close": 191.0,
        "adj_open": 188.5,
        "adj_high": 191.5,
        "adj_low": 186.5,
        "adj_close": 190.5,
        "volume": 50_000_000,
        "adj_volume": 50_000_000,
        "dividend": 0.0,
        "split_ratio": 4.0,
    },
]


def _make_ticker(symbol: str = "AAPL") -> Ticker:
    return Ticker(symbol, api_key=_TEST_API_KEY)


def _error_body(code: str, message: str = "error") -> str:
    return json.dumps({"code": code, "message": message})


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_history_happy_path_shape():
    """Successful /ohlc call returns a DataFrame with the right shape."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        json={"data": _THREE_ROWS},
        status=200,
    )
    ticker = _make_ticker()
    df = ticker.history("2024-01-02", "2024-01-04")

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (3, 7)  # 7 columns: Open High Low Close Volume Dividends Stock Splits


@resp_lib.activate
def test_history_happy_path_index():
    """Index is DatetimeIndex named 'Date', sorted ascending."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04")

    assert df.index.name == "Date"
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.index) == sorted(df.index)


@resp_lib.activate
def test_history_happy_path_values():
    """Spot-check a numeric cell value for the adjusted close."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04")

    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(186.5)
    assert df.loc[pd.Timestamp("2024-01-02"), "Volume"] == 60_000_000


@resp_lib.activate
def test_history_top_level_list_response():
    """API may return a bare list (not wrapped in {"data": ...})."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json=_THREE_ROWS, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04")
    assert df.shape[0] == 3


# ---------------------------------------------------------------------------
# auto_adjust=True (default)
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_auto_adjust_true_columns():
    """auto_adjust=True uses adj_* fields → yfinance column names."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04", auto_adjust=True)

    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


@resp_lib.activate
def test_auto_adjust_true_uses_adj_values():
    """With auto_adjust=True, 'Close' holds adj_close, not raw close."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04", auto_adjust=True)

    # adj_close for 2024-01-02 is 186.5; raw close is 187.0
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(186.5)


# ---------------------------------------------------------------------------
# auto_adjust=False
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_auto_adjust_false_columns():
    """auto_adjust=False uses raw open/high/low/close fields."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04", auto_adjust=False)

    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


@resp_lib.activate
def test_auto_adjust_false_uses_raw_values():
    """With auto_adjust=False, 'Close' holds the raw close, not adj_close."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04", auto_adjust=False)

    # raw close for 2024-01-02 is 187.0; adj_close is 186.5
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(187.0)


# ---------------------------------------------------------------------------
# Dividends and Stock Splits
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_dividends_column_present_and_correct():
    """'Dividends' column is populated from the 'dividend' field."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04")

    assert "Dividends" in df.columns
    assert df.loc[pd.Timestamp("2024-01-03"), "Dividends"] == pytest.approx(0.24)
    assert df.loc[pd.Timestamp("2024-01-02"), "Dividends"] == pytest.approx(0.0)


@resp_lib.activate
def test_stock_splits_column_present_and_correct():
    """'Stock Splits' column is populated from the 'split_ratio' field."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04")

    assert "Stock Splits" in df.columns
    assert df.loc[pd.Timestamp("2024-01-04"), "Stock Splits"] == pytest.approx(4.0)
    assert df.loc[pd.Timestamp("2024-01-02"), "Stock Splits"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Empty response
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_history_empty_response():
    """Empty data list returns an empty DataFrame with the canonical schema."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": []}, status=200)
    df = _make_ticker().history("2024-01-02", "2024-01-04")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


# ---------------------------------------------------------------------------
# Error-code mapping tests
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_ticker_not_found_error():
    """TICKER_NOT_FOUND maps to TickerNotFoundError."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        body=_error_body("TICKER_NOT_FOUND", "Ticker ZZZZ not found"),
        status=404,
        content_type="application/json",
    )
    with pytest.raises(TickerNotFoundError) as exc_info:
        _make_ticker("ZZZZ").history("2024-01-02", "2024-01-04")

    assert exc_info.value.code == "TICKER_NOT_FOUND"


@resp_lib.activate
def test_unauthorized_error():
    """UNAUTHORIZED maps to AuthenticationError."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        body=_error_body("UNAUTHORIZED", "Invalid API key"),
        status=401,
        content_type="application/json",
    )
    with pytest.raises(AuthenticationError) as exc_info:
        _make_ticker().history("2024-01-02", "2024-01-04")

    assert exc_info.value.code == "UNAUTHORIZED"


@resp_lib.activate
def test_rate_limit_exceeded_error():
    """RATE_LIMIT_EXCEEDED maps to RateLimitError."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        body=_error_body("RATE_LIMIT_EXCEEDED", "Too many requests"),
        status=429,
        content_type="application/json",
    )
    with pytest.raises(RateLimitError) as exc_info:
        _make_ticker().history("2024-01-02", "2024-01-04")

    assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"


@resp_lib.activate
def test_ticker_required_error():
    """TICKER_REQUIRED maps to InvalidParameterError."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        body=_error_body("TICKER_REQUIRED", "Ticker is required"),
        status=400,
        content_type="application/json",
    )
    with pytest.raises(InvalidParameterError) as exc_info:
        _make_ticker().history("2024-01-02", "2024-01-04")

    assert exc_info.value.code == "TICKER_REQUIRED"


@resp_lib.activate
def test_unknown_error_code_raises_api_error():
    """An unrecognised error code falls back to the base APIError."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        body=_error_body("SOME_WEIRD_CODE", "Something went wrong"),
        status=500,
        content_type="application/json",
    )
    with pytest.raises(APIError) as exc_info:
        _make_ticker().history("2024-01-02", "2024-01-04")

    # Must be base APIError, not a subclass
    assert type(exc_info.value) is APIError
    assert exc_info.value.code == "SOME_WEIRD_CODE"


@resp_lib.activate
def test_non_json_error_response():
    """A non-JSON 500 body still raises APIError with an HTTP_ code."""
    resp_lib.add(
        resp_lib.GET,
        OHLC_URL,
        body="Internal Server Error",
        status=500,
        content_type="text/plain",
    )
    with pytest.raises(APIError) as exc_info:
        _make_ticker().history("2024-01-02", "2024-01-04")

    assert exc_info.value.code.startswith("HTTP_")


# ---------------------------------------------------------------------------
# Ticker initialisation / header tests
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_api_key_sent_as_header():
    """The Authorization: Bearer header is included in the request."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": []}, status=200)
    _make_ticker().history("2024-01-02", "2024-01-04")

    assert resp_lib.calls[0].request.headers.get("Authorization") == f"Bearer {_TEST_API_KEY}"


def test_symbol_normalised_to_uppercase():
    """Symbol is normalised to uppercase on construction."""
    ticker = Ticker("aapl", api_key="k")
    assert ticker.symbol == "AAPL"
