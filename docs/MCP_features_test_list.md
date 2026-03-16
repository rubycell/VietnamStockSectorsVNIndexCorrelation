# MCP Server — 36 Tools Manual Test List

> **Server:** `openclaw/mcp/portfolio_server.py`
> **Backend:** `http://localhost:8000` (host) / `http://fastapi:8000` (Docker)
> **Tests:** `tests/test_mcp_server.py` (69 automated tests)

## Prerequisites

```bash
# Start FastAPI backend
docker compose up -d fastapi

# Or run locally
source venv/bin/activate && uvicorn app.main:app --port 8000

# MCP server (stdio, for JSON-RPC testing)
FASTAPI_URL=http://localhost:8000 python3 openclaw/mcp/portfolio_server.py
```

## How to Test via MCP JSON-RPC

Pipe a JSON-RPC message with Content-Length framing to the MCP server:

```bash
MSG='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"TOOL_NAME","arguments":{}}}'
printf "Content-Length: %d\r\n\r\n%s" ${#MSG} "$MSG" | \
  FASTAPI_URL=http://localhost:8000 python3 openclaw/mcp/portfolio_server.py
```

---

## Group 1: Portfolio & Trading (11 tools)

### 1. get_portfolio

Full portfolio summary with all holdings, P&L, and position status.

| | |
|---|---|
| **Method** | `GET /api/portfolio` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/portfolio | jq .
```

**MCP:**
```json
{"name": "get_portfolio", "arguments": {}}
```

**Verify:**
- [ ] Response contains `holdings` array
- [ ] Each holding has `ticker`, `total_shares`, `avg_cost`, `current_price`
- [ ] P&L values are numeric (not null)
- [ ] Empty portfolio returns `{"holdings": [], ...}`

---

### 2. get_portfolio_ticker

Detailed holdings for a single ticker including position breakdown and OHLCV.

| | |
|---|---|
| **Method** | `GET /api/portfolio/{ticker}` |
| **Required** | `ticker` (string) |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/portfolio/VCB | jq .
```

**MCP:**
```json
{"name": "get_portfolio_ticker", "arguments": {"ticker": "VCB"}}
```

**Verify:**
- [ ] Returns `trade_summary` with buy/sell totals
- [ ] `positions` array shows active/closed status
- [ ] `ohlcv` contains recent trading days
- [ ] Unknown ticker returns 404 or empty result

---

### 3. import_snapshot

Import a broker portfolio snapshot from markdown table. Wipes existing data.

| | |
|---|---|
| **Method** | `POST /api/import-snapshot` |
| **Required** | `text` (string — markdown table) |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/import-snapshot \
  -H 'Content-Type: application/json' \
  -d '{"text": "| Ticker | Shares | Avg Cost |\n| VCB | 100 | 250000 |\n| FPT | 200 | 80000 |"}' | jq .
```

**MCP:**
```json
{"name": "import_snapshot", "arguments": {"text": "| Ticker | Shares | Avg Cost |\n| VCB | 100 | 250000 |"}}
```

**Verify:**
- [ ] All tickers from table are imported
- [ ] Previous holdings are cleared
- [ ] `imported_count` matches table rows
- [ ] `get_portfolio` reflects new data after import

---

### 4. get_positions

List active positions for a ticker.

| | |
|---|---|
| **Method** | `GET /api/positions/{ticker}` |
| **Required** | `ticker` (string) |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/positions/VCB | jq .
```

**MCP:**
```json
{"name": "get_positions", "arguments": {"ticker": "VCB"}}
```

**Verify:**
- [ ] Returns array of positions
- [ ] Each position has `id`, `size`, `avg_price`, `remaining`, `sold`
- [ ] `status` is "active" if `remaining > 0`
- [ ] Unknown ticker returns empty array

---

### 5. update_position

Update an existing position's fields (avg_price, remaining, etc.).

| | |
|---|---|
| **Method** | `PUT /api/positions/{position_id}` |
| **Required** | `position_id` (integer) |
| **Optional** | `avg_price` (number), `remaining` (integer) |

