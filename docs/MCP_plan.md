# MCP Server — 36 Tools (Complete)

> `openclaw/mcp/portfolio_server.py` — stdlib-only Python MCP server over JSON-RPC 2.0 stdio.

## Status: COMPLETE

All 36 tools implemented and tested (69/69 tests passing in `tests/test_mcp_server.py`).

## Tool Inventory (36)

### Group 1: Portfolio & Trading (11)

| Tool | Method | Endpoint |
|------|--------|----------|
| `get_portfolio` | GET | `/api/portfolio` |
| `get_portfolio_ticker` | GET | `/api/portfolio/{ticker}` |
| `import_snapshot` | POST | `/api/import-snapshot` |
| `get_positions` | GET | `/api/positions/{ticker}` |
| `update_position` | PUT | `/api/positions/{position_id}` |
| `delete_position` | DELETE | `/api/positions/{position_id}` |
| `fetch_prices` | POST | `/api/prices/fetch` |
| `evaluate_rules` | POST | `/api/rules/evaluate` |
| `run_check_cycle` | POST | `/api/check-cycle` |
| `list_alerts` | GET | `/api/alerts` |
| `list_unsent_alerts` | GET | `/api/alerts/unsent?channel=` |

### Group 2: NotebookLM & Artifacts (14)

| Tool | Method | Endpoint | Timeout |
|------|--------|----------|---------|
| `list_reports` | GET | `/api/reports` | — |
| `fetch_new_reports` | POST | `/api/reports/fetch` | — |
| `analyze_report` | POST | `/api/analyze` | — |
| `list_notebooks` | GET | `/api/analyze/notebooks` | — |
| `notebook_chat` | GET | `/api/jobs/start/chat` | 60s |
| `notebook_summary` | GET | `/api/jobs/start/notebook-summary` | 60s |
| `generate_infographic` | GET | `/api/jobs/start/infographic` | 120s |
| `generate_audio` | GET | `/api/jobs/start/audio` | 180s |
| `generate_video` | GET | `/api/jobs/start/video` | 300s |
| `generate_quiz` | GET | `/api/jobs/start/quiz` | 120s |
| `generate_flashcards` | GET | `/api/jobs/start/flashcards` | 120s |
| `generate_slides` | GET | `/api/jobs/start/slides` | 120s |
| `generate_report` | GET | `/api/jobs/start/report` | 120s |
| `web_research` | GET | `/api/jobs/start/research` | 120s |

### Group 3: Agents, Search & System (11)

| Tool | Method | Endpoint | Timeout |
|------|--------|----------|---------|
| `list_agents` | GET | `/api/agents` | — |
| `execute_agent` | POST | `/api/agents/{id}/execute` | — |
| `google_search` | GET | `/api/search` | — |
| `get_report_detail` | GET | `/api/reports/{edoc_id}` | — |
| `mark_alert_sent` | POST | `/api/alerts/{id}/mark-sent` | — |
| `generate_mind_map` | GET | `/api/jobs/start/mind-map` | 120s |
| `generate_study_guide` | GET | `/api/jobs/start/study-guide` | 120s |
| `get_ticker_levels` | GET | `/api/levels/{ticker}` | — |
| `list_jobs` | GET | `/api/jobs` | — |
| `get_job_status` | GET | `/api/jobs/{job_id}` | — |
| `get_config` | GET | `/api/config` | — |

## Architecture

- **Single file:** `openclaw/mcp/portfolio_server.py` (~230 lines)
- **No dependencies:** Python stdlib only (`json`, `urllib`)
- **`_job_path` helper:** Builds URLs for all 12 job-based tools with `?wait=true&timeout=N` and optional params
- **Transport:** stdio with Content-Length framing (JSON-RPC 2.0)

### Timeout tiers
- Chat/summary: 60s
- Analysis/artifacts: 120s
- Audio: 180s
- Video: 300s

## OpenClaw Integration

MCP server registered through the **skill system** (same pattern as playwright-mcp from clawhub).

- Skill: `openclaw/skills/portfolio-mcp/SKILL.md`
- Dual-method: All skills list both MCP tools and curl fallbacks
- Startup: `FASTAPI_URL=http://fastapi:8000 python3 ~/.openclaw/mcp/portfolio_server.py`
