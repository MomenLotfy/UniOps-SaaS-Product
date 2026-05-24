"""Celery task — cleans up old audit logs, resolved alerts, and stale data."""
import asyncio
from datetime import datetime, timezone, timedelta
from app.core.celery_app import celery_app
from app.utils.logger import logger


@celery_app.task(
    name="app.tasks.cleanup_old_data.cleanup",
    bind=True,
    max_retries=1,
    soft_time_limit=1800,
)
def cleanup(self):
    """Run scheduled data cleanup tasks."""
    try:
        asyncio.run(_cleanup())
        logger.info("Data cleanup completed")
    except Exception as exc:
        logger.error(f"Data cleanup failed: {exc}")
        raise self.retry(exc=exc, countdown=3600)


async def _cleanup():
    from app.core.database import AsyncSessionLocal
    from app.models.audit_log import AuditLog
    from app.models.alert import Alert
    from app.models.ml_prediction import MLPrediction
    from sqlalchemy import delete, select

    async with AsyncSessionLocal() as db:
        audit_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        audit_result = await db.execute(
            delete(AuditLog).where(AuditLog.created_at < audit_cutoff)
        )
        logger.info(f"Deleted {audit_result.rowcount} old audit log entries (>90 days)")

        alert_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        alert_result = await db.execute(
            delete(Alert).where(
                Alert.status == "resolved",
                Alert.resolved_at < alert_cutoff,
            )
        )
        logger.info(f"Deleted {alert_result.rowcount} old resolved alerts (>30 days)")

        prediction_cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        pred_result = await db.execute(
            delete(MLPrediction).where(MLPrediction.created_at < prediction_cutoff)
        )
        logger.info(f"Deleted {pred_result.rowcount} old ML predictions (>60 days)")

        await db.commit()
        logger.info("Cleanup transaction committed")


async def cleanup_async():
    """Async version of cleanup for use in BackgroundScheduler."""
    from app.core.database import AsyncSessionLocal
    from app.models.audit_log import AuditLog
    from sqlalchemy import select, delete
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        await db.commit()
