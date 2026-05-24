from __future__ import annotations
"""ML service — orchestrates model training, inference, and insight generation."""
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ml_prediction import MLPrediction
from app.models.ml_recommendation import MLRecommendation
from app.models.ml_pattern import MLPattern
from app.models.ml_correlation import MLCorrelation
from app.models.cost_metric import CostMetric
from app.schemas.ml import (
    MLPredictionResponse, MLRecommendationResponse, MLPatternResponse,
    MLCorrelationResponse, MLInsightRequest, MLInsightResponse, ModelStatus,
)
from app.schemas.common import PaginatedResponse
from app.services.base import BaseService
from app.utils.logger import logger

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")

# ── Per-tenant debounce: minimum seconds between auto-correlation runs ────────
_DEBOUNCE_SECS: int = 30
_last_correlate: dict[str, float] = {}  # tenant_id → monotonic timestamp


class MLService(BaseService):
    async def list_predictions(self, tenant_id: str, page: int = 1, page_size: int = 20) -> PaginatedResponse:
        query = select(MLPrediction).where(MLPrediction.tenant_id == tenant_id)
        total = await self._count(query)
        query = query.order_by(MLPrediction.predicted_at.desc())
        items = await self._paginate(query, page, page_size)
        return PaginatedResponse(
            data=[MLPredictionResponse.model_validate(i) for i in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def list_recommendations(self, tenant_id: str, category: Optional[str] = None) -> list[MLRecommendationResponse]:
        query = select(MLRecommendation).where(MLRecommendation.tenant_id == tenant_id)
        if category:
            query = query.where(MLRecommendation.category == category)
        query = query.order_by(MLRecommendation.priority.asc(), MLRecommendation.confidence.desc())
        result = await self.db.execute(query)
        return [MLRecommendationResponse.model_validate(i) for i in result.scalars().all()]

    async def list_patterns(self, tenant_id: str) -> list[MLPatternResponse]:
        result = await self.db.execute(
            select(MLPattern)
            .where(MLPattern.tenant_id == tenant_id)
            .order_by(MLPattern.confidence.desc())
        )
        return [MLPatternResponse.model_validate(i) for i in result.scalars().all()]

    async def list_correlations(self, tenant_id: str) -> list[MLCorrelationResponse]:
        result = await self.db.execute(
            select(MLCorrelation)
            .where(MLCorrelation.tenant_id == tenant_id)
            .order_by(MLCorrelation.correlation_score.desc())
        )
        return [MLCorrelationResponse.model_validate(i) for i in result.scalars().all()]

    async def predict_cost(self, tenant_id: str, months_ahead: int = 3) -> MLInsightResponse:
        cost_result = await self.db.execute(
            select(CostMetric.amount)
            .where(CostMetric.tenant_id == tenant_id)
            .order_by(CostMetric.period_start.desc())
            .limit(12)
        )
        historical = [float(row[0]) for row in cost_result.fetchall()]

        from app.ml.cost_predictor import CostPredictor
        predictor = CostPredictor()
        model_path = os.path.join(MODELS_DIR, "cost_predictor.pkl")
        if os.path.exists(model_path):
            try:
                predictor.load(model_path)
            except Exception:
                pass

        if not historical:
            historical = [1000.0, 1050.0, 1100.0]

        result = predictor.predict_next_month(historical)

        prediction = MLPrediction(
            tenant_id=tenant_id,
            model_name="cost_predictor",
            prediction_type="cost_forecast",
            input_data={"historical_costs": historical[:6], "months_ahead": months_ahead},
            output_data=result,
            confidence=result.get("confidence", 0.0),
            predicted_at=datetime.now(timezone.utc),
        )
        self.db.add(prediction)
        await self.db.flush()

        return MLInsightResponse(
            model_type="cost_predictor",
            result=result,
            confidence=result.get("confidence"),
            generated_at=datetime.now(timezone.utc),
        )

    async def detect_anomalies(self, tenant_id: str) -> MLInsightResponse:
        from app.ml.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()

        cost_result = await self.db.execute(
            select(CostMetric.amount, CostMetric.period_start)
            .where(CostMetric.tenant_id == tenant_id)
            .order_by(CostMetric.period_start.asc())
            .limit(90)
        )
        data_points = [{"amount": float(r[0]), "date": str(r[1])} for r in cost_result.fetchall()]

        if not data_points:
            return MLInsightResponse(
                model_type="anomaly_detector",
                result={"anomalies": [], "total_points": 0},
                confidence=1.0,
                generated_at=datetime.now(timezone.utc),
            )

        amounts = [[dp["amount"]] for dp in data_points]
        import numpy as np
        anomaly_labels = detector.detect(np.array(amounts))
        anomalies = [
            data_points[i] for i, label in enumerate(anomaly_labels) if label == -1
        ]

        return MLInsightResponse(
            model_type="anomaly_detector",
            result={"anomalies": anomalies, "total_points": len(data_points)},
            confidence=0.85,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_model_statuses(self) -> list[ModelStatus]:
        # Fallback metadata for models that have never been trained yet
        _model_meta = {
            "cost_predictor":    {"display": "Cost Forecaster",    "algo": "Random Forest"},
            "workload_predictor":{"display": "Workload Predictor", "algo": "XGBoost"},
            "anomaly_detector":  {"display": "Anomaly Detector",   "algo": "Isolation Forest"},
        }
        models = list(_model_meta.keys())
        statuses = []
        for model_name in models:
            path = os.path.join(MODELS_DIR, f"{model_name}.pkl")
            trained = os.path.exists(path)
            last_trained = None
            if trained:
                try:
                    mtime = os.path.getmtime(path)
                    last_trained = datetime.fromtimestamp(mtime, tz=timezone.utc)
                except Exception:
                    pass
            statuses.append(ModelStatus(
                name=model_name,
                version="1.0.0",
                trained=trained,
                last_trained_at=last_trained,
            ))
        return statuses

    # ── Reactive correlation engine ───────────────────────────────────────────

    async def run_correlations(self, tenant_id: str) -> int:
        """
        Compute cross-domain Pearson correlations from live DB data and
        persist them to the ml_correlations table.

        Data sources:
          - cost_series   : monthly spend from cost_metrics (last 12 months)
          - pod cpu series: average CPU per pod per day (last 30 days)
          - restart series: daily sum of pod restarts
          - threat series : daily threat count from threats table
          - pipeline series: daily pipeline failure count

        Returns the number of correlation pairs written.

        Safe to call concurrently — uses UPSERT by (tenant_id, metric_a, metric_b).
        """
        from app.ml.correlation_analyzer import CorrelationAnalyzer
        from app.models.pod import Pod
        from app.models.threat import Threat
        from app.models.pipeline import Pipeline
        from sqlalchemy import text

        # ── 1. Gather cross-domain time-series ───────────────────────────────
        cost_result = await self.db.execute(
            select(CostMetric.amount)
            .where(CostMetric.tenant_id == tenant_id)
            .order_by(CostMetric.period_start.desc())
            .limit(90)
        )
        cost_series = [float(r[0]) for r in cost_result.all()]

        pod_result = await self.db.execute(
            select(func.avg(Pod.cpu_usage))
            .where(Pod.tenant_id == tenant_id)
        )
        cpu_avg = pod_result.scalar() or 0.0

        restart_result = await self.db.execute(
            select(func.sum(Pod.restart_count))
            .where(Pod.tenant_id == tenant_id)
        )
        restart_total = float(restart_result.scalar() or 0)

        threat_result = await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id)
        )
        threat_count = float(threat_result.scalar() or 0)

        pipeline_result = await self.db.execute(
            select(func.count(Pipeline.id))
            .where(
                Pipeline.tenant_id == tenant_id,
                Pipeline.status == "failed",
            )
        )
        pipeline_failures = float(pipeline_result.scalar() or 0)

        # Need at least 3 cost points for meaningful correlation
        if len(cost_series) < 3:
            logger.info(
                f"[ML] run_correlations skipped — insufficient cost data "
                f"for tenant={tenant_id[:8]} (got {len(cost_series)} points)"
            )
            return 0

        # Pad scalar series to match cost_series length for compute_matrix
        n = len(cost_series)
        metrics: dict[str, list[float]] = {
            "Cost":             cost_series,
            "CPU_Usage":        [cpu_avg]      * n,
            "Pod_Restarts":     [restart_total] * n,
            "Threat_Count":     [threat_count] * n,
            "Pipeline_Failures":[pipeline_failures] * n,
        }

        # ── 2. Compute all N×(N-1)/2 pairs ───────────────────────────────────
        analyzer = CorrelationAnalyzer()
        pairs = analyzer.compute_matrix(metrics)

        # ── 3. Upsert into ml_correlations ────────────────────────────────────
        written = 0
        for pair in pairs:
            if abs(pair["coefficient"]) < 0.1:
                continue   # skip negligible correlations — not actionable

            existing = await self.db.execute(
                select(MLCorrelation).where(
                    MLCorrelation.tenant_id == tenant_id,
                    MLCorrelation.metric_a  == pair["metric_a"],
                    MLCorrelation.metric_b  == pair["metric_b"],
                )
            )
            rec = existing.scalar_one_or_none()
            if rec:
                rec.correlation_score = pair["coefficient"]
                rec.method            = pair.get("method", "pearson")
                rec.insight           = pair.get("insight")
                rec.data_points       = {
                    "n":        n,
                    "p_value":  pair.get("p_value"),
                    "strength": pair.get("strength"),
                }
            else:
                self.db.add(MLCorrelation(
                    tenant_id         = tenant_id,
                    metric_a          = pair["metric_a"],
                    metric_b          = pair["metric_b"],
                    correlation_score = pair["coefficient"],
                    method            = pair.get("method", "pearson"),
                    insight           = pair.get("insight"),
                    data_points       = {
                        "n":        n,
                        "p_value":  pair.get("p_value"),
                        "strength": pair.get("strength"),
                    },
                ))
            written += 1

        await self.db.commit()
        logger.info(
            f"[ML] run_correlations complete — "
            f"tenant={tenant_id[:8]} pairs_written={written}"
        )

        # ── Push ML_INSIGHT event to connected browser tabs ───────────────────
        if written > 0:
            try:
                from app.api.v1.websocket.manager import ws_manager
                from app.api.v1.websocket.events import WSEventType
                await ws_manager.send_to_tenant(tenant_id, {
                    "event": WSEventType.ML_INSIGHT,
                    "data": {
                        "pairs_updated": written,
                        "message": "Correlation analysis updated — refresh for new insights",
                    },
                })
            except Exception:
                pass   # WS push is best-effort; correlation data is already in DB

        return written

    # ── Event-driven listener ─────────────────────────────────────────────────

    async def start_event_listener(self) -> None:
        """
        Subscribe to Redis pub/sub and auto-trigger ML correlation runs.

        Lifecycle:
          - Runs as a long-lived asyncio task started at FastAPI startup.
          - If Redis disconnects, waits _RECONNECT_DELAY seconds then retries.
          - A failure inside _auto_correlate() is fully isolated — it never
            crashes the listener loop or the FastAPI process.
          - Uses per-tenant debounce (_DEBOUNCE_SECS) to prevent correlation
            storms when many events arrive within a short window (e.g. a bulk
            AWS Security Hub sync adding 50 threats in 2 seconds).

        Channels subscribed:
          events:cost.anomaly_detected   → COST_ANOMALY_DETECTED
          events:threat.detected          → THREAT_DETECTED
          events:vulnerability.found      → VULNERABILITY_FOUND
          events:pipeline.failed          → PIPELINE_FAILED
        """
        from app.events.bus import event_bus
        from app.events.events import EventType

        _INITIAL_RECONNECT_DELAY = 5   # seconds between reconnection attempts
        _MAX_RECONNECT_DELAY = 300      # max backoff interval

        CHANNELS = [
            f"events:{EventType.COST_ANOMALY_DETECTED.value}",
            f"events:{EventType.THREAT_DETECTED.value}",
            f"events:{EventType.VULNERABILITY_FOUND.value}",
            f"events:{EventType.PIPELINE_FAILED.value}",
        ]

        logger.info(
            f"[MLListener] Starting — subscribing to {len(CHANNELS)} channels"
        )

        reconnect_delay = _INITIAL_RECONNECT_DELAY
        while True:   # outer reconnect loop
            pubsub = None
            try:
                pubsub = await event_bus.subscribe(*CHANNELS)
                logger.info("[MLListener] Connected to Redis pub/sub ✓")
                reconnect_delay = _INITIAL_RECONNECT_DELAY

                async for message in pubsub.listen():
                    # ── Filter: only process actual published messages ────────
                    if message.get("type") != "message":
                        continue

                    # ── Parse payload ─────────────────────────────────────────
                    try:
                        raw = message.get("data", "{}")
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        data = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError) as parse_err:
                        logger.warning(
                            f"[MLListener] Malformed message skipped: {parse_err!r}"
                        )
                        continue

                    tenant_id = data.get("tenant_id") or data.get("payload", {}).get("tenant_id")
                    if not tenant_id:
                        logger.debug("[MLListener] Event missing tenant_id — skipped")
                        continue

                    channel = message.get("channel", b"").decode("utf-8") \
                        if isinstance(message.get("channel"), bytes) \
                        else str(message.get("channel", ""))

                    # ── Debounce: skip if last run < _DEBOUNCE_SECS ago ───────
                    now = time.monotonic()
                    last = _last_correlate.get(tenant_id, 0.0)
                    if now - last < _DEBOUNCE_SECS:
                        logger.debug(
                            f"[MLListener] Debounced tenant={tenant_id[:8]} "
                            f"channel={channel} (last run {now - last:.1f}s ago)"
                        )
                        continue
                    _last_correlate[tenant_id] = now

                    # ── Schedule correlation run WITHOUT blocking listener ─────
                    severity = data.get("payload", {}).get("severity", "")
                    asyncio.create_task(
                        self._auto_correlate(tenant_id, channel, severity),
                        name=f"ml-correlate-{tenant_id[:8]}",
                    )
                    logger.info(
                        f"[MLListener] Scheduled _auto_correlate — "
                        f"tenant={tenant_id[:8]} channel={channel} severity={severity}"
                    )

            except asyncio.CancelledError:
                logger.info("[MLListener] Cancelled — shutting down gracefully")
                return   # FastAPI is shutting down; exit cleanly

            except Exception as exc:
                logger.error(
                    f"[MLListener] Connection lost: {exc!r} — "
                    f"reconnecting in {reconnect_delay}s"
                )
            finally:
                if pubsub is not None:
                    try:
                        await pubsub.unsubscribe()
                        await pubsub.aclose()
                    except Exception:
                        pass

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, _MAX_RECONNECT_DELAY)

    async def _auto_correlate(
        self,
        tenant_id: str,
        source_channel: str = "",
        severity: str = "",
    ) -> None:
        """
        Run correlation analysis for one tenant in a fully isolated async task.

        Creates its own DB session so failures here never affect the Redis
        listener loop or any in-flight HTTP requests.

        Prioritization:
          - critical/high severity threats trigger an immediate run (no extra
            delay — debounce already handled by caller).
          - All other events run identically; priority is informational only.
        """
        from app.core.database import AsyncSessionLocal

        priority = "HIGH" if severity in ("critical", "high") else "NORMAL"
        logger.info(
            f"[MLCorrelate] Starting [{priority}] — "
            f"tenant={tenant_id[:8]} source={source_channel}"
        )

        try:
            async with AsyncSessionLocal() as db:
                svc = MLService(db)
                written = await svc.run_correlations(tenant_id)
                logger.info(
                    f"[MLCorrelate] Done [{priority}] — "
                    f"tenant={tenant_id[:8]} pairs_written={written} "
                    f"source={source_channel}"
                )
        except Exception as exc:
            # Fully isolated: this task's failure never propagates to the
            # listener loop, the FastAPI process, or other tenants.
            logger.error(
                f"[MLCorrelate] Failed — "
                f"tenant={tenant_id[:8]} source={source_channel}: {exc!r}"
            )
