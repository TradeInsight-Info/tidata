"""TradeInsight API client — Ticker class with yfinance-compatible history()."""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

import pandas as pd

from .exceptions import InvalidParameterError
from .frame import frame_from_rows
from .transport import HttpTransport, Transport
from .window import resolve_window

_DEFAULT_BASE_URL = "https://api.tradeinsight.info/trading-data/v1"


class Ticker:
    """Client for a single ticker symbol against the TradeInsight API.

    Parameters
    ----------
    symbol:
        Ticker symbol, e.g. ``"AAPL"``.
    api_key:
        API key.  Falls back to the ``TIDATA_API_KEY`` environment variable.
    base_url:
        Override the API base URL.
    timeout:
        HTTP request timeout in seconds (default: 30).
    transport:
        Adapter that fetches rows for an endpoint. Defaults to an
        :class:`HttpTransport`; tests may pass an in-memory adapter.
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: int = 30,
        *,
        transport: Optional[Transport] = None,
    ) -> None:
        self.symbol = symbol.upper().strip()
        self._transport: Transport = transport or HttpTransport(
            base_url, api_key or os.environ.get("TIDATA_API_KEY"), timeout
        )

    def history(
        self,
        period: str | None = None,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
        auto_adjust: bool = True,
        actions: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch OHLCV history for this ticker.

        Parameters
        ----------
        period:
            Shorthand time period, e.g. ``"1y"``, ``"6mo"``, ``"ytd"``, ``"max"``.
            Mutually exclusive with providing both ``start`` and ``end``.
        interval:
            Data interval. Only ``"1d"`` is currently supported.
        start:
            Start date ``YYYY-MM-DD`` (inclusive).
        end:
            End date ``YYYY-MM-DD`` (exclusive, yfinance convention).
        auto_adjust:
            When ``True`` (default), return split/dividend-adjusted prices.
        actions:
            When ``True`` (default), include Dividends and Stock Splits columns.
        """
        if interval != "1d":
            raise InvalidParameterError(
                "INVALID_PARAMETER",
                "only interval='1d' is supported",
            )

        effective_period = period
        if effective_period is None and start is None:
            effective_period = "1mo"

        window = resolve_window(effective_period, start, end, date.today())

        params = {
            "ticker": self.symbol,
            "start": window.start,
            "end": window.end,
            "adjust_volume": "true" if auto_adjust else "false",
        }
        rows = self._transport.fetch("/ohlc", params)
        return frame_from_rows(rows, auto_adjust=auto_adjust, actions=actions)
