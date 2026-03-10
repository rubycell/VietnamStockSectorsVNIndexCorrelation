# Portfolio Trading System — Design Specification

**Date**: 2026-03-10
**Status**: Approved
**Author**: Brainstorming session with user

## Overview

A hybrid trading portfolio management system that:
1. Ingests TCBS trade history exports (XLSX)
2. Maintains a unified portfolio with real-time P&L
3. Evaluates 9 custom trading rules against live price data
4. Uses AI agents (Claude) for FUD assessment and dynamic market insights
5. Sends alerts via Telegram and WhatsApp (Evolution API)
6. Extends the existing TradingView Lightweight Charts dashboard

## Architecture

### System Components

```
FastAPI Server (API + Dashboard static files)
    │
    ├── Upload API (XLSX ingest)
    ├── Portfolio API (holdings, P&L)
    ├── Rules API (config, status)
    ├── Alerts API (history, test)
    ├── Agents API (CRUD, execute, logs)
    └── Prices API (on-demand fetch)

Redis (Celery broker + result backend)
    │
    ├── Celery Workers (deterministic tasks)
    │   ├── PriceFetcher — vnstock API, hourly 9am-3pm GMT+7
    │   ├── PortfolioCalculator — holdings, VWAP, P&L
    │   ├── SwingLowDetector — custom SMA(10) method
    │   ├── RuleEvaluator — deterministic rule checks
    │   └── AlertSender — Evolution API delivery
    │
    ├── Celery Beat (scheduler)
    │   └── Hourly checks 9am-3pm GMT+7 + on-demand
    │
    ├── AI Agent Worker (Claude API)
    │   └── FUDAssessor — structured FUD level assessment
    │
    └── Code-Gen Agent Worker (Claude API + exec)
        └── Dynamic agents: generate Python, execute on dataset

SQLite (trades, holdings, prices, config, agents, agent_runs, alerts)

Evolution API (Docker) → Telegram + WhatsApp

Existing dashboard/ extended with new tabs
```

### Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI, uvicorn |
| Task queue | Celery + Redis |
| Database | SQLite + SQLAlchemy |
| AI | Claude API (Haiku 4.5 for assessments) |
| Price data | vnstock (VCI source, 1D resolution) |
| Alerting | Evolution API (Docker) → Telegram + WhatsApp |
| Frontend | Vanilla HTML/JS/CSS, TradingView Lightweight Charts v5 |
| Deployment | Docker Compose (Redis + Evolution API), native Python |

## Data Pipeline

### TCBS XLSX Parser

**Input**: TCBS "Lich su giao dich co phieu" export files

**Format**: 16 columns, header at row 15 (0-indexed: row 14), preceded by TCBS branding/address rows.

**Metadata extracted from header rows**:
- Row 10: Account type — "Ky quy" (margin) or "Thuong" (normal)
- Row 9: Date range of the report

### Cleaning Steps

1. **Parse headers** — skip first 14 rows, extract column names from row 15
2. **Normalize columns** to English names:
   - `ticker` (Ma CP)
   - `trading_date` (Ngay GD) — parse DD/MM/YYYY to date
   - `trade_side` — "Mua" → BUY, "Ban" → SELL
   - `order_volume` (KL dat)
   - `order_price` (Gia dat, VND)
   - `matched_volume` (KL khop)
   - `matched_price` (Gia khop, VND)
   - `matched_value` (Gia tri khop, VND)
   - `fee` (Phi, VND)
   - `tax` (Thue, VND)
   - `cost_basis` (Gia von) — per-share, as reported by TCBS
   - `return_pnl` (Lai lo, VND) — realized P&L per fill
   - `channel` (Kenh GD)
   - `status` (Trang thai) — "Hoan tat" or "Da khop"
   - `order_type` (Loai lenh) — "Lenh thuong", etc.
   - `order_no` (So hieu lenh) — unique per order
3. **Tag account type** — margin or normal (from header metadata)
4. **Store individual fills** in `trade_fills` table
5. **Aggregate split fills** — same `order_no` → compute aggregate in `trades` table:
   - total_matched_volume = SUM(matched_volume)
   - vwap_matched_price = SUM(matched_value) / total_matched_volume
   - total_fee = SUM(fee)
   - total_tax = SUM(tax)
6. **Deduplicate** — on `(order_no, matched_price, matched_volume)` to prevent re-import
7. **Validate** — reject rows with missing ticker, date, or matched_volume
8. **Tag import batch** — `import_batch_id` for traceability

### Known Data Quirks

