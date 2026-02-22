# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Analyzes correlations between Vietnamese stock sectors and the VN-Index. Calculates three oversold indicators (Stochastic < 20, SMI < -40, Close < SMA-50) per ICB Level 2 sector, exports results to JSON, and visualizes them in a TradingView Lightweight Charts dashboard.

## Commands

```bash
# Setup
source venv/bin/activate
pip install vnstock pandas numpy pytz

# Data pipeline (run in order)
python cache_sectors.py          # 1. Cache ICB sector definitions to data/sectors_level2.csv
python analyze_all_sectors.py    # 2. Fetch stock OHLCV, compute stochastic, save to data/1D/*.csv + plots/
python export_web_data.py        # 3. Compute all 3 indicators, export dashboard/data.json

# Derivatives data
python fetch_vn30f1m.py          # Fetch VN30F1M 5m candles with rate-limit-safe chunking

# Dashboard
cd dashboard && python -m http.server 8000   # Serve at http://localhost:8000
```

## Architecture

### Data Pipeline Flow

```text
vnstock API (VCI source)
    │
    ├─ cache_sectors.py ──► data/sectors_level2.csv, sectors_level3.csv
    │
    ├─ analyze_all_sectors.py ──► data/1D/{TICKER}.csv (cached OHLCV)
    │                             plots/vn_index_vs_{sector}.png
    │
    └─ export_web_data.py ──► dashboard/data.json
                                  │
                          dashboard/app.js reads data.json
                          renders dual-axis chart (VN-Index left, indicator % right)
```

- **Daily stock data** uses `Quote(symbol, source='VCI')` with `resolution='1D'`
- **Derivatives intraday data** uses `Vnstock(source='KBS')` with `interval='5m'`
- Stock data is cached incrementally in `data/1D/` — only fetches new dates beyond what's cached
- `export_web_data.py` reads only from cache (no API calls), so it's safe to re-run

### Dashboard

Vanilla HTML/JS/CSS using TradingView Lightweight Charts v5 (CDN). `data.json` structure:

```json
{
  "dates": ["2016-01-04", ...],
  "vnindex": [560.27, ...],
  "indicators": {"stoch_20": "...", "smi_40": "...", "sma_50": "..."},
  "sectors": {
    "Ngân hàng": {"stoch_20": [...], "smi_40": [...], "sma_50": [...], "count": 15}
  }
}
```

### Indicator Calculations (in export_web_data.py)

| Indicator  | Threshold          | Meaning                                        |
| ---------- | ------------------ | ---------------------------------------------- |
| `stoch_20` | Stochastic %K < 20 | % of sector stocks oversold                    |
| `smi_40`   | SMI < -40          | % of sector stocks with bearish momentum       |
| `sma_50`   | Close < SMA(50)    | % of sector stocks below 50-day moving average |

Each indicator value is the percentage of stocks in a sector meeting the condition on each date.

## vnstock API Reference

### Two API styles in this codebase

1. **VCI source** (daily data, sector listings): `Quote(symbol='VCB', source='VCI')`, `Listing(source='VCI')`
2. **KBS source** (intraday/derivatives): `Vnstock(source='KBS').stock(symbol='VN30F1M')`

### Rate Limits (Guest Tier)

- **20 requests/minute** — use 5-second sleep between requests
- vnstock's internal retry mechanism consumes quota (account for this)
- Rate limit errors display Vietnamese text with wait time in seconds

### Intraday Data (KBS)

- ~6 months of 5-minute history available
- Single request caps at ~3789 rows — chunk by 30-day windows to get complete data
- Deduplicate on `time` column after combining chunks
- Intervals: `1m`, `5m`, `15m`, `30m`, `1H`, `1D`, `1W`, `1M`

### Symbol Formats

- Stocks: `VCB`, `FPT`, `PLX`
- Indices: `VNINDEX`
- Derivatives: `VN30F1M` (1st month), `VN30F2M`, `VN30F1Q` (auto-converted to KRX format)

### Pitfalls

- `pytz` is not auto-installed with vnstock — install it separately
- Expired futures contract dates return empty data (not an error)
- `analyze_all_sectors.py` can take a long time due to rate limits across hundreds of stocks
