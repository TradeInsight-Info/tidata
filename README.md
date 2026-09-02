# tidata

> ## ⚠️ Deprecated — the API behind this package is closed
>
> The TradeInsight **beta data API** that `tidata` calls stopped answering at
> **23:59 UTC on 2 September 2026**. Every request now returns
> `410 Gone`, and no key will work again — the beta credential pool is
> switched off, and beta signup is closed, so a new key cannot be issued either.
>
> Key holders were emailed on 26 August 2026. There is nothing to migrate to
> that keeps this package working.
>
> **Nothing in this package can be made to work.** It has no unauthenticated
> mode: without a key it never sent an `Authorization` header, and the server
> refused the call.
>
> **Where the data went:** [TradeInsight Desk](https://tradeinsight.info) — the
> same congressional, insider and price data, reached through an agent rather
> than a raw API.
>
> If you are reading this from a failing script, the error you want is
> `tidata.tifinance.exceptions.APIClosedError` (code `API_CLOSED`), raised in
> place of the auth error the 410 would otherwise look like.

---

The rest of this README is kept for anyone reading old code. **It no longer
describes anything that runs.**

Provides a `Ticker` class with a `history()` method that returns a pandas DataFrame
with yfinance-compatible column names.

## Installation

```bash
pip install tidata
```

Or install from source:

```bash
git clone https://github.com/TradeInsight-Info/tidata.git
cd tidata
pip install -e .
```

## Quick Start

~~Set your API key in the environment~~ — keys are no longer issued and existing
ones are rejected. The snippet below is what the client used to do:

```python
from tidata.tifinance import Ticker

# API key is read from TIDATA_API_KEY env var automatically
t = Ticker("AAPL")

# Adjusted prices (yfinance-compatible)
df = t.history(start="2024-01-01", end="2024-12-31")
print(df.head())
#                  Open        High         Low       Close      Volume  Dividends  Stock Splits
# Date
# 2024-01-02  184.210...  185.880...  183.430...  185.200...  79047200.0        0.0           0.0

# Raw (unadjusted) prices — adds an "Adj Close" column, like yfinance
df_raw = t.history(start="2024-01-01", end="2024-12-31", auto_adjust=False)
```

## yfinance drop-in

`Ticker.history()` mirrors yfinance for the daily-OHLCV case:

```python
from tidata.tifinance import Ticker, download

# period shorthands: 1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max
df = Ticker("AAPL").history(period="1y")

# non-zero dividends / splits over full available history (period="max")
divs = Ticker("AAPL").dividends
spl = Ticker("AAPL").splits

# bulk download — flat frame for one ticker, column MultiIndex for many
one = download("AAPL", period="6mo")
many = download("AAPL MSFT", period="6mo")   # columns: (field, ticker)
```

**Behaviour notes**

- On API errors, `history()` logs a warning and returns an empty DataFrame
  (yfinance behaviour). Pass `raise_errors=True` to raise the typed exception
  instead.
- `period="max"` requests full available history (from a `1900-01-01` floor),
  not a fixed window.
- Only `interval="1d"` is currently supported.
- The index is a tz-naive `DatetimeIndex` named `Date`.

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `symbol` | Ticker symbol (e.g. `"AAPL"`) | required |
| `api_key` | API key — also reads `TIDATA_API_KEY` env var | `None` |
| `base_url` | API base URL | `https://api.tradeinsight.info/trading-data/v1` |
| `timeout` | HTTP timeout in seconds | `30` |

## Exceptions

| Exception | API error code |
|-----------|---------------|
| `TickerNotFoundError` | `TICKER_NOT_FOUND`, `INVALID_TICKER` |
| `AuthenticationError` | `UNAUTHORIZED`, `INVALID_API_KEY`, `API_KEY_REQUIRED` |
| `RateLimitError` | `RATE_LIMIT_EXCEEDED`, `TOO_MANY_REQUESTS` |
| `InvalidParameterError` | `TICKER_REQUIRED`, `INVALID_DATE`, `INVALID_PARAMETER` |
| `APIError` | Any other error code (base class) |

All exceptions inherit from `APIError` which exposes `.code` and `.message`.

## License

MIT
