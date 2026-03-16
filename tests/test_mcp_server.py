"""Tests for MCP portfolio server — all 36 tools.

Tests mock _http_request to verify dispatch logic without a running backend.
"""

import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Add the MCP server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "openclaw", "mcp"))
import portfolio_server as mcp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_RESPONSE = {"ok": True}


def call_tool(name: str, arguments: dict | None = None) -> dict:
    """Call a tool through _call_tool with mocked HTTP."""
    with patch.object(mcp, "_http_request", return_value=MOCK_RESPONSE) as mock_http:
        result = mcp._call_tool(name, arguments or {})
    return result, mock_http


# ---------------------------------------------------------------------------
# Test: All 36 tool names exist in TOOLS list
# ---------------------------------------------------------------------------

EXPECTED_TOOLS = [
    # Group 1: Portfolio & Trading (12)
    "get_portfolio",
    "get_portfolio_ticker",
    "import_snapshot",
    "get_positions",
    "update_position",
    "delete_position",
    "fetch_prices",
    "evaluate_rules",
    "run_check_cycle",
    "list_alerts",
    "list_unsent_alerts",
    # Group 2: NotebookLM & Artifacts (14)
    "list_reports",
    "fetch_new_reports",
    "analyze_report",
    "list_notebooks",
    "notebook_chat",
    "notebook_summary",
    "generate_infographic",
    "generate_audio",
    "generate_video",
    "generate_quiz",
    "generate_flashcards",
    "generate_slides",
    "generate_report",
    "web_research",
    # Group 3: Agents, Search & System (11)
    "list_agents",
    "execute_agent",
    "google_search",
    "get_report_detail",
    "mark_alert_sent",
    "generate_mind_map",
    "generate_study_guide",
    "get_ticker_levels",
    "list_jobs",
    "get_job_status",
    "get_config",
]


def test_tool_count():
    """MCP server must have exactly 36 tools."""
    assert len(mcp.TOOLS) == 36


def test_all_expected_tools_exist():
    """Every expected tool name must be in the TOOLS list."""
    tool_names = {t["name"] for t in mcp.TOOLS}
    for name in EXPECTED_TOOLS:
        assert name in tool_names, f"Missing tool: {name}"


def test_no_unexpected_tools():
    """No tools outside the expected set."""
    tool_names = {t["name"] for t in mcp.TOOLS}
    expected_set = set(EXPECTED_TOOLS)
    unexpected = tool_names - expected_set
    assert not unexpected, f"Unexpected tools: {unexpected}"


def test_all_tools_have_input_schema():
    """Every tool must have a valid inputSchema."""
    for tool in mcp.TOOLS:
        assert "inputSchema" in tool, f"{tool['name']} missing inputSchema"
        assert tool["inputSchema"]["type"] == "object", f"{tool['name']} schema type != object"


def test_all_tools_have_description():
    """Every tool must have a non-empty description."""
    for tool in mcp.TOOLS:
        assert tool.get("description"), f"{tool['name']} missing description"


# ---------------------------------------------------------------------------
# Test: Tool dispatch — existing tools (13)
# ---------------------------------------------------------------------------

