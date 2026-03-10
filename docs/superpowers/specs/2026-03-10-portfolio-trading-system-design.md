# Portfolio Trading System — Design Specification

**Date**: 2026-03-10
**Status**: Approved (v2 — Hybrid OpenClaw + FastAPI)
**Author**: Brainstorming session with user

## Overview

A hybrid trading portfolio management system that:
1. Ingests TCBS trade history exports (XLSX)
2. Maintains a unified portfolio with real-time P&L
3. Evaluates 9 custom trading rules against live price data
4. Uses AI agents (Claude) for FUD assessment and dynamic market insights
5. Sends alerts via Telegram and WhatsApp (OpenClaw built-in channels)
6. Extends the existing TradingView Lightweight Charts dashboard

## Architecture

### Hybrid: OpenClaw + FastAPI

OpenClaw handles messaging (Telegram/WhatsApp), scheduling (cron jobs), and agent orchestration.
FastAPI handles VN stock-specific domain logic, data pipeline, and serves the dashboard.

```
┌──────────────── Docker Compose ─────────────────┐
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │         OpenClaw Gateway                 │    │
│  │                                          │    │
│  │  Channels:                               │    │
│  │  ├── Telegram (Bot API)                  │    │
│  │  └── WhatsApp (Baileys / QR link)        │    │
│  │                                          │    │
│  │  Cron Scheduler:                         │    │
│  │  ├── Hourly checks (9am-3pm GMT+7)      │    │
│  │  └── Daily reports                       │    │
│  │                                          │    │
│  │  Skills (SKILL.md files):                │    │
│  │  ├── check-portfolio                     │    │
│  │  ├── evaluate-rules                      │    │
│  │  ├── run-agent                           │    │
│  │  ├── fetch-prices                        │    │
│  │  └── full-check-cycle                    │    │
│  └──────────────┬──────────────────────────┘    │
│                  │ HTTP (docker network)         │
│  ┌──────────────▼──────────────────────────┐    │
│  │         FastAPI Backend                  │    │
│  │                                          │    │
│  │  /api/health                             │    │
│  │  /api/upload      (TCBS xlsx ingest)    │    │
│  │  /api/portfolio   (holdings, P&L)       │    │
│  │  /api/prices      (fetch via vnstock)   │    │
│  │  /api/rules       (evaluate rules)      │    │
│  │  /api/swing-lows  (detection)           │    │
│  │  /api/agents      (CRUD + execute)      │    │
│  │  /api/alerts      (history, create)     │    │
│  │  /api/config      (thresholds, levels)  │    │
│  │                                          │    │
│  │  SQLite (portfolio.db)                   │    │
│  │  Code-Gen Engine (exec runner)           │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  Dashboard: http://localhost:8000                 │
└──────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology |
|---|---|
| Agent orchestration | OpenClaw (gateway + skills + cron) |
| Messaging | OpenClaw built-in Telegram + WhatsApp |
| Scheduling | OpenClaw cron jobs |
| Backend | Python, FastAPI, uvicorn |
| Database | SQLite + SQLAlchemy |
| AI (code-gen agents) | Claude API (Haiku 4.5) via FastAPI |
| AI (reasoning/chat) | OpenClaw's built-in Claude integration |
| Price data | vnstock (VCI source, 1D resolution) |
| Frontend | Vanilla HTML/JS/CSS, TradingView Lightweight Charts v5 |
| Deployment | Docker Compose (OpenClaw + FastAPI) |

### What OpenClaw Replaces

| Removed | Replaced by |
|---|---|
| Celery + Redis | OpenClaw cron + direct HTTP calls to FastAPI |
| Celery Beat scheduler | OpenClaw `cron add --cron "0 9-15 * * 1-5"` |
| Evolution API | OpenClaw built-in Telegram + WhatsApp channels |
| Custom alert sender | OpenClaw `--announce --channel telegram` |

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

2. **Code-Gen AI** (`type: code_gen`): Claude generates Python code from a prompt template, code is executed against the dataset. Full trust (runs in Docker container).

### Code-Gen Execution Flow

1. OpenClaw cron or on-demand trigger calls `POST /api/agents/{id}/execute`
2. FastAPI loads agent definition from `agents` table
3. Sends to Claude API (Haiku 4.5):
   - System prompt: analyst role, generate pandas/numpy code, return JSON
   - User prompt: filled prompt_template + table schemas + sample rows
4. Claude returns Python code
5. Execute with `exec()`:
   - Available: pandas, numpy, datetime, json
   - SQLite connection (read-only access to prices, trades, sectors tables)
6. Capture result (JSON)
7. If `alert_on_result` and result is non-empty, return to OpenClaw for delivery
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

## OpenClaw Integration

### Skills

Each skill is a `SKILL.md` file in `openclaw/skills/` that teaches OpenClaw how to call FastAPI endpoints.

| Skill | Triggers | FastAPI endpoint |
|---|---|---|
| `check-portfolio` | "How's my portfolio?" or cron | `GET /api/portfolio` |
| `evaluate-rules` | "Check my rules" or cron | `POST /api/rules/evaluate` |
| `run-agent` | "Run [agent name]" | `POST /api/agents/{id}/execute` |
| `fetch-prices` | "Update prices" or cron | `POST /api/prices/fetch` |
| `full-check-cycle` | Hourly cron (9am-3pm) | `POST /api/check-cycle` |
| `upload-trades` | "I have new trades" | Instructs user to use dashboard upload |

### Cron Jobs

```bash
# Hourly check during market hours (Mon-Fri, 9am-3pm GMT+7)
openclaw cron add --name "hourly-check" \
  --cron "0 9-15 * * 1-5" --tz "Asia/Ho_Chi_Minh" \
  --session isolated \
  --message "Run the full check cycle and report any triggered rules" \
  --announce --channel telegram --to "${TELEGRAM_CHAT_ID}"