**curl:**
```bash
curl -s -X PUT http://localhost:8000/api/positions/1 \
  -H 'Content-Type: application/json' \
  -d '{"avg_price": 252000, "remaining": 50}' | jq .
```

**MCP:**
```json
{"name": "update_position", "arguments": {"position_id": 1, "avg_price": 252000, "remaining": 50}}
```

**Verify:**
- [ ] Only provided fields are updated
- [ ] Non-existent `position_id` returns 404
- [ ] Returned position reflects changes

---

### 6. delete_position

Delete a position by ID.

| | |
|---|---|
| **Method** | `DELETE /api/positions/{position_id}` |
| **Required** | `position_id` (integer) |
| **Optional** | — |

**curl:**
```bash
curl -s -X DELETE http://localhost:8000/api/positions/1 | jq .
```

**MCP:**
```json
{"name": "delete_position", "arguments": {"position_id": 1}}
```

**Verify:**
- [ ] Position removed from database
- [ ] Non-existent ID returns 404
- [ ] No longer appears in `get_positions`

---

### 7. fetch_prices

Fetch latest stock prices from vnstock API and update the cache.

| | |
|---|---|
| **Method** | `POST /api/prices/fetch` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/prices/fetch | jq .
```

**MCP:**
```json
{"name": "fetch_prices", "arguments": {}}
```

**Verify:**
- [ ] Returns count of tickers updated
- [ ] Prices are positive numbers in VND
- [ ] Portfolio `current_price` fields updated
- [ ] Handles vnstock rate limits gracefully

---

### 8. evaluate_rules

Evaluate all trading rules against current holdings.

| | |
|---|---|
| **Method** | `POST /api/rules/evaluate` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/rules/evaluate | jq .
```

**MCP:**
```json
{"name": "evaluate_rules", "arguments": {}}
```

**Verify:**
- [ ] Returns count of rules evaluated
- [ ] `triggered_alerts` array for matching rules
- [ ] Each alert has `ticker`, `severity`, `message`

---

### 9. run_check_cycle

Full trading check cycle: fetch prices → update portfolio → detect swing lows → evaluate rules → create alerts.

| | |
|---|---|
| **Method** | `POST /api/check-cycle` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/check-cycle | jq .
```

**MCP:**
```json
{"name": "run_check_cycle", "arguments": {}}
```

**Verify:**
- [ ] All sub-steps complete (prices, rules, alerts)
- [ ] New alerts created for triggered rules
- [ ] Idempotent — can run repeatedly without data loss
- [ ] Returns completion time

---

### 10. list_alerts

List trading alerts, optionally filtered by ticker.

| | |
|---|---|
| **Method** | `GET /api/alerts` or `GET /api/alerts?ticker={ticker}` |
| **Required** | — |
| **Optional** | `ticker` (string) |

**curl:**
```bash
curl -s http://localhost:8000/api/alerts | jq .
curl -s "http://localhost:8000/api/alerts?ticker=VCB" | jq .
```

**MCP:**
```json
{"name": "list_alerts", "arguments": {"ticker": "VCB"}}
```

**Verify:**
- [ ] Returns array (newest first)
- [ ] Ticker filter works correctly
- [ ] Each alert shows channel send status
- [ ] Empty result returns `[]` (not null)

---

### 11. list_unsent_alerts

List alerts not yet sent to a specific channel.

| | |
|---|---|
| **Method** | `GET /api/alerts/unsent?channel={channel}` |
| **Required** | — |
| **Optional** | `channel` (string, default: "telegram") |

**curl:**
```bash
curl -s "http://localhost:8000/api/alerts/unsent?channel=telegram" | jq .
curl -s "http://localhost:8000/api/alerts/unsent?channel=discord" | jq .
```

**MCP:**
```json
{"name": "list_unsent_alerts", "arguments": {"channel": "discord"}}
```

**Verify:**
- [ ] Filters for alerts where `sent_{channel} = false`
- [ ] Default channel is "telegram"
- [ ] Valid channels: telegram, discord

---

## Group 2: NotebookLM & Artifacts (14 tools)

### 12. list_reports

List broker analysis reports from Vietstock and CafeF.

| | |
|---|---|
| **Method** | `GET /api/reports` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/reports | jq .
curl -s "http://localhost:8000/api/reports?ticker=FRT" | jq .
```

