"""TradeInsight API client — Ticker class with yfinance-compatible history()."""

from __future__ import annotations

import logging
import os
import warnings
from datetime import date
from typing import Optional

import pandas as pd

from .exceptions import APIClosedError, APIError, InvalidParameterError
from .frame import empty_frame, frame_from_rows
from .transport import HttpTransport, Transport
from .window import resolve_window

_DEFAULT_BASE_URL = "https://api.tradeinsight.info/trading-data/v1"

# The beta data API this package is built on stops answering at 23:59 UTC on
# 2 September 2026. Said at
# construction rather than only on the first request, so someone who installs
# this today learns why before they start debugging a failed call.
_SHUTDOWN_NOTICE = (
    "tidata is deprecated: the TradeInsight beta data API it calls stops "
    "answering at 23:59 UTC on 2 September 2026, after which every request "
    "returns 410 Gone and no API key will work again. "
    "The data moved to TradeInsight Desk — https://tradeinsight.info"
)

logger = logging.getLogger(__name__)


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
        # Not warned when a transport is injected: that is the test seam and a
        # caller pointing at their own server, neither of which is affected.
        if transport is None:
            warnings.warn(_SHUTDOWN_NOTICE, DeprecationWarning, stacklevel=2)
        self.symbol = symbol.upper().strip()
        self._transport: Transport = transport or HttpTransport(
            base_url, api_key or os.environ.get("TIDATA_API_KEY"), timeout
        )
        self._action_history: Optional[pd.DataFrame] = None

    def history(
        self,
        period: str | None = None,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
        auto_adjust: bool = True,
        actions: bool = True,
        raise_errors: bool = False,
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
        raise_errors:
            When ``False`` (default, yfinance behaviour), API errors are logged
            and an empty DataFrame is returned. When ``True``, they raise.
            :class:`APIClosedError` always raises regardless — the API is gone,
            and an empty frame would hide that behind "no data".
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
        try:
            rows = self._transport.fetch("/ohlc", params)
        except APIClosedError:
            # Never swallowed, even with raise_errors=False. That default exists
            # to match yfinance for a transient failure, where an empty frame is
            # a reasonable answer. A closed API is not transient: returning an
            # empty DataFrame would read as "no data for this ticker" and hide
            # the one fact the caller needs.
            raise
        except APIError:
            if raise_errors:
                raise
            logger.warning(
                "history() for %s failed; returning empty DataFrame",
                self.symbol,
                exc_info=True,
            )
            return empty_frame(auto_adjust=auto_adjust, actions=actions)
        return frame_from_rows(rows, auto_adjust=auto_adjust, actions=actions)

    @property
    def dividends(self) -> pd.Series:
        """Non-zero dividends over the full available history."""
        s = self._full_actions()["Dividends"]
        return s[s != 0]

    @property
    def splits(self) -> pd.Series:
        """Non-zero stock splits over the full available history."""
        s = self._full_actions()["Stock Splits"]
        return s[s != 0]

    def _full_actions(self) -> pd.DataFrame:
        """Full-history frame with action columns, fetched once and cached."""
        if self._action_history is None:
            self._action_history = self.history(period="max", actions=True)
        return self._action_history
