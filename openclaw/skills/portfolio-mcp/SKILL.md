---
name: portfolio-mcp
description: "Portfolio MCP server providing 36 backend tools via JSON-RPC 2.0 over stdio. Covers portfolio, trading, NotebookLM artifacts, reports, jobs, and search. Falls back to curl if MCP is unavailable."
metadata: {"openclaw":{"emoji":"📊","os":["linux","darwin","win32"],"requires":{"bins":["portfolio-mcp"]}}}
---

# Portfolio MCP Server

MCP server wrapping the FastAPI portfolio/trading backend. Provides **36 tools** via JSON-RPC 2.0 over stdio.

## Start Server

```bash
FASTAPI_URL=http://fastapi:8000 python3 ~/.openclaw/mcp/portfolio_server.py
```

## Available MCP Tools (36)

### Portfolio & Trading (11)

| Tool | Description | Curl fallback |
|------|-------------|---------------|
| `get_portfolio` | Full portfolio summary | `curl -s http://fastapi:8000/api/portfolio` |
| `get_portfolio_ticker` | Single ticker detail | `curl -s http://fastapi:8000/api/portfolio/{ticker}` |
| `import_snapshot` | Import broker snapshot | `curl -s -X POST http://fastapi:8000/api/import-snapshot -d '{"text":"..."}' -H 'Content-Type: application/json'` |
| `get_positions` | List positions for ticker | `curl -s http://fastapi:8000/api/positions/{ticker}` |
| `update_position` | Update position fields | `curl -s -X PUT http://fastapi:8000/api/positions/{id} -d '{"avg_price":50000}' -H 'Content-Type: application/json'` |
| `delete_position` | Delete a position | `curl -s -X DELETE http://fastapi:8000/api/positions/{id}` |
| `fetch_prices` | Fetch latest prices | `curl -s -X POST http://fastapi:8000/api/prices/fetch` |
| `evaluate_rules` | Evaluate trading rules | `curl -s -X POST http://fastapi:8000/api/rules/evaluate` |
| `run_check_cycle` | Full trading check cycle | `curl -s -X POST http://fastapi:8000/api/check-cycle` |
| `list_alerts` | List trading alerts | `curl -s http://fastapi:8000/api/alerts` |
| `list_unsent_alerts` | Unsent alerts by channel | `curl -s http://fastapi:8000/api/alerts/unsent?channel=telegram` |

### NotebookLM & Artifacts (14)

| Tool | Description | Curl fallback |
|------|-------------|---------------|
| `list_reports` | List broker reports | `curl -s http://fastapi:8000/api/reports` |
| `fetch_new_reports` | Scrape new reports | `curl -s -X POST http://fastapi:8000/api/reports/fetch` |
| `analyze_report` | Analyze via NotebookLM | `curl -s -X POST http://fastapi:8000/api/analyze -d '{"edoc_id":"..."}' -H 'Content-Type: application/json'` |
| `list_notebooks` | List NotebookLM notebooks | `curl -s http://fastapi:8000/api/analyze/notebooks` |
| `notebook_chat` | Follow-up question | `curl -s "http://fastapi:8000/api/jobs/start/chat?notebook_id=ID&question=Q&wait=true&timeout=60"` |
| `notebook_summary` | Quick notebook summary | `curl -s "http://fastapi:8000/api/jobs/start/notebook-summary?notebook_id=ID&wait=true&timeout=60"` |
| `generate_infographic` | Visual infographic | `curl -s "http://fastapi:8000/api/jobs/start/infographic?notebook_id=ID&wait=true&timeout=120"` |
| `generate_audio` | Podcast-style audio | `curl -s "http://fastapi:8000/api/jobs/start/audio?notebook_id=ID&wait=true&timeout=180"` |
| `generate_video` | Animated video | `curl -s "http://fastapi:8000/api/jobs/start/video?notebook_id=ID&wait=true&timeout=300"` |
| `generate_quiz` | Interactive quiz (HTML) | `curl -s "http://fastapi:8000/api/jobs/start/quiz?notebook_id=ID&wait=true&timeout=120"` |
| `generate_flashcards` | Study flashcards (HTML) | `curl -s "http://fastapi:8000/api/jobs/start/flashcards?notebook_id=ID&wait=true&timeout=120"` |
| `generate_slides` | Slide deck (PDF) | `curl -s "http://fastapi:8000/api/jobs/start/slides?notebook_id=ID&wait=true&timeout=120"` |
| `generate_report` | Written report | `curl -s "http://fastapi:8000/api/jobs/start/report?notebook_id=ID&wait=true&timeout=120"` |
| `web_research` | Web research for notebook | `curl -s "http://fastapi:8000/api/jobs/start/research?notebook_id=ID&query=Q&wait=true&timeout=120"` |

