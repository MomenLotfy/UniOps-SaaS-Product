"""Celery task — generates ML-driven insights and stores recommendations."""
import asyncio
from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.utils.logger import logger


@celery_app.task(
    name="app.tasks.generate_insights.generate_all_insights",
    bind=True,
    max_retries=2,
    soft_time_limit=600,
)
def generate_all_insights(self):
    """Generate ML insights for all active tenants."""
    try:
        asyncio.run(_generate_insights())
        logger.info("Insight generation completed")
    except Exception as exc:
        logger.error(f"Insight generation failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


async def _generate_insights():
    from app.core.database import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.ml_recommendation import MLRecommendation
    from app.models.cost_metric import CostMetric
    from app.models.vulnerability import Vulnerability
    from app.models.threat import Threat
    from app.models.pipeline import Pipeline
    from app.models.pod import Pod
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        tenants_r = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = tenants_r.scalars().all()

        for tenant in tenants:
            try:
                cost_r = await db.execute(
                    select(func.sum(CostMetric.amount), CostMetric.service)
                    .where(CostMetric.tenant_id == tenant.id)
                    .group_by(CostMetric.service)
                )
                cost_by_service = {row[1]: float(row[0]) for row in cost_r.fetchall() if row[1]}
                total_cost = sum(cost_by_service.values())

                critical_vulns = await db.execute(
                    select(func.count(Vulnerability.id)).where(
                        Vulnerability.tenant_id == tenant.id,
                        Vulnerability.severity == "critical",
                        Vulnerability.status == "open",
                    )
                )

                open_threats = await db.execute(
                    select(func.count(Threat.id)).where(
                        Threat.tenant_id == tenant.id, Threat.status == "open"
                    )
                )

                pipeline_stats = await db.execute(
                    select(Pipeline.status, func.count(Pipeline.id))
                    .where(Pipeline.tenant_id == tenant.id)
                    .group_by(Pipeline.status)
                )
                pipeline_counts = {row[0]: row[1] for row in pipeline_stats.fetchall()}
                total_pipelines = sum(pipeline_counts.values())
                success = pipeline_counts.get("success", 0) + pipeline_counts.get("passed", 0)
                success_rate = success / total_pipelines if total_pipelines > 0 else 1.0

                high_restart_pods = await db.execute(
                    select(func.count(Pod.id)).where(
                        Pod.tenant_id == tenant.id, Pod.restart_count >= 5
                    )
                )

                from app.ml.recommendation_engine import RecommendationEngine
                engine = RecommendationEngine()

                context = {
                    "cost": {"total_cost": total_cost, "by_service": cost_by_service, "trend_pct": 0},
                    "security": {
                        "critical_vulnerabilities": critical_vulns.scalar() or 0,
                        "open_threats": open_threats.scalar() or 0,
                    },
                    "devops": {
                        "pipeline_success_rate": success_rate,
                        "high_restart_pods": high_restart_pods.scalar() or 0,
                    },
                }

                recommendations = engine.generate_all(context)

                existing_r = await db.execute(
                    select(MLRecommendation).where(
                        MLRecommendation.tenant_id == tenant.id,
                        MLRecommendation.status == "pending",
                    )
                )
                existing_titles = {r.title for r in existing_r.scalars().all()}

                for rec in recommendations:
                    if rec["title"] not in existing_titles:
                        db.add(MLRecommendation(
                            tenant_id=tenant.id,
                            title=rec["title"],
                            description=rec.get("description"),
                            category=rec.get("category"),
                            priority=rec.get("priority", 5),
                            confidence=rec.get("confidence", 0.7),
                            impact=rec.get("impact", "medium"),
                            effort=rec.get("effort", "medium"),
                            action=rec.get("action"),
                            status="pending",
                        ))

                await db.commit()
                logger.info(f"Generated {len(recommendations)} insights for tenant {tenant.id}")
            except Exception as e:
                logger.error(f"Insight generation failed for tenant {tenant.id}: {e}")
                await db.rollback()
