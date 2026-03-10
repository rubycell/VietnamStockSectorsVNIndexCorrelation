"""Agent management CRUD API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    id: str
    name: str
    description: str | None = None
    agent_type: str = "code_gen"
    prompt_template: str | None = None
    schedule: str = "on_demand"
    enabled: bool = True
    alert_on_result: bool = False


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt_template: str | None = None
    schedule: str | None = None
    enabled: bool | None = None
    alert_on_result: bool | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    agent_type: str
    prompt_template: str | None
    schedule: str
    enabled: bool
    alert_on_result: bool

    model_config = {"from_attributes": True}


@router.post("", status_code=201, response_model=AgentResponse)
def create_agent(
    data: AgentCreate,
    session: Session = Depends(get_database_session),
):
    if session.query(Agent).filter_by(id=data.id).first():
        raise HTTPException(409, "Agent already exists")
    agent = Agent(**data.model_dump())
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.get("", response_model=list[AgentResponse])
def list_agents(session: Session = Depends(get_database_session)):
    return session.query(Agent).all()


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    session: Session = Depends(get_database_session),
):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    data: AgentUpdate,
    session: Session = Depends(get_database_session),
):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: str,
    session: Session = Depends(get_database_session),
):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    session.delete(agent)
    session.commit()


from app.agents.runner import run_agent


class AgentExecuteRequest(BaseModel):
    variables: dict | None = None


@router.post("/{agent_id}/execute")
def execute_agent(
    agent_id: str,
    body: AgentExecuteRequest = AgentExecuteRequest(),
    session: Session = Depends(get_database_session),
):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return run_agent(agent_id, body.variables, session=session)
