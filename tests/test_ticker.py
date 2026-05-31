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
    df = ticker.history(start="2024-01-02", end="2024-01-05")

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (3, 7)  # 7 columns: Open High Low Close Volume Dividends Stock Splits


@resp_lib.activate
def test_history_happy_path_index():
    """Index is DatetimeIndex named 'Date', sorted ascending."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")

    assert df.index.name == "Date"
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.index) == sorted(df.index)


@resp_lib.activate
def test_history_happy_path_values():
    """Spot-check a numeric cell value for the adjusted close."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")

    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(186.5)
    assert df.loc[pd.Timestamp("2024-01-02"), "Volume"] == 60_000_000


@resp_lib.activate
def test_history_top_level_list_response():
    """API may return a bare list (not wrapped in {"data": ...})."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json=_THREE_ROWS, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")
    assert df.shape[0] == 3


# ---------------------------------------------------------------------------
# auto_adjust=True (default)
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_auto_adjust_true_columns():
    """auto_adjust=True uses adj_* fields → yfinance column names."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05", auto_adjust=True)

    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


@resp_lib.activate
def test_auto_adjust_true_uses_adj_values():
    """With auto_adjust=True, 'Close' holds adj_close, not raw close."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05", auto_adjust=True)

    # adj_close for 2024-01-02 is 186.5; raw close is 187.0
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(186.5)


# ---------------------------------------------------------------------------
# auto_adjust=False
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_auto_adjust_false_columns():
    """auto_adjust=False uses raw open/high/low/close fields."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05", auto_adjust=False)

    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


@resp_lib.activate
def test_auto_adjust_false_uses_raw_values():
    """With auto_adjust=False, 'Close' holds the raw close, not adj_close."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05", auto_adjust=False)

    # raw close for 2024-01-02 is 187.0; adj_close is 186.5
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == pytest.approx(187.0)


# ---------------------------------------------------------------------------
# Dividends and Stock Splits
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_dividends_column_present_and_correct():
    """'Dividends' column is populated from the 'dividend' field."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")

    assert "Dividends" in df.columns
    assert df.loc[pd.Timestamp("2024-01-03"), "Dividends"] == pytest.approx(0.24)
    assert df.loc[pd.Timestamp("2024-01-02"), "Dividends"] == pytest.approx(0.0)


@resp_lib.activate
def test_stock_splits_column_present_and_correct():
    """'Stock Splits' column is populated from the 'split_ratio' field."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")

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
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")

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
        _make_ticker("ZZZZ").history(start="2024-01-02", end="2024-01-05")

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
        _make_ticker().history(start="2024-01-02", end="2024-01-05")

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
        _make_ticker().history(start="2024-01-02", end="2024-01-05")

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
        _make_ticker().history(start="2024-01-02", end="2024-01-05")

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
        _make_ticker().history(start="2024-01-02", end="2024-01-05")

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
        _make_ticker().history(start="2024-01-02", end="2024-01-05")

    assert exc_info.value.code.startswith("HTTP_")


# ---------------------------------------------------------------------------
# Ticker initialisation / header tests
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_api_key_sent_as_header():
    """The Authorization: Bearer header is included in the request."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": []}, status=200)
    _make_ticker().history(start="2024-01-02", end="2024-01-05")

    assert resp_lib.calls[0].request.headers.get("Authorization") == f"Bearer {_TEST_API_KEY}"


def test_symbol_normalised_to_uppercase():
    """Symbol is normalised to uppercase on construction."""
    ticker = Ticker("aapl", api_key="k")
    assert ticker.symbol == "AAPL"


# ---------------------------------------------------------------------------
# period resolution
# ---------------------------------------------------------------------------

from datetime import date, timedelta


def test_period_invalid_raises():
    with pytest.raises(InvalidParameterError):
        _make_ticker().history(period="3y")


def test_period_all_three_raises():
    with pytest.raises(ValueError, match="nonsense"):
        _make_ticker().history(period="1y", start="2022-01-01", end="2023-01-01")


