"""Full check cycle endpoint — called by OpenClaw cron."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Agent, Holding
from app.agents.runner import run_agent

router = APIRouter(tags=["check-cycle"])


@router.post("/api/check-cycle")
def run_check_cycle(session: Session = Depends(get_database_session)):
    """Run the full hourly check: prices -> portfolio -> swing lows -> rules -> scheduled agents."""
    tickers = [h.ticker for h in session.query(Holding.ticker).filter(Holding.total_shares > 0).all()]
    variables = {"tickers": tickers, "timestamp": datetime.utcnow().isoformat()}

    results = {}
    errors = []

    for agent_id in ["price-fetcher", "portfolio-calculator", "swing-low-detector", "rule-evaluator"]:
        result = run_agent(agent_id, variables=variables, session=session)
        results[agent_id] = result
        if not result.get("success"):
            errors.append({"agent": agent_id, "error": result.get("error")})

    scheduled = (
        session.query(Agent)
        .filter_by(schedule="hourly", enabled=True)
        .filter(Agent.agent_type.in_(["code_gen", "structured_ai"]))
        .all()
    )
    for agent_def in scheduled:
        result = run_agent(agent_def.id, variables=variables, session=session)
        results[agent_def.id] = result
        if not result.get("success"):
            errors.append({"agent": agent_def.id, "error": result.get("error")})

    return {"success": True, "results": results, "errors": errors}
