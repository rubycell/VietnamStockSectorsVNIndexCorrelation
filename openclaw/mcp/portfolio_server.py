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
import urllib.request
from typing import Any

FASTAPI_URL = os.environ.get("FASTAPI_URL", "http://fastapi:8000")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_reports",
        "description": (
            "List broker analysis reports from Vietstock and CafeF. "
            "Returns report id, ticker, title, source, date, and download URL."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "fetch_new_reports",
        "description": (
            "Scrape Vietstock and CafeF for new broker analysis reports. "
            "Saves new reports to the database. Returns count of new reports found."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "analyze_report",
        "description": (
            "Analyze a broker report using Google NotebookLM. Downloads the PDF "
            "and processes it through NotebookLM for accurate, source-grounded answers. "
            "ALWAYS use this for any question about report content — never answer from your own knowledge."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "edoc_id": {
                    "type": "string",
                    "description": "The report's edoc_id from list_reports results.",
                },
                "question": {
                    "type": "string",
                    "description": (
                        "Question to ask about the report. Defaults to a Vietnamese summary "
                        "with key recommendations and target prices. Accepts any language."
                    ),
                },
            },
            "required": ["edoc_id"],
        },
    },
    {
        "name": "get_portfolio",
        "description": "Get full portfolio summary with all holdings, P&L, and position status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_portfolio_ticker",
        "description": "Get detailed holdings for a single ticker including position breakdown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. VCB, FPT, FRT).",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "run_check_cycle",
        "description": (
            "Run the full trading check cycle: fetch prices, update portfolio, "
            "detect swing lows, evaluate rules, and check for alerts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_alerts",
        "description": "List trading alerts, optionally filtered by ticker.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Optional ticker to filter alerts.",
                },
            },
        },
    },
    {
        "name": "list_unsent_alerts",
        "description": "List alerts that have not been sent to a specific channel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name (e.g. telegram, discord).",
                    "default": "telegram",
                },
            },
        },
    },
    {
        "name": "fetch_prices",
        "description": "Fetch latest stock prices from vnstock and update the cache.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "evaluate_rules",
        "description": "Evaluate all trading rules against current holdings.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_agents",
        "description": "List all configured AI agents.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "execute_agent",
        "description": "Execute a specific AI agent by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "The agent's numeric ID.",
                },
            },
            "required": ["agent_id"],
        },
    },
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
