"""Trading Data Service client — Ticker class with yfinance-compatible history()."""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests

from .exceptions import APIError, from_code

_DEFAULT_BASE_URL = "https://api.tradeinsight.info"

# Raw API field → yfinance-compatible column name (auto_adjust=True)
_ADJ_COLUMN_MAP = {
    "adj_open": "Open",
    "adj_high": "High",
    "adj_low": "Low",
    "adj_close": "Close",
    "adj_volume": "Volume",
}

# Raw API field → yfinance-compatible column name (auto_adjust=False)
_RAW_COLUMN_MAP = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
}


class Ticker:
    """Client for a single ticker symbol against the Trading Data Service API.

    Parameters
    ----------
    symbol:
        Ticker symbol, e.g. ``"AAPL"``.
    api_key:
        API key for the Trading Data Service.  Falls back to the
        ``TRADING_DATA_API_KEY`` environment variable when omitted.
    base_url:
        Base URL for the API.  Defaults to ``https://api.tradeinsight.info``.
    timeout:
        HTTP request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: int = 30,
    ) -> None:
        self.symbol = symbol.upper().strip()
        self.api_key: Optional[str] = api_key or os.environ.get("TRADING_DATA_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"X-Api-Key": self.api_key})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def history(
        self,
        start: str,
        end: str,
        auto_adjust: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV history for this ticker.

        Parameters
        ----------
        start:
            Start date in ``YYYY-MM-DD`` format (inclusive).
        end:
            End date in ``YYYY-MM-DD`` format (inclusive).
        auto_adjust:
            When ``True`` (default), return split- and dividend-adjusted
            prices using ``adj_*`` fields, matching yfinance column names.
            When ``False``, return raw (unadjusted) prices.

        Returns
        -------
        pd.DataFrame
            Indexed by ``Date`` (``datetime64[ns]``).  Columns:
            ``Open, High, Low, Close, Volume, Dividends, Stock Splits``.

        Raises
        ------
        TickerNotFoundError
            The ticker symbol was not found.
        AuthenticationError
            The API key is missing or invalid.
        RateLimitError
            The API rate limit has been exceeded.
        InvalidParameterError
            A required parameter is missing or invalid.
        APIError
            Any other API-level error.
        requests.exceptions.RequestException
            Network-level errors (timeout, connection refused, etc.).
        """
        params = {
            "ticker": self.symbol,
            "start": start,
            "end": end,
            "adjust_volume": "true" if auto_adjust else "false",
        }
        response = self._session.get(
            f"{self.base_url}/ohlc",
            params=params,
            timeout=self.timeout,
        )
        return self._parse_response(response, auto_adjust=auto_adjust)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(
        self, response: requests.Response, auto_adjust: bool
    ) -> pd.DataFrame:
        """Parse a raw HTTP response into a DataFrame, raising on errors."""
        if not response.ok:
            self._raise_for_error(response)

        data = response.json()

        # API may return a top-level list or {"data": [...]}
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "data" in data:
            rows = data["data"]
        else:
            rows = [data] if data else []

        if not rows:
            return self._empty_dataframe()

        df = pd.DataFrame(rows)

        # Build OHLCV columns
        col_map = _ADJ_COLUMN_MAP if auto_adjust else _RAW_COLUMN_MAP
        df = df.rename(columns=col_map)

        # Corporate actions columns
        df["Dividends"] = pd.to_numeric(df.get("dividend", 0), errors="coerce").fillna(0.0)
        df["Stock Splits"] = pd.to_numeric(df.get("split_ratio", 0), errors="coerce").fillna(0.0)

        # Keep only the canonical columns (drop raw fields)
        keep = ["date", "Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"]
        existing = [c for c in keep if c in df.columns]
        df = df[existing].copy()

        # Parse and set index
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"date": "Date"}).set_index("Date")
        df = df.sort_index()

        # Coerce numeric types
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _raise_for_error(self, response: requests.Response) -> None:
        """Parse the error body and raise a typed exception."""
        try:
            body = response.json()
            code = body.get("code", f"HTTP_{response.status_code}")
            message = body.get("message", response.text or "Unknown error")
        except Exception:
            code = f"HTTP_{response.status_code}"
            message = response.text or "Unknown error"
        raise from_code(code, message)

    @staticmethod
    def _empty_dataframe() -> pd.DataFrame:
        """Return an empty DataFrame with the canonical schema."""
        return pd.DataFrame(
            columns=["Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"],
            index=pd.DatetimeIndex([], name="Date"),
        )