@resp_lib.activate
def test_period_1y_end_is_today():
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="1y")
    qs = resp_lib.calls[0].request.url
    assert f"end={date.today().isoformat()}" in qs


@resp_lib.activate
def test_period_1y_start_is_365_days_ago():
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="1y")
    qs = resp_lib.calls[0].request.url
    expected = (date.today() - timedelta(days=365)).isoformat()
    assert f"start={expected}" in qs


@resp_lib.activate
def test_period_with_end_sets_start():
    """period='1y', end='2023-01-01' -> start=2022-01-01, end=2022-12-31 (exclusive end)."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="1y", end="2023-01-01")
    qs = resp_lib.calls[0].request.url
    assert "start=2022-01-01" in qs
    assert "end=2022-12-31" in qs


@resp_lib.activate
def test_period_with_start_sets_end():
    """period='1y', start='2022-01-01' -> end=2022-12-31."""
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="1y", start="2022-01-01")
    qs = resp_lib.calls[0].request.url
    assert "start=2022-01-01" in qs
    assert "end=2022-12-31" in qs


@resp_lib.activate
def test_period_ytd_start_is_jan_1():
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="ytd")
    qs = resp_lib.calls[0].request.url
    jan1 = f"{date.today().year}-01-01"
    assert f"start={jan1}" in qs


@resp_lib.activate
def test_period_max_same_as_10y():
    import urllib.parse
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="max")
    qs_max = resp_lib.calls[0].request.url

    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": [], "total": 0, "limit": 1000, "offset": 0}, status=200)
    _make_ticker().history(period="10y")
    qs_10y = resp_lib.calls[1].request.url

    p_max = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(qs_max).query))
    p_10y = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(qs_10y).query))
    assert p_max["start"] == p_10y["start"]
    assert p_max["end"] == p_10y["end"]


# ---------------------------------------------------------------------------
# interval and actions
# ---------------------------------------------------------------------------


def test_interval_non_1d_raises():
    with pytest.raises(InvalidParameterError, match="interval"):
        _make_ticker().history(start="2024-01-02", end="2024-01-05", interval="1wk")


@resp_lib.activate
def test_actions_false_drops_columns():
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS, "total": 3, "limit": 1000, "offset": 0}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05", actions=False)
    assert "Dividends" not in df.columns
    assert "Stock Splits" not in df.columns
    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume"}


# ---------------------------------------------------------------------------
# pagination
# ---------------------------------------------------------------------------


def _make_rows(n: int) -> list[dict]:
    return [
        {
            "date": f"2020-01-{(i % 28) + 1:02d}",
            "adj_open": 100.0, "adj_high": 101.0, "adj_low": 99.0,
            "adj_close": 100.5, "adj_volume": 1_000_000,
            "open": 100.0, "high": 101.0, "low": 99.0,
            "close": 100.5, "volume": 1_000_000,
            "dividend": 0.0, "split_ratio": 0.0,
        }
        for i in range(n)
    ]


@resp_lib.activate
def test_pagination_concatenates_pages():
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _make_rows(1000), "total": 2500, "limit": 1000, "offset": 0}, status=200)
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _make_rows(1000), "total": 2500, "limit": 1000, "offset": 1000}, status=200)
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _make_rows(500), "total": 2500, "limit": 1000, "offset": 2000}, status=200)

    df = _make_ticker().history(start="2020-01-01", end="2027-01-01")
    assert len(df) == 2500
    assert len(resp_lib.calls) == 3
    assert "offset=0"    in resp_lib.calls[0].request.url
    assert "offset=1000" in resp_lib.calls[1].request.url
    assert "offset=2000" in resp_lib.calls[2].request.url


@resp_lib.activate
def test_single_page_no_extra_requests():
    resp_lib.add(resp_lib.GET, OHLC_URL, json={"data": _THREE_ROWS, "total": 3, "limit": 1000, "offset": 0}, status=200)
    df = _make_ticker().history(start="2024-01-02", end="2024-01-05")
    assert df.shape[0] == 3
    assert len(resp_lib.calls) == 1