class TestExistingTools:
    """Tests for the 13 tools that already exist."""

    def test_get_portfolio(self):
        result, mock = call_tool("get_portfolio")
        mock.assert_called_once_with("GET", "/api/portfolio")

    def test_get_portfolio_ticker(self):
        result, mock = call_tool("get_portfolio_ticker", {"ticker": "VCB"})
        mock.assert_called_once_with("GET", "/api/portfolio/VCB")

    def test_list_reports(self):
        result, mock = call_tool("list_reports")
        mock.assert_called_once_with("GET", "/api/reports")

    def test_fetch_new_reports(self):
        result, mock = call_tool("fetch_new_reports")
        mock.assert_called_once_with("POST", "/api/reports/fetch")

    def test_analyze_report_minimal(self):
        result, mock = call_tool("analyze_report", {"edoc_id": "abc123"})
        mock.assert_called_once_with("POST", "/api/analyze", {"edoc_id": "abc123"})

    def test_analyze_report_with_question(self):
        result, mock = call_tool("analyze_report", {"edoc_id": "abc", "question": "What?"})
        mock.assert_called_once_with("POST", "/api/analyze", {"edoc_id": "abc", "question": "What?"})

    def test_run_check_cycle(self):
        result, mock = call_tool("run_check_cycle")
        mock.assert_called_once_with("POST", "/api/check-cycle")

    def test_list_alerts_no_filter(self):
        result, mock = call_tool("list_alerts")
        mock.assert_called_once_with("GET", "/api/alerts")

    def test_list_alerts_with_ticker(self):
        result, mock = call_tool("list_alerts", {"ticker": "FPT"})
        mock.assert_called_once_with("GET", "/api/alerts?ticker=FPT")

    def test_list_unsent_alerts_default(self):
        result, mock = call_tool("list_unsent_alerts")
        mock.assert_called_once_with("GET", "/api/alerts/unsent?channel=telegram")

    def test_list_unsent_alerts_discord(self):
        result, mock = call_tool("list_unsent_alerts", {"channel": "discord"})
        mock.assert_called_once_with("GET", "/api/alerts/unsent?channel=discord")

    def test_fetch_prices(self):
        result, mock = call_tool("fetch_prices")
        mock.assert_called_once_with("POST", "/api/prices/fetch")

    def test_evaluate_rules(self):
        result, mock = call_tool("evaluate_rules")
        mock.assert_called_once_with("POST", "/api/rules/evaluate")

    def test_list_agents(self):
        result, mock = call_tool("list_agents")
        mock.assert_called_once_with("GET", "/api/agents")

    def test_execute_agent(self):
        result, mock = call_tool("execute_agent", {"agent_id": 3})
        mock.assert_called_once_with("POST", "/api/agents/3/execute")

    def test_google_search(self):
        result, mock = call_tool("google_search", {"query": "HPG news"})
        call_args = mock.call_args
        assert call_args[0][0] == "GET"
        assert "/api/search?" in call_args[0][1]
        assert "HPG" in call_args[0][1]


# ---------------------------------------------------------------------------
# Test: Tool dispatch — new Portfolio & Trading tools (4)
# ---------------------------------------------------------------------------

class TestNewPortfolioTools:

    def test_import_snapshot(self):
        result, mock = call_tool("import_snapshot", {"text": "| Ticker | Shares |\n| VCB | 100 |"})
        mock.assert_called_once_with("POST", "/api/import-snapshot", {"text": "| Ticker | Shares |\n| VCB | 100 |"})

    def test_get_positions(self):
        result, mock = call_tool("get_positions", {"ticker": "FPT"})
        mock.assert_called_once_with("GET", "/api/positions/FPT")

    def test_update_position(self):
        result, mock = call_tool("update_position", {"position_id": 5, "avg_price": 50000, "remaining": 200})
        mock.assert_called_once_with("PUT", "/api/positions/5", {"avg_price": 50000, "remaining": 200})

    def test_delete_position(self):
        result, mock = call_tool("delete_position", {"position_id": 7})
        mock.assert_called_once_with("DELETE", "/api/positions/7")


# ---------------------------------------------------------------------------
# Test: Tool dispatch — new NotebookLM & Artifacts tools (11)
# ---------------------------------------------------------------------------

