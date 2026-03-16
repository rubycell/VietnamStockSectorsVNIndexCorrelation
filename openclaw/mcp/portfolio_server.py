#!/usr/bin/env python3
"""MCP server wrapping the FastAPI portfolio/reports API.

Implements the Model Context Protocol (JSON-RPC 2.0 over stdio)
using only Python stdlib — no external dependencies required.

Transport: stdio with Content-Length framing.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

FASTAPI_URL = os.environ.get("FASTAPI_URL", "http://fastapi:8000")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    # ── Group 1: Portfolio & Trading ──────────────────────────────────────
    {"name": "get_portfolio", "description": "Get full portfolio summary with all holdings, P&L, and position status.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_portfolio_ticker", "description": "Get detailed holdings for a single ticker including position breakdown.", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol (e.g. VCB, FPT, FRT)."}}, "required": ["ticker"]}},
    {"name": "import_snapshot", "description": "Import a broker portfolio snapshot from a markdown table. Wipes existing data and creates synthetic trades to match.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "description": "Markdown table with portfolio data (ticker, shares, avg cost, etc.)."}}, "required": ["text"]}},
    {"name": "get_positions", "description": "List active positions for a ticker.", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol."}}, "required": ["ticker"]}},
    {"name": "update_position", "description": "Update an existing position's fields (avg_price, remaining, etc.).", "inputSchema": {"type": "object", "properties": {"position_id": {"type": "integer", "description": "Position ID to update."}, "avg_price": {"type": "number", "description": "New average price."}, "remaining": {"type": "integer", "description": "New remaining shares."}}, "required": ["position_id"]}},
    {"name": "delete_position", "description": "Delete a position by ID.", "inputSchema": {"type": "object", "properties": {"position_id": {"type": "integer", "description": "Position ID to delete."}}, "required": ["position_id"]}},
    {"name": "fetch_prices", "description": "Fetch latest stock prices from vnstock and update the cache.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "evaluate_rules", "description": "Evaluate all trading rules against current holdings.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "run_check_cycle", "description": "Run the full trading check cycle: fetch prices, update portfolio, detect swing lows, evaluate rules, and check for alerts.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_alerts", "description": "List trading alerts, optionally filtered by ticker.", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Optional ticker to filter alerts."}}}},
    {"name": "list_unsent_alerts", "description": "List alerts that have not been sent to a specific channel.", "inputSchema": {"type": "object", "properties": {"channel": {"type": "string", "description": "Channel name (e.g. telegram, discord).", "default": "telegram"}}}},
    # ── Group 2: NotebookLM & Artifacts ───────────────────────────────────
    {"name": "list_reports", "description": "List broker analysis reports from Vietstock and CafeF. Returns report id, ticker, title, source, date.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "fetch_new_reports", "description": "Scrape Vietstock and CafeF for new broker analysis reports. Returns count of new reports found.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "analyze_report", "description": "Analyze a broker report using Google NotebookLM. ALWAYS use this for report content — never answer from your own knowledge.", "inputSchema": {"type": "object", "properties": {"edoc_id": {"type": "string", "description": "The report's edoc_id from list_reports."}, "question": {"type": "string", "description": "Question to ask. Defaults to Vietnamese summary with recommendations."}}, "required": ["edoc_id"]}},
    {"name": "list_notebooks", "description": "List persistent NotebookLM notebooks with their IDs and metadata.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "notebook_chat", "description": "Ask a follow-up question to a NotebookLM notebook. Retains context from all sources.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID from list_notebooks."}, "question": {"type": "string", "description": "Question to ask."}}, "required": ["notebook_id", "question"]}},
    {"name": "notebook_summary", "description": "Get a quick AI summary of a NotebookLM notebook without generating artifacts.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}}, "required": ["notebook_id"]}},
    {"name": "generate_infographic", "description": "Generate a visual infographic from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "orientation": {"type": "string", "description": "portrait, landscape, or square."}, "detail_level": {"type": "string", "description": "concise, standard, or detailed."}}, "required": ["notebook_id"]}},
    {"name": "generate_audio", "description": "Generate podcast-style audio from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "audio_format": {"type": "string", "description": "deep_dive, brief, critique, or debate."}, "audio_length": {"type": "string", "description": "short, default, or long."}}, "required": ["notebook_id"]}},
    {"name": "generate_video", "description": "Generate animated video from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "video_format": {"type": "string", "description": "explainer or brief."}, "video_style": {"type": "string", "description": "classic, whiteboard, kawaii, anime, watercolor, retro_print, heritage, paper_craft."}}, "required": ["notebook_id"]}},
    {"name": "generate_quiz", "description": "Generate an interactive quiz (HTML) from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "quantity": {"type": "string", "description": "fewer or standard."}, "difficulty": {"type": "string", "description": "easy, medium, or hard."}}, "required": ["notebook_id"]}},
    {"name": "generate_flashcards", "description": "Generate study flashcards (HTML) from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "quantity": {"type": "string", "description": "fewer or standard."}, "difficulty": {"type": "string", "description": "easy, medium, or hard."}}, "required": ["notebook_id"]}},
    {"name": "generate_slides", "description": "Generate a slide deck (PDF) from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "slide_format": {"type": "string", "description": "detailed_deck or presenter_slides."}, "slide_length": {"type": "string", "description": "default or short."}}, "required": ["notebook_id"]}},
    {"name": "generate_report", "description": "Generate a written report from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "report_format": {"type": "string", "description": "briefing_doc, study_guide, blog_post, or custom."}}, "required": ["notebook_id"]}},
    {"name": "web_research", "description": "Web research using NotebookLM notebook context. Searches and adds found sources.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}, "query": {"type": "string", "description": "Research query."}}, "required": ["notebook_id", "query"]}},
    # ── Group 3: Agents, Search & System ──────────────────────────────────
    {"name": "list_agents", "description": "List all configured AI agents.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "execute_agent", "description": "Execute a specific AI agent by its ID.", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "integer", "description": "The agent's numeric ID."}}, "required": ["agent_id"]}},
    {"name": "google_search", "description": "Search Google for Vietnamese stock news or any query. Defaults to Google News localized to Vietnam.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query."}, "search_type": {"type": "string", "description": "nws (news), search (web), isch (images).", "default": "nws"}, "num": {"type": "integer", "description": "Number of results (1-100).", "default": 10}}, "required": ["query"]}},
    {"name": "get_report_detail", "description": "Get full details for a single report including download URL.", "inputSchema": {"type": "object", "properties": {"edoc_id": {"type": "string", "description": "Report edoc_id."}}, "required": ["edoc_id"]}},
    {"name": "mark_alert_sent", "description": "Mark an alert as sent via a specific channel.", "inputSchema": {"type": "object", "properties": {"alert_id": {"type": "integer", "description": "Alert ID."}, "channel": {"type": "string", "description": "Channel: telegram, discord, whatsapp."}}, "required": ["alert_id", "channel"]}},
    {"name": "generate_mind_map", "description": "Generate a structured mind map from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}}, "required": ["notebook_id"]}},
    {"name": "generate_study_guide", "description": "Generate a comprehensive study guide from a NotebookLM notebook.", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string", "description": "Notebook ID."}}, "required": ["notebook_id"]}},
    {"name": "get_ticker_levels", "description": "Get all price levels for a ticker: swing lows, swing highs, round numbers, manual levels.", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol."}}, "required": ["ticker"]}},
    {"name": "list_jobs", "description": "List recent background jobs, optionally filtered by status.", "inputSchema": {"type": "object", "properties": {"status": {"type": "string", "description": "Filter by status: pending, running, completed, failed."}}}},
    {"name": "get_job_status", "description": "Get status and result of a specific background job.", "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string", "description": "Job ID."}}, "required": ["job_id"]}},
    {"name": "get_config", "description": "Get all application configuration values.", "inputSchema": {"type": "object", "properties": {}}},
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_request(method: str, path: str, body: dict | None = None) -> dict | str:
    """Make an HTTP request to the FastAPI backend."""
    url = f"{FASTAPI_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
    except urllib.error.HTTPError as error:
        error_body = error.read().decode()
        try:
            detail = json.loads(error_body)
            return {"error": detail.get("detail", error_body), "status": error.code}
        except json.JSONDecodeError:
            return {"error": error_body, "status": error.code}
    except Exception as error:
        return {"error": str(error)}


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _job_path(job_type: str, arguments: dict, *, timeout: int,
              extra_keys: list[str] | None = None) -> str:
    """Build a /api/jobs/start/<type>?... path with wait=true and timeout."""
    params = {"notebook_id": arguments["notebook_id"], "wait": "true", "timeout": str(timeout)}
    for key in extra_keys or []:
        if key in arguments:
            params[key] = arguments[key]
    query_string = urllib.parse.urlencode(params)
    return f"/api/jobs/start/{job_type}?{query_string}"


def _call_tool(name: str, arguments: dict) -> Any:
    """Dispatch a tool call to the appropriate FastAPI endpoint."""
    match name:
        case "list_reports":
            return _http_request("GET", "/api/reports")

        case "fetch_new_reports":
            return _http_request("POST", "/api/reports/fetch")

        case "analyze_report":
            payload = {"edoc_id": arguments["edoc_id"]}
            if "question" in arguments:
                payload["question"] = arguments["question"]
            return _http_request("POST", "/api/analyze", payload)

        case "get_portfolio":
            return _http_request("GET", "/api/portfolio")

        case "get_portfolio_ticker":
            return _http_request("GET", f"/api/portfolio/{arguments['ticker']}")

        case "run_check_cycle":
            return _http_request("POST", "/api/check-cycle")

        case "list_alerts":
            ticker = arguments.get("ticker")
            path = f"/api/alerts?ticker={ticker}" if ticker else "/api/alerts"
            return _http_request("GET", path)

        case "list_unsent_alerts":
            channel = arguments.get("channel", "telegram")
            return _http_request("GET", f"/api/alerts/unsent?channel={channel}")

        case "fetch_prices":
            return _http_request("POST", "/api/prices/fetch")

        case "evaluate_rules":
            return _http_request("POST", "/api/rules/evaluate")

        case "list_agents":
            return _http_request("GET", "/api/agents")

        case "execute_agent":
            return _http_request("POST", f"/api/agents/{arguments['agent_id']}/execute")

        case "google_search":
            query = arguments["query"]
            search_type = arguments.get("search_type", "nws")
            num = arguments.get("num", 10)
            path = f"/api/search?query={urllib.parse.quote(query)}&search_type={search_type}&num={num}"
            return _http_request("GET", path)

        # ── New Portfolio & Trading tools ─────────────────────────────────

        case "import_snapshot":
            return _http_request("POST", "/api/import-snapshot", {"text": arguments["text"]})

        case "get_positions":
            return _http_request("GET", f"/api/positions/{arguments['ticker']}")

        case "update_position":
            position_id = arguments.pop("position_id")
            return _http_request("PUT", f"/api/positions/{position_id}", arguments)

        case "delete_position":
            return _http_request("DELETE", f"/api/positions/{arguments['position_id']}")

        # ── New NotebookLM & Artifacts tools ──────────────────────────────

        case "list_notebooks":
            return _http_request("GET", "/api/analyze/notebooks")

        case "notebook_chat":
            return _http_request("GET", _job_path("chat", arguments, timeout=60,
                                                   extra_keys=["question"]))

        case "notebook_summary":
            return _http_request("GET", _job_path("notebook-summary", arguments, timeout=60))

        case "generate_infographic":
            return _http_request("GET", _job_path("infographic", arguments, timeout=120,
                                                   extra_keys=["orientation", "detail_level"]))

        case "generate_audio":
            return _http_request("GET", _job_path("audio", arguments, timeout=180,
                                                   extra_keys=["audio_format", "audio_length"]))

        case "generate_video":
            return _http_request("GET", _job_path("video", arguments, timeout=300,
                                                   extra_keys=["video_format", "video_style"]))

        case "generate_quiz":
            return _http_request("GET", _job_path("quiz", arguments, timeout=120,
                                                   extra_keys=["quantity", "difficulty"]))

        case "generate_flashcards":
            return _http_request("GET", _job_path("flashcards", arguments, timeout=120,
                                                   extra_keys=["quantity", "difficulty"]))

        case "generate_slides":
            return _http_request("GET", _job_path("slides", arguments, timeout=120,
                                                   extra_keys=["slide_format", "slide_length"]))

        case "generate_report":
            return _http_request("GET", _job_path("report", arguments, timeout=120,
                                                   extra_keys=["report_format"]))

        case "web_research":
            return _http_request("GET", _job_path("research", arguments, timeout=120,
                                                   extra_keys=["query"]))

        # ── New System tools ──────────────────────────────────────────────

        case "get_report_detail":
            return _http_request("GET", f"/api/reports/{arguments['edoc_id']}")

        case "mark_alert_sent":
            alert_id = arguments["alert_id"]
            return _http_request("POST", f"/api/alerts/{alert_id}/mark-sent",
                                 {"channel": arguments.get("channel", "telegram")})

        case "generate_mind_map":
            return _http_request("GET", _job_path("mind-map", arguments, timeout=120))

        case "generate_study_guide":
            return _http_request("GET", _job_path("study-guide", arguments, timeout=120))

        case "get_ticker_levels":
            return _http_request("GET", f"/api/levels/{arguments['ticker']}")

        case "list_jobs":
            status = arguments.get("status")
            path = f"/api/jobs?status={status}" if status else "/api/jobs"
            return _http_request("GET", path)

        case "get_job_status":
            return _http_request("GET", f"/api/jobs/{arguments['job_id']}")

        case "get_config":
            return _http_request("GET", "/api/config")

        case _:
            return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# MCP JSON-RPC 2.0 stdio transport
# ---------------------------------------------------------------------------

SERVER_INFO = {
    "name": "portfolio-api",
    "version": "1.0.0",
}

SERVER_CAPABILITIES = {
    "tools": {},
}


def _read_message() -> dict | None:
    """Read a JSON-RPC message from stdin using Content-Length framing."""
    while True:
        line = sys.stdin.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if line.startswith("Content-Length:"):
            content_length = int(line.split(":", 1)[1].strip())
            # Read blank line separator
            sys.stdin.readline()
            body = sys.stdin.read(content_length)
            return json.loads(body)
        elif line == "":
            continue
        else:
            # Try parsing as raw JSON (some clients skip Content-Length)
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue


def _send_message(message: dict) -> None:
    """Write a JSON-RPC message to stdout with Content-Length framing."""
    body = json.dumps(message)
    header = f"Content-Length: {len(body)}\r\n\r\n"
    sys.stdout.write(header)
    sys.stdout.write(body)
    sys.stdout.flush()


def _make_response(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _make_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _handle_request(message: dict) -> dict | None:
    """Handle a single JSON-RPC request."""
    method = message.get("method", "")
    request_id = message.get("id")
    params = message.get("params", {})

    # Notifications (no id) don't get responses
    if request_id is None and method == "notifications/initialized":
        return None

    match method:
        case "initialize":
            # Echo back the client's protocol version for compatibility
            client_version = params.get("protocolVersion", "2024-11-05")
            return _make_response(request_id, {
                "protocolVersion": client_version,
                "capabilities": SERVER_CAPABILITIES,
                "serverInfo": SERVER_INFO,
            })

        case "tools/list":
            return _make_response(request_id, {"tools": TOOLS})

        case "tools/call":
            tool_name = params.get("name", "")
            tool_arguments = params.get("arguments", {})
            result = _call_tool(tool_name, tool_arguments)
            text = json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else str(result)
            return _make_response(request_id, {
                "content": [{"type": "text", "text": text}],
            })

        case "ping":
            return _make_response(request_id, {})

        case _:
            if request_id is not None:
                return _make_error(request_id, -32601, f"Method not found: {method}")
            return None


def main() -> None:
    """Run the MCP server on stdio."""
    # Redirect stderr for logging (stdout is reserved for JSON-RPC)
    log = open("/tmp/mcp-portfolio.log", "a")

    log.write(f"MCP portfolio-api server started. FASTAPI_URL={FASTAPI_URL}\n")
    log.flush()

    while True:
        message = _read_message()
        if message is None:
            log.write("EOF on stdin, exiting.\n")
            break

        log.write(f"<< {json.dumps(message)[:200]}\n")
        log.flush()

        response = _handle_request(message)
        if response is not None:
            log.write(f">> {json.dumps(response)[:200]}\n")
            log.flush()
            _send_message(response)

    log.close()


if __name__ == "__main__":
    main()
