"""Celery task — trains/retrains ML models on tenant data."""
import asyncio
import os
from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.utils.logger import logger

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


@celery_app.task(
    name="app.tasks.train_ml_models.retrain_all",
    bind=True,
    max_retries=1,
    soft_time_limit=3600,
)
def retrain_all(self):
    """Retrain all ML models on the latest data."""
    try:
        asyncio.run(_retrain_all())
        logger.info("ML model retraining completed")
    except Exception as exc:
        logger.error(f"ML retraining failed: {exc}")
        raise self.retry(exc=exc, countdown=1800)


@celery_app.task(name="app.tasks.train_ml_models.train_cost_predictor")
def train_cost_predictor():
    asyncio.run(_train_cost_predictor())


async def _retrain_all():
    await _train_cost_predictor()
    await _train_anomaly_detector()
    logger.info("All models retrained successfully")


async def _train_cost_predictor():
    from app.core.database import CelerySessionLocal as AsyncSessionLocal
    from app.models.cost_metric import CostMetric
    from sqlalchemy import select
    import numpy as np

    os.makedirs(MODELS_DIR, exist_ok=True)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CostMetric.amount, CostMetric.period_start)
            .order_by(CostMetric.period_start.asc())
            .limit(1000)
        )
        rows = result.fetchall()

        if len(rows) < 10:
            logger.warning("Not enough cost data to train cost predictor (need ≥ 10 samples)")
            return

        amounts = [float(r[0]) for r in rows]
        from app.ml.cost_predictor import CostPredictor
        predictor = CostPredictor()

        if len(amounts) > 8:
            predictor._build_features(amounts)
            features = predictor._build_features(amounts[:-1])
            targets = np.array(amounts[1:])
            if len(features) >= len(targets):
                features = features[:len(targets)]
            predictor.train(features, targets)

        model_path = os.path.join(MODELS_DIR, "cost_predictor.pkl")
        predictor.save(model_path)

        from app.ml.model_registry import model_registry
        model_registry.register("cost_predictor", "1.0.0", {"samples": len(amounts)})
        logger.info(f"Cost predictor trained on {len(amounts)} samples and saved to {model_path}")


async def _train_anomaly_detector():
    from app.core.database import CelerySessionLocal as AsyncSessionLocal
    from app.models.cost_metric import CostMetric
    from sqlalchemy import select
    import numpy as np

    os.makedirs(MODELS_DIR, exist_ok=True)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CostMetric.amount).order_by(CostMetric.period_start.asc()).limit(500)
        )
        amounts = [float(r[0]) for r in result.fetchall()]

        if len(amounts) < 20:
            logger.warning("Not enough data to train anomaly detector")
            return

        from app.ml.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector(contamination=0.05)
        X = np.array(amounts).reshape(-1, 1)
        detector.train(X)

        model_path = os.path.join(MODELS_DIR, "anomaly_detector.pkl")
        detector.save(model_path)

        from app.ml.model_registry import model_registry
        model_registry.register("anomaly_detector", "1.0.0", {"samples": len(amounts)})
        logger.info(f"Anomaly detector trained on {len(amounts)} samples")