class TestNewNotebookTools:

    def test_list_notebooks(self):
        result, mock = call_tool("list_notebooks")
        mock.assert_called_once_with("GET", "/api/analyze/notebooks")

    def test_notebook_chat(self):
        result, mock = call_tool("notebook_chat", {"notebook_id": "nb1", "question": "Summary?"})
        call_args = mock.call_args[0]
        assert call_args[0] == "GET"
        assert "/api/jobs/start/chat?" in call_args[1]
        assert "notebook_id=nb1" in call_args[1]
        assert "question=" in call_args[1]
        assert "wait=true" in call_args[1]

    def test_notebook_summary(self):
        result, mock = call_tool("notebook_summary", {"notebook_id": "nb1"})
        call_args = mock.call_args[0]
        assert call_args[0] == "GET"
        assert "/api/jobs/start/notebook-summary?" in call_args[1]
        assert "notebook_id=nb1" in call_args[1]
        assert "wait=true" in call_args[1]

    def test_generate_infographic(self):
        result, mock = call_tool("generate_infographic", {"notebook_id": "nb1"})
        call_args = mock.call_args[0]
        assert call_args[0] == "GET"
        assert "/api/jobs/start/infographic?" in call_args[1]
        assert "notebook_id=nb1" in call_args[1]
        assert "wait=true" in call_args[1]

    def test_generate_infographic_with_options(self):
        result, mock = call_tool("generate_infographic", {
            "notebook_id": "nb1", "orientation": "landscape", "detail_level": "detailed"
        })
        call_args = mock.call_args[0][1]
        assert "orientation=landscape" in call_args
        assert "detail_level=detailed" in call_args

    def test_generate_audio(self):
        result, mock = call_tool("generate_audio", {"notebook_id": "nb1"})
        call_args = mock.call_args[0]
        assert call_args[0] == "GET"
        assert "/api/jobs/start/audio?" in call_args[1]
        assert "wait=true" in call_args[1]

    def test_generate_audio_with_options(self):
        result, mock = call_tool("generate_audio", {
            "notebook_id": "nb1", "audio_format": "debate", "audio_length": "long"
        })
        call_args = mock.call_args[0][1]
        assert "audio_format=debate" in call_args
        assert "audio_length=long" in call_args

    def test_generate_video(self):
        result, mock = call_tool("generate_video", {"notebook_id": "nb1"})
        call_args = mock.call_args[0]
        assert call_args[0] == "GET"
        assert "/api/jobs/start/video?" in call_args[1]

    def test_generate_video_with_style(self):
        result, mock = call_tool("generate_video", {
            "notebook_id": "nb1", "video_style": "whiteboard"
        })
        assert "video_style=whiteboard" in mock.call_args[0][1]

    def test_generate_quiz(self):
        result, mock = call_tool("generate_quiz", {"notebook_id": "nb1"})
        call_args = mock.call_args[0]
        assert "/api/jobs/start/quiz?" in call_args[1]
        assert "wait=true" in call_args[1]

    def test_generate_flashcards(self):
        result, mock = call_tool("generate_flashcards", {"notebook_id": "nb1"})
        assert "/api/jobs/start/flashcards?" in mock.call_args[0][1]

    def test_generate_slides(self):
        result, mock = call_tool("generate_slides", {"notebook_id": "nb1"})
        assert "/api/jobs/start/slides?" in mock.call_args[0][1]

    def test_generate_report(self):
        result, mock = call_tool("generate_report", {"notebook_id": "nb1"})
        assert "/api/jobs/start/report?" in mock.call_args[0][1]

    def test_web_research(self):
        result, mock = call_tool("web_research", {"notebook_id": "nb1", "query": "HPG outlook"})
        call_args = mock.call_args[0][1]
        assert "/api/jobs/start/research?" in call_args
        assert "notebook_id=nb1" in call_args
        assert "HPG" in call_args
        assert "wait=true" in call_args


# ---------------------------------------------------------------------------
# Test: Tool dispatch — new System tools (8)
# ---------------------------------------------------------------------------

class TestNewSystemTools:

    def test_get_report_detail(self):
        result, mock = call_tool("get_report_detail", {"edoc_id": "rpt123"})
        mock.assert_called_once_with("GET", "/api/reports/rpt123")

    def test_mark_alert_sent(self):
        result, mock = call_tool("mark_alert_sent", {"alert_id": 42, "channel": "discord"})
        mock.assert_called_once_with("POST", "/api/alerts/42/mark-sent", {"channel": "discord"})

    def test_generate_mind_map(self):
        result, mock = call_tool("generate_mind_map", {"notebook_id": "nb1"})
        call_args = mock.call_args[0]
        assert "/api/jobs/start/mind-map?" in call_args[1]
        assert "wait=true" in call_args[1]

    def test_generate_study_guide(self):
        result, mock = call_tool("generate_study_guide", {"notebook_id": "nb1"})
        assert "/api/jobs/start/study-guide?" in mock.call_args[0][1]

    def test_get_ticker_levels(self):
        result, mock = call_tool("get_ticker_levels", {"ticker": "HPG"})
        mock.assert_called_once_with("GET", "/api/levels/HPG")

    def test_list_jobs(self):
        result, mock = call_tool("list_jobs")
        mock.assert_called_once_with("GET", "/api/jobs")

    def test_list_jobs_with_status(self):
        result, mock = call_tool("list_jobs", {"status": "completed"})
        mock.assert_called_once_with("GET", "/api/jobs?status=completed")

    def test_get_job_status(self):
        result, mock = call_tool("get_job_status", {"job_id": "job-abc"})
        mock.assert_called_once_with("GET", "/api/jobs/job-abc")

    def test_get_config(self):
        result, mock = call_tool("get_config")
        mock.assert_called_once_with("GET", "/api/config")


