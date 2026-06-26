from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.utils.logger import logger

class TimelineEnricher(IEnricher):
    """
    Tracks the lifecycle of the vulnerability from disclosure to enrichment.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[TimelineEnricher] Building timeline for {context.finding_id}")

        timeline = []

        if context.vulnerability:
            if context.vulnerability.published_at:
                timeline.append({
                    "event": "published",
                    "timestamp": context.vulnerability.published_at,
                    "description": "Vulnerability officially published"
                })

        if context.exploit:
            # Use a stub date if not available
            exploit_date = context.exploit.status.first_seen or datetime.utcnow()
            timeline.append({
                "event": "exploited",
                "timestamp": exploit_date,
                "description": "Exploit first observed in the wild"
            })

        timeline.append({
            "event": "enriched",
            "timestamp": datetime.utcnow(),
            "description": "Enriched by UniOps Intelligence Engine"
        })

        # Sort timeline by date
        timeline.sort(key=lambda x: x["timestamp"])
        context.timeline = timeline
