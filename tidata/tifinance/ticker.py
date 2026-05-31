"""TradeInsight API client — Ticker class with yfinance-compatible history()."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests

from .exceptions import APIError, InvalidParameterError, from_code

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

_PERIOD_DELTAS: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "1mo": timedelta(days=30),
    "3mo": timedelta(days=91),
    "6mo": timedelta(days=182),
    "1y": timedelta(days=365),
    "2y": timedelta(days=730),
    "5y": timedelta(days=1825),
    "10y": timedelta(days=3650),
    "max": timedelta(days=3650),  # treated as 10y
}

_VALID_PERIODS = frozenset(_PERIOD_DELTAS) | {"ytd"}


def _parse_date(s: str, param_name: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise InvalidParameterError(
            "INVALID_PARAMETER",
            f"Invalid date for '{param_name}': {s!r}. Expected YYYY-MM-DD.",
        )


def _resolve_dates(
    period: str | None,
    start: str | None,
    end: str | None,
) -> tuple[str, str]:
    """Convert period/start/end to an inclusive (start, end) pair for the API.

    yfinance callers pass end as exclusive when they supply it explicitly —
    we subtract 1 day. Internally computed ends use today as-is (inclusive).
    """
    today = date.today()

    if period is not None and start is not None and end is not None:
        raise ValueError(
            "Setting period, start and end is nonsense. Set maximum 2 of them."
        )

    if period is not None:
        p = period.lower()
        if p not in _VALID_PERIODS:
            raise InvalidParameterError(
                "INVALID_PARAMETER",
                f"Invalid period '{period}'. Valid: {', '.join(sorted(_VALID_PERIODS))}",
            )

        if p == "ytd":
            return date(today.year, 1, 1).isoformat(), today.isoformat()

        delta = _PERIOD_DELTAS[p]

        if end is not None:
            end_d = _parse_date(end, "end") - timedelta(days=1)  # exclusive -> inclusive
            return (end_d - delta + timedelta(days=1)).isoformat(), end_d.isoformat()
        elif start is not None:
            start_d = _parse_date(start, "start")
            end_d = min(start_d + delta - timedelta(days=1), today)
            if end_d < start_d:
                raise InvalidParameterError(
                    "INVALID_PARAMETER",
                    f"'start' ({start}) is in the future; no data available.",
                )
            return start_d.isoformat(), end_d.isoformat()
        else:
            return (today - delta).isoformat(), today.isoformat()

    if start is None:
        raise ValueError("Provide 'period' or 'start'.")

    start_d = _parse_date(start, "start")
    if end is None:
        return start_d.isoformat(), today.isoformat()
    else:
        end_d = _parse_date(end, "end") - timedelta(days=1)  # exclusive -> inclusive
        return start_d.isoformat(), end_d.isoformat()


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

        resolved_start, resolved_end = _resolve_dates(effective_period, start, end)

        params = {
            "ticker": self.symbol,
            "start": resolved_start,
            "end": resolved_end,
            "adjust_volume": "true" if auto_adjust else "false",
        }
        rows = self._fetch_all(params)
        return self._build_dataframe(rows, auto_adjust=auto_adjust, actions=actions)

    def _fetch_all(self, params: dict) -> list:
        """Paginate through all result pages and return combined rows."""
        rows: list = []
        offset = 0
        while True:
            page_params = {**params, "limit": 1000, "offset": offset}
            response = self._session.get(
                f"{self.base_url}/ohlc",
                params=page_params,
                timeout=self.timeout,
            )
            if not response.ok:
                self._raise_for_error(response)
            data = response.json()
            if isinstance(data, list):
                page = data
            elif isinstance(data, dict) and "data" in data:
                page = data["data"]
            else:
                page = []
            rows.extend(page)
            if len(page) < 1000:
                break
            offset += 1000
        return rows

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
