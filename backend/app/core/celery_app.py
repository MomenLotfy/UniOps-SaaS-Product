from __future__ import annotations
"""
Celery app — used in production with Redis.
In dev mode (no Redis), the BackgroundScheduler handles scheduling instead.
"""
from app.config import settings

try:
    from celery import Celery

    celery_app = Celery(
        "uniops",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "app.tasks.sync_pipelines",
            "app.tasks.sync_pods",
            "app.tasks.sync_costs",
            "app.tasks.sync_security",
            "app.tasks.scan_vulnerabilities",
            "app.tasks.train_ml_models",
            "app.tasks.generate_insights",
            "app.tasks.send_alerts",
            "app.tasks.cleanup_old_data",
            "app.tasks.run_scan",
        ],
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_default_queue="scans",
        # Beat schedule — used when running: celery -A app.tasks.worker beat
        beat_schedule={
            "sync-pods-every-2min": {
                "task": "app.tasks.sync_pods.sync_all_pods",
                "schedule": 120.0,
            },
            "sync-pipelines-every-5min": {
                "task": "app.tasks.sync_pipelines.sync_all_pipelines",
                "schedule": 300.0,
            },
            "sync-aws-costs-every-hour": {
                "task": "app.tasks.sync_costs.sync_cloud_costs",
                "schedule": 3600.0,
            },
            "sync-aws-security-every-hour": {
                "task": "app.tasks.sync_security.sync_aws_security",
                "schedule": 3600.0,
            },
            "scan-vulnerabilities-every-6h": {
                "task": "app.tasks.scan_vulnerabilities.run_full_scan",
                "schedule": 21600.0,
            },
            "cleanup-daily": {
                "task": "app.tasks.cleanup_old_data.cleanup",
                "schedule": 86400.0,
            },
            # ── ML Continuous Learning Pipeline ───────────────────────────────
            #
            # WHY THESE ARE REQUIRED
            # ──────────────────────
            # ML models trained on historical data degrade silently as
            # infrastructure patterns evolve.  A RandomForestRegressor trained
            # on April cost data will produce increasingly inaccurate forecasts
            # by June without retraining — the model has never "seen" the new
            # usage patterns.  Similarly, correlation weights computed from
            # last month's metrics stop reflecting current cross-domain
            # relationships.  Neither degradation produces an error; the UI
            # simply shows confidently wrong predictions.
            #
            # SCHEDULE REASONING
            # ──────────────────
            # 7 days for retrain: ML models need enough new data since the
            # last run to justify the CPU cost of RandomForest/GradientBoost
            # training.  Daily retraining on small delta data is wasteful and
            # produces unstable weight drift.  Weekly is the industry standard
            # for operational ML models with daily data ingestion.
            #
            # 24 hours for insights: Correlation analysis is cheap (scipy
            # pearsonr on < 1000 points).  Running it daily ensures that the
            # dashboard reflects last night's cost/security/performance data
            # even if no operational events fired during a quiet day.
            #
            # CELERY BEAT SAFETY
            # ──────────────────
            # Both tasks are idempotent: re-running them does not duplicate
            # records — they upsert (update-or-insert) existing rows.
            # If a run fails, the next scheduled run will pick up where the
            # last succeeded.  No manual intervention is needed.
            "retrain-ml-models-weekly": {
                "task":     "app.tasks.train_ml_models.retrain_all",
                "schedule": 604_800.0,   # 7 days = 7 × 24 × 60 × 60
                "kwargs":   {"force": False},   # skip if not enough new data
            },
            "generate-ml-insights-daily": {
                "task":     "app.tasks.generate_insights.run_for_all_tenants",
                "schedule": 86_400.0,    # 24 hours — same cadence as cleanup
            },
        },
    )

except ImportError:
    celery_app = None  # type: ignore