### Agents, Search & System (11)

| Tool | Description | Curl fallback |
|------|-------------|---------------|
| `list_agents` | List AI agents | `curl -s http://fastapi:8000/api/agents` |
| `execute_agent` | Run an agent by ID | `curl -s -X POST http://fastapi:8000/api/agents/{id}/execute` |
| `google_search` | Search Google News/Web | `curl -s "http://fastapi:8000/api/search?query=HPG&search_type=nws"` |
| `get_report_detail` | Get report PDF/detail | `curl -s http://fastapi:8000/api/reports/{edoc_id}` |
| `mark_alert_sent` | Mark alert as sent | `curl -s -X POST http://fastapi:8000/api/alerts/{id}/mark-sent -d '{"channel":"telegram"}' -H 'Content-Type: application/json'` |
| `generate_mind_map` | Concept mind map | `curl -s "http://fastapi:8000/api/jobs/start/mind-map?notebook_id=ID&wait=true&timeout=120"` |
| `generate_study_guide` | Study guide | `curl -s "http://fastapi:8000/api/jobs/start/study-guide?notebook_id=ID&wait=true&timeout=120"` |
| `get_ticker_levels` | Support/resistance levels | `curl -s http://fastapi:8000/api/levels/{ticker}` |
| `list_jobs` | List async jobs | `curl -s http://fastapi:8000/api/jobs` |
| `get_job_status` | Get job status | `curl -s http://fastapi:8000/api/jobs/{job_id}` |
| `get_config` | Get server config | `curl -s http://fastapi:8000/api/config` |

## Usage

**IMPORTANT: Always prefer MCP tools over curl or webfetch.** Only fall back to curl if MCP tools are unavailable.

**Preferred — Via MCP tools:**
```
google_search: { query: "HPG FRT NLG", search_type: "nws", num: 5 }
get_portfolio: {}
analyze_report: { edoc_id: "12345", question: "Tóm tắt báo cáo" }
generate_infographic: { notebook_id: "abc", orientation: "landscape" }
```

**Fallback — Via curl (only if MCP is unavailable):**
```bash
curl -s http://fastapi:8000/api/portfolio
curl -s "http://fastapi:8000/api/search?query=HPG+FRT&search_type=nws&num=5"
```

## NotebookLM Job Options

| Artifact | Options |
|----------|---------|
| Infographic | `orientation`: portrait/landscape/square, `detail_level`: concise/standard/detailed |
| Audio | `audio_format`: deep_dive/brief/critique/debate, `audio_length`: short/default/long |
| Video | `video_format`: explainer/brief, `video_style`: classic/whiteboard/kawaii/anime/watercolor/retro_print/heritage/paper_craft |
| Quiz | `quantity`: fewer/standard, `difficulty`: easy/medium/hard |
| Flashcards | `quantity`: fewer/standard, `difficulty`: easy/medium/hard |
| Slides | `slide_format`: detailed_deck/presenter_slides, `slide_length`: default/short |
| Report | `report_format`: briefing_doc/study_guide/blog_post/custom |

## Google Search Parameters

| Parameter | Default | Options |
|-----------|---------|---------|
| `query` | (required) | Any search query — ticker symbols, keywords, etc. |
| `search_type` | `nws` | `nws` (news), `search` (web), `isch` (images) |
| `num` | `10` | 1-100 results |

Search is localized to Vietnam (google.com.vn, Ho Chi Minh City location).
