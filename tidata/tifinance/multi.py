"""yfinance-style ``download()`` over one or more tickers."""

from __future__ import annotations

from typing import Iterable, Optional, Union

import pandas as pd

from .ticker import Ticker


def download(
    tickers: Union[str, Iterable[str]],
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
    interval: str = "1d",
    auto_adjust: bool = True,
    actions: bool = True,
    group_by: str = "column",
    api_key: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """Download history for one or more tickers, yfinance-style.

    ``tickers`` may be a space-separated string (``"AAPL MSFT"``) or an
    iterable of symbols. A single ticker returns a flat DataFrame; multiple
    tickers return a column MultiIndex. ``group_by="column"`` (default) nests
    as ``(field, ticker)``; ``group_by="ticker"`` nests as ``(ticker, field)``.
    """
    symbols = tickers.split() if isinstance(tickers, str) else list(tickers)
    if not symbols:
        raise ValueError("Provide at least one ticker.")

    frames = {
        sym: Ticker(sym, api_key=api_key).history(
            period=period,
            interval=interval,
            start=start,
            end=end,
            auto_adjust=auto_adjust,
            actions=actions,
        )
        for sym in symbols
    }

    if len(symbols) == 1:
        return frames[symbols[0]]

    combined = pd.concat(frames, axis=1)  # columns: (ticker, field)
    if group_by == "column":
        combined = combined.swaplevel(axis=1).sort_index(axis=1)  # (field, ticker)
    return combined
