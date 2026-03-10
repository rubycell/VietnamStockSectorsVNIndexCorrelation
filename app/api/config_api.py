"""Configuration key-value API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Config as ConfigModel

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigValue(BaseModel):
    value: str
    description: str | None = None


@router.get("")
def list_config(session: Session = Depends(get_database_session)):
    """List all config entries."""
    configs = session.query(ConfigModel).order_by(ConfigModel.key).all()
    return [
        {"key": c.key, "value": c.value, "description": c.description}
        for c in configs
    ]


@router.get("/{key}")
def get_config(key: str, session: Session = Depends(get_database_session)):
    """Get a single config value."""
    config = session.query(ConfigModel).filter_by(key=key).first()
    if not config:
        raise HTTPException(404, f"Config key '{key}' not found")
    return {"key": config.key, "value": config.value, "description": config.description}


@router.put("/{key}")
def set_config(key: str, body: ConfigValue, session: Session = Depends(get_database_session)):
    """Set a config value (upsert)."""
    config = session.query(ConfigModel).filter_by(key=key).first()
    if config:
        config.value = body.value
        if body.description is not None:
            config.description = body.description
        config.updated_at = datetime.utcnow()
    else:
        config = ConfigModel(key=key, value=body.value, description=body.description)
        session.add(config)

    session.commit()
    return {"key": key, "value": body.value, "description": body.description}