- File 1 (margin): OrderNo is a hex string like `800006032602F65C`
- File 2 (normal): OrderNo is parsed as float by pandas (e.g., `8.000170e+15`) — must read as string
- Footer rows contain "Ngay xuat bao cao", "Report Date", "Chu thich" — must be filtered out
- "Tong" (Total) rows may appear — must be filtered

## Portfolio Engine

### Holdings Calculation

All trades merged into one unified portfolio (margin + normal combined).

```
For each ticker:
  buys = all fills WHERE trade_side = BUY
  sells = all fills WHERE trade_side = SELL

  total_bought = SUM(buys.matched_volume)
  total_sold = SUM(sells.matched_volume)
  current_holding = total_bought - total_sold

  vwap_cost = SUM(buys.matched_value + buys.fee) / total_bought

  realized_pnl = SUM(sells.return_pnl)

  If current_holding > 0:
    unrealized_pnl = (current_price - vwap_cost) * current_holding
```

### Position Numbering

For trading rules that reference "position #1" and "position #2":
- **Position #1** = first/initial buy order for a ticker
- **Position #2+** = any subsequent buy orders (add-ons, averaging down)
- Tracked by counting distinct BUY order_no per ticker, ordered chronologically

## Data Model (SQLite)

### Tables

| Table | Purpose |
|---|---|
| `trade_fills` | Individual fill rows from TCBS exports |
| `trades` | Aggregated orders (one row per order_no) |
| `holdings` | Current portfolio state per ticker |
| `prices` | Daily OHLCV cache from vnstock |
| `swing_lows` | Detected swing lows per ticker |
| `price_levels` | Important price levels (auto + manual) per ticker |
| `alerts` | Alert history with delivery status |
| `config` | Key-value settings (thresholds, API keys, etc.) |
| `agents` | Agent definitions (name, prompt, schedule, enabled) |
| `agent_runs` | Execution log (input, generated code, output, errors) |
| `import_batches` | XLSX import tracking (filename, date, row count) |

### Key Schemas

**trade_fills**:
`id, order_no, ticker, trading_date, trade_side, matched_volume, matched_price, matched_value, fee, tax, cost_basis, return_pnl, channel, status, order_type, account_type, import_batch_id`

**agents**:
`id (slug), name, description, type (structured|code_gen), prompt_template, schedule (hourly|daily|on_demand), enabled, alert_on_result, created_at, updated_at`

**agent_runs**:
`id, agent_id, started_at, completed_at, status (success|error), generated_code, input_context, output_json, error_message`

## Trading Rules Engine

### Swing Low Detection (Custom Algorithm)

```
Input: Daily OHLCV for a ticker
Parameters: SMA period = 10

1. Compute SMA(close, 10)
2. Find Point A: candle where close < SMA(10)
3. Find Point B: next candle where close > SMA(10) AND low > SMA(10)
4. Swing low = MIN(low) of all candles from A to B inclusive
5. Confirmed when Point B is found
6. Track most recent confirmed swing low per ticker
```

### Important Price Levels (Rule #8)

Three sources, merged per ticker:
1. **Resistance zones** — auto-detected from swing highs (inverse of swing low algo)
2. **Round numbers** — nearest 5,000 and 10,000 VND increments around current price
3. **Manual levels** — user-configured via dashboard

### Rule Definitions

| Rule | ID | Trigger condition | Alert message template |
|---|---|---|---|
| #1 | `no_prediction` | Always | Dashboard disclaimer only |
| #2 | `fud_reduce_size` | FUD detected (configurable volatility threshold OR sector >50% oversold) | "{ticker}: FUD detected in {sector}. Consider reducing planned action size." |
| #3 | `no_fomo_swap` | Passive reminder | Dashboard reminder when buying new ticker while holding losers |
| #4 | `below_swing_low_sell` | `close < latest_confirmed_swing_low` | "CRITICAL: {ticker} closed at {price} below swing low {swing_low}. Rule #4: consider selling." |
| #5 | `stick_to_strategy` | Always | Dashboard labels each position's strategy |
| #6 | `fud_reduce_further` | FUD escalates from previous check | "{ticker}: FUD intensifying. Consider further size reduction." |
| #7 | `ptp_to_swing_low` | Position #2+ AND in profit | "{ticker} position #2+. BE at {be}, nearest swing low at {sl}. Consider partial take-profit to pull BE to swing low." |
| #8 | `high_entry_sell_levels` | Position #1 AND price reaches important level | "{ticker} reaching important level {level}. Entry was high at {entry}. Consider partial sell." |
| #9 | `stoploss_all_pos2` | Position #2+ AND `close < swing_low` | "CRITICAL: {ticker} position #2+ below swing low. Rule #9: stop-loss all, may keep up to 200 shares." |