**MCP:**
```json
{"name": "list_reports", "arguments": {}}
```

**Verify:**
- [ ] Each report has `edoc_id`, `title`, `source`, `date`, `ticker`
- [ ] edoc_id prefix: "vs_" (Vietstock) or "cf_" (CafeF)
- [ ] Ordered newest first

---

### 13. fetch_new_reports

Scrape Vietstock and CafeF for new broker analysis reports.

| | |
|---|---|
| **Method** | `POST /api/reports/fetch` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/reports/fetch | jq .
```

**MCP:**
```json
{"name": "fetch_new_reports", "arguments": {}}
```

**Verify:**
- [ ] Returns `new_reports` count
- [ ] Deduplicates by edoc_id
- [ ] Reports scraping errors in `errors` array
- [ ] Takes 30-60s (network dependent)

---

### 14. analyze_report

Analyze a broker report via Google NotebookLM. **NEVER answer from your own knowledge.**

| | |
|---|---|
| **Method** | `POST /api/analyze` |
| **Required** | `edoc_id` (string) |
| **Optional** | `question` (string) |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"edoc_id": "vs_12345"}' | jq .
```

**MCP:**
```json
{"name": "analyze_report", "arguments": {"edoc_id": "vs_12345", "question": "Tóm tắt khuyến nghị"}}
```

**Verify:**
- [ ] Non-existent edoc_id returns 404
- [ ] PDF downloaded from broker source
- [ ] Answer uses NotebookLM (not LLM hallucination)
- [ ] Notebook ID stored for follow-up questions

---

### 15. list_notebooks

List persistent NotebookLM notebooks with IDs and metadata.

| | |
|---|---|
| **Method** | `GET /api/analyze/notebooks` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/analyze/notebooks | jq .
```

**MCP:**
```json
{"name": "list_notebooks", "arguments": {}}
```

**Verify:**
- [ ] Each notebook has `notebook_id`, `notebook_type`, `notebook_key`
- [ ] Types: "ticker" or "category"
- [ ] `source_count` shows number of added reports

---

### 16. notebook_chat

Ask a follow-up question to a NotebookLM notebook. Retains context from all sources.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/chat?notebook_id=&question=&wait=true&timeout=60` |
| **Required** | `notebook_id` (string), `question` (string) |
| **Optional** | — |
| **Timeout** | 60s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/chat?notebook_id=nb123&question=Target%20price%3F&wait=true&timeout=60" | jq .
```

**MCP:**
```json
{"name": "notebook_chat", "arguments": {"notebook_id": "nb123", "question": "Khuyến nghị giao dịch?"}}
```

**Verify:**
- [ ] URL contains `wait=true` and `timeout=60`
- [ ] Answer uses context from ALL notebook sources
- [ ] Non-existent notebook_id returns error
- [ ] Typically completes in 5-15s

---

### 17. notebook_summary

Quick AI summary of a notebook without generating artifacts.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/notebook-summary?notebook_id=&wait=true&timeout=60` |
| **Required** | `notebook_id` (string) |
| **Optional** | — |
| **Timeout** | 60s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/notebook-summary?notebook_id=nb123&wait=true&timeout=60" | jq .
```

**MCP:**
```json
{"name": "notebook_summary", "arguments": {"notebook_id": "nb123"}}
```

**Verify:**
- [ ] Returns text summary (not HTML/PDF)
- [ ] Extracts key points from all sources
- [ ] No artifact files generated

---

### 18. generate_infographic

Generate a visual infographic image from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/infographic?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | `orientation` (portrait/landscape/square), `detail_level` (concise/standard/detailed) |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/infographic?notebook_id=nb123&orientation=landscape&detail_level=detailed&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_infographic", "arguments": {"notebook_id": "nb123", "orientation": "landscape", "detail_level": "standard"}}
```

