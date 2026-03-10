"""Seed initial agent definitions."""

from sqlalchemy.orm import Session
from app.models import Agent

INITIAL_AGENTS = [
    {
        "id": "fud-assessor",
        "name": "FUD Assessor",
        "description": "Assess current market FUD level using VN-Index data and sector indicators",
        "agent_type": "structured_ai",
        "prompt_template": (
            "Analyze the current Vietnamese stock market conditions. "
            "VN-Index change today: {vnindex_change}%. "
            "Sectors with >50% oversold stocks: {fud_sectors}. "
            "Respond with JSON: {{\"fud_level\": \"low/medium/high\", "
            "\"summary\": \"1-2 sentence assessment\", "
            "\"recommendation\": \"action suggestion\"}}"
        ),
        "schedule": "on_demand",
        "enabled": True,
        "alert_on_result": False,
    },
    {
        "id": "trendy-sector-detector",
        "name": "Trendy Sector Detector",
        "description": "Find sectors with improving breadth (fewer oversold stocks over time)",
        "agent_type": "code_gen",
        "prompt_template": (
            "Analyze the prices table to find sectors where stocks are trending up. "
            "Look for stocks where the 20-day moving average is rising. "
            "Group by ICB sector if available. Return the top 3 trending sectors."
        ),
        "schedule": "hourly",
        "enabled": True,
        "alert_on_result": True,
    },
    {
        "id": "unusual-volume-scanner",
        "name": "Unusual Volume Scanner",
        "description": "Detect stocks with volume significantly above their 20-day average",
        "agent_type": "code_gen",
        "prompt_template": (
            "Scan the prices table for stocks where today's volume is more than "
            "{volume_multiplier}x their 20-day average volume. "
            "Return ticker, today's volume, average volume, and the multiplier."
        ),
        "schedule": "hourly",
        "enabled": True,
        "alert_on_result": True,
    },
    {
        "id": "sector-rotation-tracker",
        "name": "Sector Rotation Tracker",
        "description": "Track money flow between sectors using relative performance",
        "agent_type": "code_gen",
        "prompt_template": (
            "Compare sector performance over the last {lookback_days} days. "
            "Calculate average return per sector. Identify sectors gaining vs losing momentum."
        ),
        "schedule": "daily",
        "enabled": True,
        "alert_on_result": False,
    },
    {
        "id": "oversold-bounce-finder",
        "name": "Oversold Bounce Finder",
        "description": "Find stocks bouncing from oversold conditions (potential buy signals)",
        "agent_type": "code_gen",
        "prompt_template": (
            "Find stocks in the prices table where: "
            "1) Stochastic was below 20 within the last 5 days, "
            "2) Current close is above the 5-day low. "
            "These are potential bounce candidates."
        ),
        "schedule": "daily",
        "enabled": True,
        "alert_on_result": True,
    },
    {
        "id": "correlation-breakdown-alert",
        "name": "Correlation Breakdown Alert",
        "description": "Detect when a stock's correlation with VN-Index breaks down",
        "agent_type": "code_gen",
        "prompt_template": (
            "For holdings tickers, calculate 20-day rolling correlation with VN-Index. "
            "Flag any ticker where correlation dropped below 0.3 (unusual divergence)."
        ),
        "schedule": "daily",
        "enabled": True,
        "alert_on_result": True,
    },
    {
        "id": "portfolio-risk-monitor",
        "name": "Portfolio Risk Monitor",
        "description": "Calculate portfolio-level risk metrics",
        "agent_type": "code_gen",
        "prompt_template": (
            "Using the holdings and prices tables, calculate: "
            "1) Portfolio beta vs VN-Index, "
            "2) Maximum drawdown of each holding over last 30 days, "
            "3) Concentration risk (% in top 3 holdings)."
        ),
        "schedule": "hourly",
        "enabled": True,
        "alert_on_result": False,
    },
    {
        "id": "earnings-momentum-scanner",
        "name": "Earnings Momentum Scanner",
        "description": "Identify stocks with strong price momentum that may indicate earnings",
        "agent_type": "code_gen",
        "prompt_template": (
            "Find stocks with: 1) 5-day return > 5%, 2) Volume increasing. "
            "These may be reacting to earnings or news. Return top candidates."
        ),
        "schedule": "daily",
        "enabled": True,
        "alert_on_result": True,
    },
    {
        "id": "support-level-proximity",
        "name": "Support Level Proximity",
        "description": "Alert when holdings approach key support levels",
        "agent_type": "code_gen",
        "prompt_template": (
            "For each holding, check if current price is within 3% of: "
            "1) 50-day SMA, 2) 200-day SMA, 3) Recent swing low. "
            "These are potential support test areas."
        ),
        "schedule": "hourly",
        "enabled": True,
        "alert_on_result": True,
    },
    {
        "id": "market-breadth-analyzer",
        "name": "Market Breadth Analyzer",
        "description": "Analyze overall market health using breadth indicators",
        "agent_type": "code_gen",
        "prompt_template": (
            "Using all available price data, calculate: "
            "1) % of stocks above their 50-day SMA, "
            "2) Advance/decline ratio for the last 5 days, "
            "3) New 20-day highs vs lows. Summarize market health."
        ),
        "schedule": "daily",
        "enabled": True,
        "alert_on_result": False,
    },
]


def seed_agents(session: Session) -> int:
    """Seed initial agent definitions. Idempotent -- skips existing agents.

    Returns number of agents created.
    """
    created = 0
    for agent_data in INITIAL_AGENTS:
        existing = session.query(Agent).filter_by(id=agent_data["id"]).first()
        if not existing:
            session.add(Agent(**agent_data))
            created += 1

    session.commit()
    return created