# Daily end-of-day report
openclaw cron add --name "daily-report" \
  --cron "0 16 * * 1-5" --tz "Asia/Ho_Chi_Minh" \
  --session isolated \
  --message "Generate end-of-day portfolio summary and run all daily agents" \
  --announce --channel telegram --to "${TELEGRAM_CHAT_ID}"
```

### Alert Delivery via OpenClaw

When FastAPI's rule evaluator detects a trigger:
1. FastAPI stores alert in `alerts` table
2. Returns alert data to OpenClaw (via skill response)
3. OpenClaw formats and sends to Telegram + WhatsApp via its built-in channels
4. OpenClaw's cron `--announce` flag auto-delivers to configured channels

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
| Config | `config.js` (new) | FUD thresholds, manual price levels, settings |

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
├── docker-compose.yml            # OpenClaw + FastAPI
├── Dockerfile                    # FastAPI container
├── .env                          # secrets (not committed)
│
├── app/                          # FastAPI backend
│   ├── main.py                   # FastAPI app entry
│   ├── config.py                 # Settings, env vars
│   ├── database.py               # SQLite setup
│   ├── models.py                 # SQLAlchemy models
│   │
│   ├── api/
│   │   ├── upload.py             # POST /api/upload
│   │   ├── portfolio.py          # GET /api/portfolio
│   │   ├── rules.py              # GET/POST /api/rules
│   │   ├── alerts.py             # GET/POST /api/alerts
│   │   ├── prices.py             # GET/POST /api/prices
│   │   ├── agents.py             # CRUD + execute /api/agents
│   │   ├── config.py             # GET/PUT /api/config
│   │   └── check_cycle.py        # POST /api/check-cycle
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
│   └── agents/
│       ├── base.py               # Agent base class
│       ├── code_executor.py      # exec() runner
│       └── registry.py           # Load agents from DB
│
├── openclaw/                     # OpenClaw configuration
│   ├── openclaw.json             # Channel config (Telegram, WhatsApp)
│   └── skills/
│       ├── check-portfolio/
│       │   └── SKILL.md
│       ├── evaluate-rules/
│       │   └── SKILL.md
│       ├── run-agent/
│       │   └── SKILL.md
│       ├── fetch-prices/
│       │   └── SKILL.md
│       └── full-check-cycle/
│           └── SKILL.md
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
├── tests/
│   ├── test_database.py
│   ├── test_pipeline.py
│   ├── test_portfolio.py
│   ├── test_rules.py
│   ├── test_swing_low.py
│   ├── test_agents.py
│   ├── test_api_*.py
│   └── test_integration.py
│
├── data/                         # Existing data cache
├── plots/                        # Existing plots
├── docs/superpowers/             # Design docs and plans
│
├── analyze_all_sectors.py        # Existing
├── cache_sectors.py              # Existing
├── export_web_data.py            # Existing
└── fetch_vn30f1m.py              # Existing
```

