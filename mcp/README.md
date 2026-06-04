# TradeInsight MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI assistants real-time access to stock market data via the [TradeInsight API](https://tradeinsight.info).

**Endpoint:** `https://api.tradeinsight.info/mcp`  
**Protocol:** Streamable HTTP (JSON-RPC 2.0)

## Tools

### `get_price_history`

Get daily OHLCV price history for a stock ticker.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | string | yes | Ticker symbol, e.g. `"AAPL"` |
| `start_date` | string | no | Start date `YYYY-MM-DD` (default: 1 year ago) |
| `end_date` | string | no | End date `YYYY-MM-DD` (default: today) |
| `limit` | integer | no | Max rows 1–1000 (default 365) |
| `adjusted` | boolean | no | Use split/dividend-adjusted prices (default `true`) |

### `get_top_movers`

Get tickers ranked by volume, 20-day moving average, or price change.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sort_by` | string | yes | `"volume"`, `"moving_average"`, or `"price_change"` |
| `limit` | integer | no | Max results 1–50 (default 10) |

### `search_ticker`

Search for stock tickers by company name substring.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Company name substring, e.g. `"apple"` |
| `limit` | integer | no | Max results 1–50 (default 20) |

## Setup

### Get an API key

Sign up at [tradeinsight.info](https://tradeinsight.info) to get your API key.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tradeinsight": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://api.tradeinsight.info/mcp",
        "--header",
        "Authorization: Bearer YOUR_API_KEY"
      ]
    }
  }
}
```

### Claude Code

```bash
claude mcp add tradeinsight \
  --transport http \
  --url https://api.tradeinsight.info/mcp \
  --header "Authorization: Bearer YOUR_API_KEY"
```

### Cursor / other MCP clients

Use transport `streamable-http`, URL `https://api.tradeinsight.info/mcp`, and set the `Authorization: Bearer <key>` header.

## Authentication

All requests require a `Bearer` token in the `Authorization` header:

```
Authorization: Bearer ti_xxxxxxxxxxxx
```

Requests without a valid key return JSON-RPC error `-32001` (Unauthorized).

## Rate limits

Rate limits are enforced per API key and tier. When exceeded the server returns JSON-RPC error `-32029` with a `retry_after` field (seconds).

## Error codes

| Code | Meaning |
|------|---------|
| `-32700` | Parse error — malformed JSON body |
| `-32602` | Invalid params — missing required field or bad value |
| `-32601` | Method not found — unknown method or tool name |
| `-32001` | Unauthorized — missing or invalid API key |
| `-32029` | Rate limited — includes `data.retry_after` (seconds) |
| `-32002` | No data — ticker not found |
| `-32603` | Internal error |

## Python client

For programmatic access without MCP, use the [tidata](https://github.com/TradeInsight-Info/tidata) Python library:

```python
from tidata.tifinance import Ticker

t = Ticker("AAPL")
df = t.history(period="1y")
print(df.head())
```