**Verify:**
- [ ] URL includes optional params when provided
- [ ] Returns `result.file_path` with image
- [ ] Orientation and detail_level affect output
- [ ] Image is downloadable via `/api/artifacts/download?file_path=`

---

### 19. generate_audio

Generate podcast-style audio from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/audio?notebook_id=&wait=true&timeout=180` |
| **Required** | `notebook_id` (string) |
| **Optional** | `audio_format` (deep_dive/brief/critique/debate), `audio_length` (short/default/long) |
| **Timeout** | 180s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/audio?notebook_id=nb123&audio_format=debate&audio_length=long&wait=true&timeout=180" | jq .
```

**MCP:**
```json
{"name": "generate_audio", "arguments": {"notebook_id": "nb123", "audio_format": "critique", "audio_length": "default"}}
```

**Verify:**
- [ ] Returns `result.file_path` with audio file
- [ ] Format affects conversation style (debate = 2 perspectives)
- [ ] Length affects duration (short ~5min, long ~20min)

---

### 20. generate_video

Generate animated video from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/video?notebook_id=&wait=true&timeout=300` |
| **Required** | `notebook_id` (string) |
| **Optional** | `video_format` (explainer/brief), `video_style` (classic/whiteboard/kawaii/anime/watercolor/retro_print/heritage/paper_craft) |
| **Timeout** | 300s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/video?notebook_id=nb123&video_format=explainer&video_style=whiteboard&wait=true&timeout=300" | jq .
```

**MCP:**
```json
{"name": "generate_video", "arguments": {"notebook_id": "nb123", "video_format": "brief", "video_style": "kawaii"}}
```

**Verify:**
- [ ] Longest timeout (300s) — video generation is slowest
- [ ] 8 visual style options
- [ ] Returns `result.file_path` with video file

---

### 21. generate_quiz

Generate an interactive quiz (HTML) from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/quiz?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | `quantity` (fewer/standard), `difficulty` (easy/medium/hard) |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/quiz?notebook_id=nb123&quantity=standard&difficulty=hard&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_quiz", "arguments": {"notebook_id": "nb123", "quantity": "fewer", "difficulty": "easy"}}
```

**Verify:**
- [ ] Returns `result.html_path` with interactive HTML
- [ ] fewer = 5-7 questions, standard = 10-15
- [ ] Difficulty affects question complexity

---

### 22. generate_flashcards

Generate study flashcards (HTML) from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/flashcards?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | `quantity` (fewer/standard), `difficulty` (easy/medium/hard) |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/flashcards?notebook_id=nb123&quantity=standard&difficulty=easy&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_flashcards", "arguments": {"notebook_id": "nb123", "quantity": "standard", "difficulty": "hard"}}
```

**Verify:**
- [ ] Returns `result.html_path` with interactive HTML
- [ ] Each card has front (question) and back (answer)
- [ ] Card count matches quantity

---

### 23. generate_slides

Generate a slide deck (PDF) from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/slides?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | `slide_format` (detailed_deck/presenter_slides), `slide_length` (default/short) |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/slides?notebook_id=nb123&slide_format=presenter_slides&slide_length=short&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_slides", "arguments": {"notebook_id": "nb123", "slide_format": "detailed_deck", "slide_length": "default"}}
```

**Verify:**
- [ ] Returns `result.file_path` with PDF
- [ ] presenter_slides includes speaker notes
- [ ] short = 8-12 slides, default = 15-25

---

### 24. generate_report

Generate a written report from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/report?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | `report_format` (briefing_doc/study_guide/blog_post/custom) |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/report?notebook_id=nb123&report_format=blog_post&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_report", "arguments": {"notebook_id": "nb123", "report_format": "study_guide"}}
```

**Verify:**
- [ ] Returns `result.text` with markdown/plain text
- [ ] Format affects structure and tone
- [ ] Includes citations from sources

---

### 25. web_research

