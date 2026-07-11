"""yfinance drop-in parity: error swallowing, dividends/splits, download()."""

from __future__ import annotations

import pandas as pd
import pytest

from tidata.tifinance import Ticker, download
from tidata.tifinance.exceptions import TickerNotFoundError

_ROWS = [
    {"date": "2024-01-02", "adj_open": 184.5, "adj_high": 188.0, "adj_low": 183.8,
     "adj_close": 186.5, "adj_volume": 60_000_000, "open": 185.0, "high": 188.5,
     "low": 184.0, "close": 187.0, "volume": 60_000_000, "dividend": 0.5, "split_ratio": 0.0},
    {"date": "2024-01-03", "adj_open": 186.5, "adj_high": 189.5, "adj_low": 185.0,
     "adj_close": 188.5, "adj_volume": 55_000_000, "open": 187.0, "high": 190.0,
     "low": 185.5, "close": 189.0, "volume": 55_000_000, "dividend": 0.0, "split_ratio": 4.0},
]


class FakeTransport:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error

    def fetch(self, path, params):
        if self.error is not None:
            raise self.error
        return self.rows


# --- error swallowing (yfinance default) -----------------------------------


def test_error_returns_empty_frame_by_default():
    t = Ticker("ZZZZ", api_key="k",
               transport=FakeTransport(error=TickerNotFoundError("TICKER_NOT_FOUND", "no")))
    df = t.history(start="2024-01-02", end="2024-01-05")
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert set(df.columns) == {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}


def test_error_raises_when_requested():
    t = Ticker("ZZZZ", api_key="k",
               transport=FakeTransport(error=TickerNotFoundError("TICKER_NOT_FOUND", "no")))
    with pytest.raises(TickerNotFoundError):
        t.history(start="2024-01-02", end="2024-01-05", raise_errors=True)


# --- dividends / splits properties ------------------------------------------


def test_dividends_returns_nonzero_series():
    t = Ticker("AAPL", api_key="k", transport=FakeTransport(_ROWS))
    divs = t.dividends
    assert list(divs.index) == [pd.Timestamp("2024-01-02")]
    assert divs.iloc[0] == pytest.approx(0.5)


def test_splits_returns_nonzero_series():
    t = Ticker("AAPL", api_key="k", transport=FakeTransport(_ROWS))
    splits = t.splits
    assert list(splits.index) == [pd.Timestamp("2024-01-03")]
    assert splits.iloc[0] == pytest.approx(4.0)


# --- download() -------------------------------------------------------------


def _patch_download_ticker(monkeypatch):
    monkeypatch.setattr(
        "tidata.tifinance.multi.Ticker",
        lambda sym, api_key=None: Ticker(sym, api_key="k", transport=FakeTransport(_ROWS)),
    )


def test_download_single_ticker_is_flat(monkeypatch):
    _patch_download_ticker(monkeypatch)
    df = download("AAPL")
    assert not isinstance(df.columns, pd.MultiIndex)
    assert "Close" in df.columns


def test_download_multi_ticker_is_multiindex_field_ticker(monkeypatch):
    _patch_download_ticker(monkeypatch)
    df = download(["AAPL", "MSFT"])
    assert isinstance(df.columns, pd.MultiIndex)
    # group_by="column" default -> (field, ticker)
    assert ("Close", "AAPL") in df.columns
    assert ("Close", "MSFT") in df.columns
