"""Agent runner — executes any agent type."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL, AI_PROVIDER,
)
from app.models import Agent, AgentRun
from app.agents.code_executor import run_generated_code
from app.agents.registry import AgentRegistry


def _get_data_context(session: Session) -> dict:
    """Build data context for code-gen agents."""
    import pandas as pd

    tables = {"prices": "prices", "trades": "trades", "holdings": "holdings"}
    context = {}
    for key, table in tables.items():
        try:
            context[key] = pd.read_sql(f"SELECT * FROM {table}", session.bind)
        except Exception:
            context[key] = pd.DataFrame()
    return context


def _build_prompt(prompt_template: str, variables: dict, data_context: dict) -> tuple[str, str]:
    """Build system prompt and user message for code generation."""
    filled = prompt_template
    for key, value in variables.items():
        filled = filled.replace(f"{{{key}}}", str(value))

    schema_lines = []
    for name, dataframe in data_context.items():
        if hasattr(dataframe, "columns") and len(dataframe) > 0:
            schema_lines.append(f"Table '{name}': columns = {list(dataframe.columns)}")
            schema_lines.append(f"  Sample:\n{dataframe.head(3).to_string()}")
        else:
            schema_lines.append(f"Table '{name}': empty")

    system_prompt = (
        "You are a stock market data analyst. Generate Python code using pandas/numpy. "
        "Data is in data_context dict. Set 'output' to a JSON string. "
        "Return ONLY Python code, no markdown."
    )
    user_message = f"Task: {filled}\n\nData:\n{chr(10).join(schema_lines)}"
    return system_prompt, user_message


def _strip_code_fences(code: str) -> str:
    """Remove markdown code fences from generated code."""
    code = code.strip()
    for fence in ["```python", "```"]:
        if code.startswith(fence):
            code = code[len(fence):].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code


def _call_gemini(system_prompt: str, user_message: str, max_tokens: int = 2048) -> str:
    """Call Google Gemini API."""
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text.strip()


def _call_anthropic(system_prompt: str, user_message: str, max_tokens: int = 2048) -> str:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def _call_ai(system_prompt: str, user_message: str, max_tokens: int = 2048) -> str:
    """Call the configured AI provider."""
    if AI_PROVIDER == "gemini":
        return _call_gemini(system_prompt, user_message, max_tokens)
    return _call_anthropic(system_prompt, user_message, max_tokens)


def _call_ai_for_code(prompt_template: str, variables: dict, data_context: dict) -> str:
    """Call AI to generate Python analysis code."""
    system_prompt, user_message = _build_prompt(prompt_template, variables, data_context)
    return _strip_code_fences(_call_ai(system_prompt, user_message))


def run_agent(
    agent_id: str,
    variables: dict | None = None,
    session: Session | None = None,
) -> dict:
    """Execute an agent by ID. Returns dict with success, output, error."""
    if session is None:
        raise ValueError("Session required")

    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        return {"success": False, "error": f"Agent '{agent_id}' not found", "output": None}
    if not agent.enabled:
        return {"success": False, "error": f"Agent '{agent_id}' is disabled", "output": None}

    agent_run = AgentRun(
        agent_id=agent_id,
        started_at=datetime.utcnow(),
        status="running",
        input_context=json.dumps(variables or {}),
    )
    session.add(agent_run)
    session.commit()

    try:
        if agent.agent_type == "code_gen":
            data_context = _get_data_context(session)
            generated_code = _call_ai_for_code(
                agent.prompt_template, variables or {}, data_context
            )
            result = run_generated_code(generated_code, data_context)
            agent_run.generated_code = generated_code

        elif agent.agent_type == "structured_ai":
            result = _run_structured_ai(agent, variables or {})

        else:
            built_in = AgentRegistry().get(agent_id)
            if built_in:
                agent_result = built_in.run(variables or {})
                result = {
                    "success": agent_result.success,
                    "output": agent_result.output,
                    "error": agent_result.error,
                    "generated_code": None,
                }
            else:
                result = {
                    "success": False,
                    "error": f"No handler for '{agent_id}'",
                    "output": None,
                }

        agent_run.completed_at = datetime.utcnow()
        agent_run.status = "success" if result.get("success") else "error"
        agent_run.output_json = (
            json.dumps(result.get("output")) if result.get("output") else None
        )
        agent_run.error_message = result.get("error")
        session.commit()
        return result

    except Exception as err:
        agent_run.completed_at = datetime.utcnow()
        agent_run.status = "error"
        agent_run.error_message = str(err)
        session.commit()
        return {"success": False, "error": str(err), "output": None}


def _run_structured_ai(agent: Agent, variables: dict) -> dict:
    """Structured AI agent: returns JSON directly."""
    filled = agent.prompt_template or ""
    for key, value in variables.items():
        filled = filled.replace(f"{{{key}}}", str(value))

    try:
        raw_text = _call_ai(
            system_prompt="Respond ONLY with valid JSON. No markdown.",
            user_message=filled,
            max_tokens=1024,
        )
        return {
            "success": True,
            "output": json.loads(_strip_code_fences(raw_text)),
            "error": None,
            "generated_code": None,
        }
    except Exception as err:
        return {
            "success": False,
            "output": None,
            "error": str(err),
            "generated_code": None,
        }
