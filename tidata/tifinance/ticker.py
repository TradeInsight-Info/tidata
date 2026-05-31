"""TradeInsight API client — Ticker class with yfinance-compatible history()."""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests

from .exceptions import APIError, from_code

_DEFAULT_BASE_URL = "https://api.tradeinsight.info/trading-data/v1"

_ADJ_COLUMN_MAP = {
    "adj_open": "Open",
    "adj_high": "High",
    "adj_low": "Low",
    "adj_close": "Close",
    "adj_volume": "Volume",
}

_RAW_COLUMN_MAP = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
}


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
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: int = 30,
    ) -> None:
        self.symbol = symbol.upper().strip()
        self.api_key: Optional[str] = api_key or os.environ.get("TIDATA_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def history(
        self,
        start: str,
        end: str,
        auto_adjust: bool = True,
        actions: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV history for this ticker.

        Parameters
        ----------
        start:
            Start date ``YYYY-MM-DD`` (inclusive).
        end:
            End date ``YYYY-MM-DD`` (inclusive).
        auto_adjust:
            When ``True`` (default), return split/dividend-adjusted prices.
        actions:
            When ``True`` (default), include Dividends and Stock Splits columns.
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
        return self._parse_response(response, auto_adjust=auto_adjust, actions=actions)

    def _parse_response(
        self, response: requests.Response, auto_adjust: bool, actions: bool
    ) -> pd.DataFrame:
        if not response.ok:
            self._raise_for_error(response)
        data = response.json()
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "data" in data:
            rows = data["data"]
        else:
            rows = [data] if data else []
        return self._build_dataframe(rows, auto_adjust=auto_adjust, actions=actions)

    def _build_dataframe(
        self, rows: list, auto_adjust: bool, actions: bool
    ) -> pd.DataFrame:
        if not rows:
            return self._empty_dataframe()
        df = pd.DataFrame(rows)
        col_map = _ADJ_COLUMN_MAP if auto_adjust else _RAW_COLUMN_MAP
        df = df.rename(columns=col_map)
        df["Dividends"] = pd.to_numeric(
            df["dividend"] if "dividend" in df.columns else pd.Series(0.0, index=df.index),
            errors="coerce",
        ).fillna(0.0)
        df["Stock Splits"] = pd.to_numeric(
            df["split_ratio"] if "split_ratio" in df.columns else pd.Series(0.0, index=df.index),
            errors="coerce",
        ).fillna(0.0)
        keep = ["date", "Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"]
        existing = [c for c in keep if c in df.columns]
        df = df[existing].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"date": "Date"}).set_index("Date")
        df = df.sort_index()
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if not actions:
            df = df.drop(columns=["Dividends", "Stock Splits"], errors="ignore")
        return df

    def _raise_for_error(self, response: requests.Response) -> None:
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
        return pd.DataFrame(
            columns=["Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"],
            index=pd.DatetimeIndex([], name="Date"),
        )
