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


CHANNEL_FIELDS = {
    "telegram": "sent_telegram",
    "discord": "sent_discord",
    "whatsapp": "sent_whatsapp",
}


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
            "sent_discord": getattr(alert, "sent_discord", False),
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

    field = CHANNEL_FIELDS.get(body.channel)
    if not field:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {body.channel}")

    setattr(alert, field, True)
    session.commit()
    return {"id": alert.id, "channel": body.channel, "marked": True}


@router.get("/unsent")
def list_unsent_alerts(
    channel: str = "discord",
    limit: int = 50,
    session: Session = Depends(get_database_session),
):
    """List alerts that have not been sent to a specific channel."""
    field = CHANNEL_FIELDS.get(channel)
    if not field:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")

    query = (
        session.query(Alert)
        .filter(getattr(Alert, field) == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
    )

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
