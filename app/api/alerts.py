"""Alerts API — alert history and management."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


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
