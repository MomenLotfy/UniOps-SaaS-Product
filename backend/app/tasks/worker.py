"""Celery worker entry point."""
from app.core.celery_app import celery_app
from app.utils.logger import logger

import app.tasks.sync_pipelines       # noqa
import app.tasks.sync_pods            # noqa
import app.tasks.sync_costs           # noqa
import app.tasks.sync_security        # noqa
import app.tasks.scan_vulnerabilities # noqa
import app.tasks.train_ml_models      # noqa
import app.tasks.generate_insights    # noqa
import app.tasks.send_alerts          # noqa
import app.tasks.cleanup_old_data     # noqa
import app.tasks.run_scan             # noqa — DevSecOps scan engine

logger.info("Celery worker initialized with all tasks registered")

__all__ = ["celery_app"]