### FUD Detection

**Volatility-based**: VN-Index daily change exceeds configurable threshold (user sets via dashboard).

**Sector sentiment**: Reuse existing oversold indicators from `export_web_data.py`:
- If >50% of a sector's stocks meet any oversold condition (stoch_20, smi_40, sma_50), flag sector as FUD.

### Alert Deduplication

- Same rule + same ticker = max 1 alert per day
- Escalation: if condition worsens, send follow-up alert

## AI Agent Framework

### Agent Types

1. **Structured AI** (`type: structured`): Claude receives data, returns structured JSON. No code generation. Example: FUD Assessor.

2. **Code-Gen AI** (`type: code_gen`): Claude generates Python code from a prompt template, code is executed with `exec()` against the dataset. Full trust (runs in Docker container).

### Code-Gen Execution Flow

1. Celery task triggers agent by schedule or on-demand
2. Load agent definition from `agents` table
3. Send to Claude API (Haiku 4.5):
   - System prompt: analyst role, generate pandas/numpy code, return JSON
   - User prompt: filled prompt_template + table schemas + sample rows
4. Claude returns Python code
5. Execute with `exec()`:
   - Available: pandas, numpy, datetime, json
   - SQLite connection (read-only access to prices, trades, sectors tables)
6. Capture result (JSON)
7. If `alert_on_result` and result is non-empty, queue alert
8. Log to `agent_runs` table

### Claude API Usage

- Model: `claude-haiku-4-5`
- Max 1 API call per agent per execution cycle
- Estimated cost: ~$0.001 per call, ~6 calls/day for hourly agents = ~$0.006/day
- Fallback: if API fails, log error, skip AI context in alerts

### Initial Agents (10)

| ID | Name | Type | Schedule |
|---|---|---|---|
| `fud-assessor` | FUD Assessor | structured | On rule trigger |
| `trendy-sector-detector` | Trendy Sector Detector | code_gen | Hourly |
| `unusual-volume-scanner` | Unusual Volume Scanner | code_gen | Hourly |
| `sector-rotation-tracker` | Sector Rotation Tracker | code_gen | Daily |
| `oversold-bounce-finder` | Oversold Bounce Finder | code_gen | Daily |
| `correlation-breakdown-alert` | Correlation Breakdown Alert | code_gen | Daily |
| `portfolio-risk-monitor` | Portfolio Risk Monitor | code_gen | Hourly |
| `earnings-momentum-scanner` | Earnings Momentum Scanner | code_gen | Daily |
| `support-level-proximity` | Support Level Proximity | code_gen | Hourly |
| `market-breadth-analyzer` | Market Breadth Analyzer | code_gen | Daily |

### Dashboard Agent Management

- **Agents tab**: List all agents with enable/disable toggle
- **Create agent**: Form with name, description, prompt template (with `{variable}` placeholders), schedule dropdown, alert toggle
- **Agent runs log**: Table showing execution history, generated code viewer, result viewer, errors
- **Test run**: Execute once and preview results before enabling scheduled runs

## Alerting

### Evolution API (Docker)

- Runs in Docker via `docker-compose.yml`
- Provides unified API for both Telegram and WhatsApp
- Config stored in `config` table: API key, instance name, Telegram bot token, WhatsApp number

### Alert Message Format

```
[CRITICAL/WARNING] RULE #{n} — {TICKER}

{description of what triggered}

Context:
- Holding: {shares} shares @ avg {cost}
- Unrealized P&L: {pnl} ({pct}%)
- FUD status: {fud_level} ({fud_summary})
- AI insight: {agent_summary} (if available)

{timestamp} GMT+7
```

### Delivery

- Send to both Telegram and WhatsApp simultaneously
- If Evolution API is down, log alert to SQLite, show in dashboard
- Alert history viewable in dashboard Alerts tab

## Dashboard

### Tab Navigation

Extends existing `dashboard/` with tab-based navigation:

| Tab | Source file | Content |
|---|---|---|
| Sectors | `app.js` (existing) | VN-Index vs sector oversold indicators |
| Portfolio | `portfolio.js` (new) | Holdings table, P&L summary, per-ticker charts |
| Trades | `trades.js` (new) | Trade history, filtering, XLSX upload |
| Rules | `rules.js` (new) | Rule status per ticker, swing lows, price levels |
| Agents | `agents.js` (new) | Agent management, runs log, create/edit |
| Alerts | `alerts.js` (new) | Alert history log, test button |
| Config | `config.js` (new) | FUD thresholds, manual price levels, API settings |

