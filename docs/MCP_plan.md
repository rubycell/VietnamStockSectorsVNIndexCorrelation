# MCP Server Upgrade Plan

> Upgrade `openclaw/mcp/portfolio_server.py` from 11 tools to 35 tools, covering the full FastAPI backend surface.

## Current State

The existing MCP server (`openclaw/mcp/portfolio_server.py`) has 11 tools:
- `list_reports`, `fetch_new_reports`, `analyze_report`
- `get_portfolio`, `get_portfolio_ticker`
- `run_check_cycle`, `list_alerts`, `list_unsent_alerts`
- `fetch_prices`, `evaluate_rules`
- `list_agents`, `execute_agent`

## Target: 35 Tools in 3 Groups

### Group 1: Portfolio & Trading (12 tools)

| Tool | Method | Endpoint | Description |
|------|--------|----------|-------------|
| `get_portfolio` | GET | `/api/portfolio` | Full portfolio summary with all holdings |
| `get_portfolio_ticker` | GET | `/api/portfolio/{ticker}` | Detailed holdings for one ticker |
| `import_snapshot` | POST | `/api/import-snapshot` | Import broker portfolio snapshot (markdown/CSV) |
| `upload_trades` | POST | `/api/upload` | Upload TCBS trade history XLSX |
| `get_positions` | GET | `/api/positions` | List all active positions |
| `update_position` | PUT | `/api/positions/{ticker}` | Update position avg_cost/count |
| `delete_position` | DELETE | `/api/positions/{ticker}` | Remove a position |
| `fetch_prices` | POST | `/api/prices/fetch` | Fetch latest stock prices |
| `evaluate_rules` | POST | `/api/rules/evaluate` | Evaluate trading rules |
| `run_check_cycle` | POST | `/api/check-cycle` | Full check cycle |
| `list_alerts` | GET | `/api/alerts` | List alerts (optional ticker filter) |
| `list_unsent_alerts` | GET | `/api/alerts/unsent` | Unsent alerts for a channel |

### Group 2: NotebookLM & Artifacts (14 tools)

| Tool | Method | Endpoint | Description |
|------|--------|----------|-------------|
| `list_reports` | GET | `/api/reports` | List broker reports (filter by ticker) |
| `fetch_new_reports` | POST | `/api/jobs/start/fetch-reports` | Scrape new reports from Vietstock/CafeF |
| `analyze_report` | POST | `/api/jobs/start/analyze` | Analyze report via NotebookLM |
| `list_notebooks` | GET | `/api/analyze/notebooks` | List persistent NotebookLM notebooks |
| `notebook_chat` | POST | `/api/jobs/start/chat` | Follow-up question to a notebook |
| `notebook_summary` | POST | `/api/jobs/start/notebook-summary` | Quick AI summary of a notebook |
| `generate_infographic` | POST | `/api/jobs/start/infographic` | Generate visual infographic |
| `generate_audio` | POST | `/api/jobs/start/audio` | Generate podcast-style audio |
| `generate_video` | POST | `/api/jobs/start/video` | Generate animated video |
| `generate_quiz` | POST | `/api/jobs/start/quiz` | Generate interactive quiz (HTML) |
| `generate_flashcards` | POST | `/api/jobs/start/flashcards` | Generate study flashcards (HTML) |
| `generate_slides` | POST | `/api/jobs/start/slides` | Generate slide deck (PDF) |
| `generate_report` | POST | `/api/jobs/start/report` | Generate written report |
| `web_research` | POST | `/api/jobs/start/research` | Web research using notebook context |

### Group 3: Agents & System (9 tools)

| Tool | Method | Endpoint | Description |
|------|--------|----------|-------------|
| `list_agents` | GET | `/api/agents` | List AI agents |
| `execute_agent` | POST | `/api/agents/{id}/execute` | Execute an agent |
| `get_report_detail` | GET | `/api/reports/{edoc_id}` | Get single report detail + download URL |
| `download_artifact` | GET | `/api/artifacts/download` | Download generated artifact file |
| `mark_alert_sent` | POST | `/api/alerts/{id}/mark-sent` | Mark alert as sent to channel |
| `generate_mind_map` | POST | `/api/jobs/start/mind-map` | Generate mind map from notebook |
| `generate_study_guide` | POST | `/api/jobs/start/study-guide` | Generate study guide from notebook |
| `generate_data_table` | POST | `/api/jobs/start/data-table` | Extract structured data table |
| `get_daily_report` | POST | `/api/jobs/start/daily-report` | Generate daily portfolio report |

## Architecture Decisions

### 1. Single file, stdlib only
Keep everything in `portfolio_server.py`. No external dependencies. Python stdlib `urllib` + `json` only.

### 2. Blocking with `?wait=true`
All job endpoints use `?wait=true&timeout=N` to block until completion. This is simpler for MCP (synchronous tool calls) and eliminates polling.

### 3. Timeout tiers
- Quick operations (list, fetch prices): 30s
- Analysis jobs: 120s
- Audio/video generation: 300s

### 4. Tool naming convention
- `get_*` for read operations
- `list_*` for collection queries
- `generate_*` for NotebookLM artifact creation
- Action verbs for mutations: `import_snapshot`, `upload_trades`, `evaluate_rules`

## OpenClaw Registration

In `openclaw/openclaw.json`, the MCP server is registered under the `"tools"` section. Current config:

```json
{
  "tools": {
    "exec": {
      "security": "full",
      "ask": "off"
    }
  }
}
```

Add MCP server registration (exact config TBD based on OpenClaw MCP integration docs):

```json
{
  "tools": {
    "exec": {
      "security": "full",
      "ask": "off"
    },
    "mcp": {
      "servers": {
        "portfolio-api": {
          "command": "python3",
          "args": ["/app/openclaw/mcp/portfolio_server.py"],
          "env": {
            "FASTAPI_URL": "http://fastapi:8000"
          }
        }
      }
    }
  }
}
```

## Skill Simplification

Once MCP tools are registered, OpenClaw skills become thinner. Instead of embedding `curl` commands, skills reference MCP tools:

**Before (curl-based skill):**
```markdown
## Analyze a report
curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=<ID>&wait=true"
```

**After (MCP-aware skill):**
```markdown
## Analyze a report
Use the `analyze_report` tool with `edoc_id` parameter.
```

Skills still own:
- Message formatting (severity-based alert templates)
- Workflow orchestration (multi-step flows like fetch → analyze → send)
- User interaction patterns (acknowledgments, file delivery)

## Implementation Order

### Phase 1: New tool definitions (add to TOOLS list)
Add all 24 new tool definitions with proper `inputSchema` including:
- Required vs optional parameters
- Default values
- Parameter descriptions

### Phase 2: Tool dispatch (add to `_call_tool`)
Implement the `match` cases for each new tool, mapping to FastAPI endpoints.

### Phase 3: Register in OpenClaw
Update `openclaw.json` to register the MCP server.

### Phase 4: Simplify skills
Update skill files to reference MCP tools instead of raw curl commands.

### Phase 5: Test
- Verify each tool returns expected results
- Test timeout handling for long-running jobs
- Test error responses for invalid inputs