Web research using notebook context. Searches the web and adds found sources to the notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/research?notebook_id=&query=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string), `query` (string) |
| **Optional** | — |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/research?notebook_id=nb123&query=HPG%20outlook%202026&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "web_research", "arguments": {"notebook_id": "nb123", "query": "HPG outlook 2026"}}
```

**Verify:**
- [ ] URL contains both `notebook_id` and `query`
- [ ] Query is URL-encoded in the path
- [ ] Found sources are added to the notebook
- [ ] Returns search results and added source count

---

## Group 3: Agents, Search & System (11 tools)

### 26. list_agents

List all configured AI agents.

| | |
|---|---|
| **Method** | `GET /api/agents` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/agents | jq .
```

**MCP:**
```json
{"name": "list_agents", "arguments": {}}
```

**Verify:**
- [ ] Returns array of agent definitions
- [ ] Each agent has `id`, `name`, `description`

---

### 27. execute_agent

Execute a specific AI agent by its numeric ID.

| | |
|---|---|
| **Method** | `POST /api/agents/{agent_id}/execute` |
| **Required** | `agent_id` (integer) |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/agents/3/execute | jq .
```

**MCP:**
```json
{"name": "execute_agent", "arguments": {"agent_id": 3}}
```

**Verify:**
- [ ] Agent with given ID must exist
- [ ] Returns execution result
- [ ] Non-existent ID returns error

---

### 28. google_search

Search Google for Vietnamese stock news or any query via SerpAPI.

| | |
|---|---|
| **Method** | `GET /api/search?query=&search_type=&num=` |
| **Required** | `query` (string) |
| **Optional** | `search_type` (nws/search/isch, default: "nws"), `num` (1-100, default: 10) |

**curl:**
```bash
curl -s "http://localhost:8000/api/search?query=HPG+FRT&search_type=nws&num=5" | jq .
```

**MCP:**
```json
{"name": "google_search", "arguments": {"query": "HPG FRT NLG", "search_type": "nws", "num": 5}}
```

**Verify:**
- [ ] Returns structured results (title, link, snippet, date)
- [ ] Localized to Vietnam (google.com.vn)
- [ ] `nws` returns news results, `search` returns web results
- [ ] Query with special chars is URL-encoded

---

### 29. get_report_detail

Get full details for a single report including download URL.

| | |
|---|---|
| **Method** | `GET /api/reports/{edoc_id}` |
| **Required** | `edoc_id` (string) |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/reports/vs_12345 | jq .
```

**MCP:**
```json
{"name": "get_report_detail", "arguments": {"edoc_id": "vs_12345"}}
```

**Verify:**
- [ ] Returns full report metadata
- [ ] Includes `download_url` and `detail_url`
- [ ] Non-existent edoc_id returns 404

---

### 30. mark_alert_sent

Mark an alert as sent via a specific channel.

| | |
|---|---|
| **Method** | `POST /api/alerts/{alert_id}/mark-sent` |
| **Required** | `alert_id` (integer), `channel` (string) |
| **Optional** | — |

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/alerts/42/mark-sent \
  -H 'Content-Type: application/json' \
  -d '{"channel": "discord"}' | jq .
```

**MCP:**
```json
{"name": "mark_alert_sent", "arguments": {"alert_id": 42, "channel": "discord"}}
```

**Verify:**
- [ ] Alert's `sent_{channel}` flag set to true
- [ ] Non-existent alert_id returns 404
- [ ] Alert no longer appears in `list_unsent_alerts` for that channel
- [ ] Default channel is "telegram" if not specified

---

### 31. generate_mind_map

Generate a structured concept mind map from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/mind-map?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | — |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/mind-map?notebook_id=nb123&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_mind_map", "arguments": {"notebook_id": "nb123"}}
```

**Verify:**
- [ ] Returns `result.data` with structured JSON
- [ ] Hierarchical concept structure
- [ ] URL contains `wait=true` and `timeout=120`

---

### 32. generate_study_guide

Generate a comprehensive study guide from a notebook.

| | |
|---|---|
| **Method** | `GET /api/jobs/start/study-guide?notebook_id=&wait=true&timeout=120` |
| **Required** | `notebook_id` (string) |
| **Optional** | — |
| **Timeout** | 120s |

**curl:**
```bash
curl -s "http://localhost:8000/api/jobs/start/study-guide?notebook_id=nb123&wait=true&timeout=120" | jq .
```