# ---------------------------------------------------------------------------
# Test: Unknown tool returns error
# ---------------------------------------------------------------------------

def test_unknown_tool():
    result, _ = call_tool("nonexistent_tool")
    assert "error" in result
    assert "Unknown tool" in result["error"]


# ---------------------------------------------------------------------------
# Test: JSON-RPC protocol
# ---------------------------------------------------------------------------

class TestJsonRpcProtocol:

    def test_handle_initialize(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
        response = mcp._handle_request(msg)
        assert response["id"] == 1
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert "serverInfo" in response["result"]

    def test_handle_tools_list(self):
        msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = mcp._handle_request(msg)
        assert response["id"] == 2
        assert len(response["result"]["tools"]) == 36

    def test_handle_tools_call(self):
        msg = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "get_portfolio", "arguments": {}},
        }
        with patch.object(mcp, "_http_request", return_value={"holdings": []}):
            response = mcp._handle_request(msg)
        assert response["id"] == 3
        assert response["result"]["content"][0]["type"] == "text"

    def test_handle_ping(self):
        msg = {"jsonrpc": "2.0", "id": 4, "method": "ping", "params": {}}
        response = mcp._handle_request(msg)
        assert response["id"] == 4
        assert response["result"] == {}

    def test_handle_unknown_method(self):
        msg = {"jsonrpc": "2.0", "id": 5, "method": "unknown/method", "params": {}}
        response = mcp._handle_request(msg)
        assert response["error"]["code"] == -32601

    def test_handle_notification_no_response(self):
        msg = {"method": "notifications/initialized", "params": {}}
        response = mcp._handle_request(msg)
        assert response is None

    def test_make_response(self):
        resp = mcp._make_response(1, {"data": "test"})
        assert resp == {"jsonrpc": "2.0", "id": 1, "result": {"data": "test"}}

    def test_make_error(self):
        resp = mcp._make_error(1, -32600, "Invalid request")
        assert resp["error"]["code"] == -32600
        assert resp["error"]["message"] == "Invalid request"


# ---------------------------------------------------------------------------
# Test: Job tools all use wait=true and correct timeout
# ---------------------------------------------------------------------------

JOB_TOOLS_AND_TIMEOUTS = [
    ("notebook_chat", {"notebook_id": "n", "question": "q"}, 60),
    ("notebook_summary", {"notebook_id": "n"}, 60),
    ("generate_infographic", {"notebook_id": "n"}, 120),
    ("generate_audio", {"notebook_id": "n"}, 180),
    ("generate_video", {"notebook_id": "n"}, 300),
    ("generate_quiz", {"notebook_id": "n"}, 120),
    ("generate_flashcards", {"notebook_id": "n"}, 120),
    ("generate_slides", {"notebook_id": "n"}, 120),
    ("generate_report", {"notebook_id": "n"}, 120),
    ("web_research", {"notebook_id": "n", "query": "q"}, 120),
    ("generate_mind_map", {"notebook_id": "n"}, 120),
    ("generate_study_guide", {"notebook_id": "n"}, 120),
]


@pytest.mark.parametrize("tool_name,args,expected_timeout", JOB_TOOLS_AND_TIMEOUTS)
def test_job_tool_uses_wait_and_timeout(tool_name, args, expected_timeout):
    """All job-based tools must include wait=true and correct timeout."""
    result, mock = call_tool(tool_name, args)
    path = mock.call_args[0][1]
    assert "wait=true" in path, f"{tool_name} missing wait=true"
    assert f"timeout={expected_timeout}" in path, f"{tool_name} expected timeout={expected_timeout}, got: {path}"
