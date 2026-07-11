"""Shape raw API rows into a yfinance-compatible OHLCV DataFrame.

Pure module: rows in, DataFrame out. No network, no I/O — the whole
row→DataFrame concern (column maps, numeric coercion, dividends/splits,
sort, empty schema) lives here and is tested directly.
"""

from __future__ import annotations

import pandas as pd

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

_COLUMNS = ["Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"]


def empty_frame() -> pd.DataFrame:
    """Canonical empty DataFrame with the yfinance column schema."""
    return pd.DataFrame(
        columns=list(_COLUMNS),
        index=pd.DatetimeIndex([], name="Date"),
    )


def frame_from_rows(
    rows: list,
    *,
    auto_adjust: bool,
    actions: bool,
) -> pd.DataFrame:
    """Build the OHLCV DataFrame from raw API rows.

    Parameters
    ----------
    rows:
        Raw row dicts from the API.
    auto_adjust:
        When ``True``, use ``adj_*`` fields; otherwise use raw fields.
    actions:
        When ``True``, keep the ``Dividends`` and ``Stock Splits`` columns.
    """
    if not rows:
        return empty_frame()
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
    keep = ["date", *_COLUMNS]
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
