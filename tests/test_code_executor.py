"""Tests for the code runner used by code-gen agents."""

import pandas as pd
from app.agents.code_executor import run_generated_code


def test_simple_code():
    code = 'import json\noutput = json.dumps({"total": 42})'
    result = run_generated_code(code, {})
    assert result["success"] is True
    assert result["output"] == {"total": 42}


def test_code_with_data_context():
    code = """
import json, pandas as pd
df = data_context["prices"]
output = json.dumps({"avg": round(df["close"].mean(), 2)})
"""
    prices = pd.DataFrame({"close": [100.0, 110.0, 105.0]})
    result = run_generated_code(code, {"prices": prices})
    assert result["output"]["avg"] == 105.0


def test_syntax_error():
    result = run_generated_code("def broken(:", {})
    assert result["success"] is False
    assert "SyntaxError" in result["error"] or "invalid syntax" in result["error"]


def test_runtime_error():
    code = 'import json\nx = 1/0\noutput = json.dumps({})'
    result = run_generated_code(code, {})
    assert result["success"] is False
    assert "ZeroDivisionError" in result["error"]


def test_captures_generated_code():
    code = 'import json\noutput = json.dumps({"ok": True})'
    assert run_generated_code(code, {})["generated_code"] == code
