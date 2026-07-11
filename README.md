# trading-data-py

Python client for the [TradeInsight](https://tradeinsight.info) Trading Data Service API.
Provides a `Ticker` class with a `history()` method that returns a pandas DataFrame
with yfinance-compatible column names.

## Installation

```bash
pip install trading-data-py
```

Or install from source:

```bash
git clone https://github.com/tradeinsight/trading-data-py.git
cd trading-data-py
pip install -e .
```

## Quick Start

Set your API key in the environment:

```bash
export TIDATA_API_KEY=your_key_here
```

Then use the client:

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
