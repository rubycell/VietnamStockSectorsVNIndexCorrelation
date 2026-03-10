"""Alerts API — alert history and management."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class MarkSentRequest(BaseModel):
    """Request body for marking an alert as sent."""

    channel: str


@router.get("")
def list_alerts(
    ticker: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_database_session),
):
    """List alerts, optionally filtered by ticker."""
    query = session.query(Alert).order_by(Alert.created_at.desc())

    if ticker:
        query = query.filter_by(ticker=ticker.upper())

    alerts = query.limit(limit).all()

    return [
        {
            "id": alert.id,
            "ticker": alert.ticker,
            "rule_id": alert.rule_id,
            "severity": alert.severity,
            "message": alert.message,
            "sent_telegram": alert.sent_telegram,
            "sent_whatsapp": alert.sent_whatsapp,
            "created_at": str(alert.created_at) if alert.created_at else None,
        }
        for alert in alerts
    ]


@router.post("/{alert_id}/mark-sent")
def mark_alert_sent(
    alert_id: int,
    body: MarkSentRequest,
    session: Session = Depends(get_database_session),
):
    """Mark an alert as sent via a specific channel."""
    alert = session.query(Alert).filter_by(id=alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if body.channel == "telegram":
        alert.sent_telegram = True
    elif body.channel == "whatsapp":
        alert.sent_whatsapp = True
    else:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {body.channel}")

    session.commit()
    return {"id": alert.id, "channel": body.channel, "marked": True}


@router.get("/unsent")
def list_unsent_alerts(
    channel: str = "telegram",
    limit: int = 50,
    session: Session = Depends(get_database_session),
):
    """List alerts that have not been sent to a specific channel."""
    query = session.query(Alert).order_by(Alert.created_at.desc())

    if channel == "telegram":
        query = query.filter_by(sent_telegram=False)
    elif channel == "whatsapp":
        query = query.filter_by(sent_whatsapp=False)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")

    alerts = query.limit(limit).all()

    return [
        {
            "id": alert.id,
            "ticker": alert.ticker,
            "rule_id": alert.rule_id,
            "severity": alert.severity,
            "message": alert.message,
            "created_at": str(alert.created_at) if alert.created_at else None,
        }
        for alert in alerts
    ]