**MCP:**
```json
{"name": "generate_study_guide", "arguments": {"notebook_id": "nb123"}}
```

**Verify:**
- [ ] Returns `result.text` with comprehensive study material
- [ ] Structured with sections and key concepts

---

### 33. get_ticker_levels

Get all price levels for a ticker: swing lows, swing highs, round numbers, manual levels.

| | |
|---|---|
| **Method** | `GET /api/levels/{ticker}` |
| **Required** | `ticker` (string) |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/levels/HPG | jq .
```

**MCP:**
```json
{"name": "get_ticker_levels", "arguments": {"ticker": "HPG"}}
```

**Verify:**
- [ ] Returns price level categories (swing_lows, swing_highs, etc.)
- [ ] Levels are sorted by price
- [ ] Unknown ticker returns empty or 404

---

### 34. list_jobs

List recent background jobs, optionally filtered by status.

| | |
|---|---|
| **Method** | `GET /api/jobs` or `GET /api/jobs?status={status}` |
| **Required** | — |
| **Optional** | `status` (pending/running/completed/failed) |

**curl:**
```bash
curl -s http://localhost:8000/api/jobs | jq .
curl -s "http://localhost:8000/api/jobs?status=completed" | jq .
```

**MCP:**
```json
{"name": "list_jobs", "arguments": {"status": "completed"}}
```

**Verify:**
- [ ] Returns array of recent jobs
- [ ] Each job has `job_id`, `job_type`, `status`, `started_at`
- [ ] Status filter works correctly
- [ ] Without filter, returns all statuses

---

### 35. get_job_status

Get status and result of a specific background job.

| | |
|---|---|
| **Method** | `GET /api/jobs/{job_id}` |
| **Required** | `job_id` (string) |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/jobs/job-abc123 | jq .
```

**MCP:**
```json
{"name": "get_job_status", "arguments": {"job_id": "job-abc123"}}
```

**Verify:**
- [ ] Returns full job details including `result` if completed
- [ ] Status transitions: pending → running → completed/failed
- [ ] Non-existent job_id returns 404
- [ ] Completed jobs include `result` and `completed_at`

---

### 36. get_config

Get all application configuration values.

| | |
|---|---|
| **Method** | `GET /api/config` |
| **Required** | — |
| **Optional** | — |

**curl:**
```bash
curl -s http://localhost:8000/api/config | jq .
```

**MCP:**
```json
{"name": "get_config", "arguments": {}}
```

**Verify:**
- [ ] Returns config key-value pairs
- [ ] Sensitive values (API keys) are masked
- [ ] Includes FASTAPI_URL, database path, etc.

---

## Quick Smoke Test Script

Run all non-destructive tools in one go:

```bash
BASE=http://localhost:8000

echo "=== Portfolio ==="
curl -s $BASE/api/portfolio | jq '.holdings | length'

echo "=== Reports ==="
curl -s $BASE/api/reports | jq '.reports | length // .count // length'

echo "=== Alerts ==="
curl -s $BASE/api/alerts | jq 'length'

echo "=== Notebooks ==="
curl -s $BASE/api/analyze/notebooks | jq '.notebooks | length // length'

echo "=== Jobs ==="
curl -s $BASE/api/jobs | jq 'length'

echo "=== Config ==="
curl -s $BASE/api/config | jq 'keys'

echo "=== Agents ==="
curl -s $BASE/api/agents | jq 'length'

echo "=== Search ==="
curl -s "$BASE/api/search?query=VN-Index&search_type=nws&num=3" | jq '.results | length // length'

echo "=== Done ==="
```

## Timeout Reference

| Timeout | Tools |
|---------|-------|
| 60s | `notebook_chat`, `notebook_summary` |
| 120s | `generate_infographic`, `generate_quiz`, `generate_flashcards`, `generate_slides`, `generate_report`, `web_research`, `generate_mind_map`, `generate_study_guide` |
| 180s | `generate_audio` |
| 300s | `generate_video` |
| — | All non-job tools (instant HTTP, no blocking) |
