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
export TRADING_DATA_API_KEY=your_key_here
```

Then use the client:

```python
from trading_data import Ticker

# API key is read from TRADING_DATA_API_KEY env var automatically
t = Ticker("AAPL")

# Adjusted prices (yfinance-compatible)
df = t.history(start="2024-01-01", end="2024-12-31")
print(df.head())
#                  Open        High         Low       Close      Volume  Dividends  Stock Splits
# Date
# 2024-01-02  184.210...  185.880...  183.430...  185.200...  79047200.0        0.0           0.0

# Raw (unadjusted) prices
df_raw = t.history(start="2024-01-01", end="2024-12-31", auto_adjust=False)
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `symbol` | Ticker symbol (e.g. `"AAPL"`) | required |
| `api_key` | API key — also reads `TRADING_DATA_API_KEY` env var | `None` |
| `base_url` | API base URL | `https://api.tradeinsight.info` |
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