### Portfolio View

- Summary cards: total value, unrealized P&L, realized P&L, FUD indicator
- Holdings table: Ticker, Shares, VWAP Cost, Current Price, Unrealized P&L %, Nearest Swing Low, Rule Status
- Click ticker → price chart with swing lows marked, BE line, important price levels
- Upload button for TCBS XLSX files

### Technology

- Vanilla HTML/JS/CSS (matches existing dashboard)
- TradingView Lightweight Charts v5 (CDN, already in use)
- New tabs as separate JS modules loaded on demand
- All data fetched from FastAPI endpoints

## File Structure

```
vnstocksectorvnindexcorrelation/
├── CLAUDE.md
├── README.md
├── requirements.txt              # updated
├── docker-compose.yml            # Redis + Evolution API
├── Dockerfile                    # Full app container
│
├── app/
│   ├── main.py                   # FastAPI app entry
│   ├── config.py                 # Settings, env vars
│   ├── database.py               # SQLite setup, migrations
│   ├── models.py                 # SQLAlchemy + Pydantic models
│   │
│   ├── api/
│   │   ├── upload.py             # POST /api/upload
│   │   ├── portfolio.py          # GET /api/portfolio
│   │   ├── rules.py              # GET/PUT /api/rules
│   │   ├── alerts.py             # GET/POST /api/alerts
│   │   ├── prices.py             # GET /api/prices
│   │   └── agents.py             # CRUD + execute /api/agents
│   │
│   ├── pipeline/
│   │   ├── parser.py             # TCBS XLSX parser
│   │   ├── cleaner.py            # Normalize, validate
│   │   └── deduplicator.py       # Duplicate detection
│   │
│   ├── engine/
│   │   ├── portfolio.py          # Holdings, VWAP, P&L
│   │   ├── swing_low.py          # Custom SMA(10) swing low
│   │   ├── rules.py              # Deterministic rule evaluator
│   │   ├── price_levels.py       # Resistance, round numbers, manual
│   │   └── fud.py                # FUD detection logic
│   │
│   ├── agents/
│   │   ├── base.py               # Agent base class
│   │   ├── fud_assessor.py       # Built-in FUD agent
│   │   ├── code_executor.py      # exec() runner
│   │   └── registry.py           # Load agents from DB
│   │
│   └── tasks/
│       ├── celery_app.py         # Celery configuration
│       ├── price_fetch.py        # Hourly price fetcher
│       ├── rule_check.py         # Full check cycle orchestrator
│       └── alert_send.py         # Evolution API sender
│
├── dashboard/
│   ├── index.html                # Updated with tabs
│   ├── app.js                    # Existing sector chart
│   ├── portfolio.js              # Portfolio view
│   ├── trades.js                 # Trade history + upload
│   ├── rules.js                  # Rules status
│   ├── agents.js                 # Agent management
│   ├── alerts.js                 # Alert history
│   ├── config.js                 # Settings panel
│   ├── styles.css                # Shared styles
│   └── data.json                 # Existing sector data
│
├── data/                         # Existing data cache
├── plots/                        # Existing plots
├── docs/superpowers/specs/       # This document
│
├── analyze_all_sectors.py        # Existing
├── cache_sectors.py              # Existing
├── export_web_data.py            # Existing
└── fetch_vn30f1m.py              # Existing
```

## Dependencies

**New additions to requirements.txt**:
```
fastapi
uvicorn[standard]
celery[redis]
redis
sqlalchemy
python-multipart
anthropic
httpx
apscheduler
vnstock
pandas
openpyxl
numpy
pytz
```

## Running the System

```bash
# 1. Start Redis + Evolution API (Docker)
docker-compose up -d

# 2. Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# 4. Start Celery Beat (scheduler)
celery -A app.tasks.celery_app beat --loglevel=info
```

Or with Docker Compose (full stack):
```bash
docker-compose --profile full up -d
```

## Data Files Analyzed

- **File 1**: Margin account (Ky quy), 209 trades, 32 tickers, Mar 2025 — Mar 2026
- **File 2**: Normal account (Thuong), 155 trades, 25 tickers, Mar 2025 — Mar 2026
- **Total**: 364 trade fills across 2 accounts
- **Tickers**: ACB, BCM, BID, CTG, CTR, DCM, DGC, DGW, DXG, FPT, FRT, GAS, GMD, HCM, HPG, IDC, KDH, MBB, MBS, MCH, MSN, MWG, NLG, PDR, PNJ, SSI, TCB, TCX, VCB, VHC, VHM, VIC, VNM, VPB, VPL, VRE
