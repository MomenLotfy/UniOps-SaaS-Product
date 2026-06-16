"""Celery task — sends pending alert notifications via email, Slack, and WebSocket."""
import asyncio
from datetime import datetime, timezone, timedelta
from app.core.celery_app import celery_app
from app.utils.logger import logger


@celery_app.task(
    name="app.tasks.send_alerts.process_pending_alerts",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=300,
)
def process_pending_alerts(self):
    """Process and deliver all pending alerts."""
    try:
        asyncio.run(_send_alerts())
        logger.info("Alert notifications sent")
    except Exception as exc:
        logger.error(f"Alert notification failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


async def _send_alerts():
    from app.core.database import CelerySessionLocal as AsyncSessionLocal
    from app.models.alert import Alert
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = await db.execute(
            select(Alert).where(
                Alert.status == "active",
                Alert.is_read == False,
                Alert.created_at >= cutoff,
                Alert.severity.in_(["critical", "high"]),
            ).limit(50)
        )
        alerts = result.scalars().all()

        if not alerts:
            return

        logger.info(f"Processing {len(alerts)} pending high-severity alerts")

        from app.services.notification_service import NotificationService
        notification_svc = NotificationService()

        for alert in alerts:
            try:
                await notification_svc.notify_alert(
                    alert.tenant_id,
                    {
                        "id": alert.id,
                        "title": alert.title,
                        "message": alert.message,
                        "severity": alert.severity,
                        "category": alert.category,
                        "resource": alert.resource,
                        "fired_at": alert.fired_at.isoformat() if alert.fired_at else None,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send alert {alert.id}: {e}")