## Dependencies

**requirements.txt** (updated):
```
vnstock
pandas
numpy
pytz
openpyxl
fastapi
uvicorn[standard]
sqlalchemy
python-multipart
anthropic
httpx
pytest
pytest-asyncio
```

No Celery, no Redis — OpenClaw handles scheduling and messaging.

## Docker Compose

```yaml
version: "3.8"

services:
  fastapi:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./dashboard:/app/dashboard
    environment:
      - DATABASE_URL=sqlite:///data/portfolio.db
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - app-net

  openclaw:
    image: ghcr.io/openclaw/openclaw:latest
    volumes:
      - ./openclaw:/home/node/.openclaw
    ports:
      - "18789:18789"
    environment:
      - HOME=/home/node
    command: ["node", "dist/index.js", "gateway", "--bind", "lan"]
    depends_on:
      fastapi:
        condition: service_healthy
    networks:
      - app-net

networks:
  app-net:
```

## Running the System

```bash
# Start everything
docker-compose up -d

# First time: set up OpenClaw channels
docker-compose exec openclaw openclaw setup    # Telegram bot token, WhatsApp QR

# Add cron jobs
docker-compose exec openclaw openclaw cron add \
  --name "hourly-check" \
  --cron "0 9-15 * * 1-5" --tz "Asia/Ho_Chi_Minh" \
  --session isolated \
  --message "Run the full check cycle" \
  --announce --channel telegram

# Dashboard
open http://localhost:8000
```

## Testing Strategy

### Three test layers

1. **Unit tests** (pytest, inside FastAPI container):
   - Pipeline: parser, cleaner, deduplicator
   - Engine: portfolio calc, swing low, rules, FUD, price levels
   - Agents: base class, code executor, registry
   - Run: `docker-compose exec fastapi pytest tests/ -v`

2. **Integration tests** (pytest, FastAPI + SQLite):
   - Full API flows: upload → portfolio → rules → alerts
   - Agent CRUD + execute with mocked Claude
   - Run: `docker-compose exec fastapi pytest tests/test_integration.py -v`

3. **E2E tests** (OpenClaw skill → FastAPI → verify):
   - Trigger skill via OpenClaw CLI, verify FastAPI response
   - Cron trigger → check alert created in DB
   - Run: `docker-compose exec openclaw openclaw cron run <jobId> --due`

### docker-compose.test.yml

```yaml
version: "3.8"

services:
  test-runner:
    build: .
    command: pytest tests/ -v --tb=short
    volumes:
      - ./data:/app/data
      - ./tests:/app/tests
    environment:
      - DATABASE_URL=sqlite:///tmp/test.db
      - ANTHROPIC_API_KEY=test-key
    networks:
      - app-net

  fastapi:
    build: .
    networks:
      - app-net

networks:
  app-net:
```

Run: `docker-compose -f docker-compose.test.yml up --abort-on-container-exit`

## Data Files Analyzed

- **File 1**: Margin account (Ky quy), 209 trades, 32 tickers, Mar 2025 — Mar 2026
- **File 2**: Normal account (Thuong), 155 trades, 25 tickers, Mar 2025 — Mar 2026
- **Total**: 364 trade fills across 2 accounts
- **Tickers**: ACB, BCM, BID, CTG, CTR, DCM, DGC, DGW, DXG, FPT, FRT, GAS, GMD, HCM, HPG, IDC, KDH, MBB, MBS, MCH, MSN, MWG, NLG, PDR, PNJ, SSI, TCB, TCX, VCB, VHC, VHM, VIC, VNM, VPB, VPL, VRE
