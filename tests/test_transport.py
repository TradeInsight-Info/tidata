"""The transport seam: Ticker works against an in-memory adapter, no HTTP fake."""

from __future__ import annotations

import pandas as pd

from tidata.tifinance import Ticker


class FakeTransport:
    """In-memory adapter — records calls, returns canned rows."""

    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def fetch(self, path: str, params: dict) -> list:
        self.calls.append((path, params))
        return self.rows


_ROWS = [
    {"date": "2024-01-02", "adj_open": 184.5, "adj_high": 188.0, "adj_low": 183.8,
     "adj_close": 186.5, "adj_volume": 60_000_000, "open": 185.0, "high": 188.5,
     "low": 184.0, "close": 187.0, "volume": 60_000_000, "dividend": 0.0, "split_ratio": 0.0},
]


def test_injected_transport_bypasses_network():
    fake = FakeTransport(_ROWS)
    df = Ticker("AAPL", api_key="k", transport=fake).history(start="2024-01-02", end="2024-01-05")

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] == 1
    assert df.loc[pd.Timestamp("2024-01-02"), "Close"] == 186.5


def test_history_calls_transport_with_ohlc_path_and_params():
    fake = FakeTransport([])
    Ticker("aapl", api_key="k", transport=fake).history(start="2024-01-02", end="2024-01-05")

    path, params = fake.calls[0]
    assert path == "/ohlc"
    assert params["ticker"] == "AAPL"
    assert params["start"] == "2024-01-02"
    assert params["end"] == "2024-01-04"  # exclusive end -> inclusive
    assert params["adjust_volume"] == "true"
