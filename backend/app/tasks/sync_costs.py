from __future__ import annotations
"""Sync cloud costs from AWS — works both as Celery task and direct async call."""

import asyncio
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import select
from app.utils.logger import logger


# ── Celery task ───────────────────────────────────────────────────────────────
try:
    from app.core.celery_app import celery_app

    @celery_app.task(
        name="app.tasks.sync_costs.sync_cloud_costs",
        bind=True,
        max_retries=3,
        default_retry_delay=300,
        soft_time_limit=600,
    )
    def sync_cloud_costs(self):
        try:
            asyncio.run(sync_aws_costs_async())
            logger.info("Cost sync completed")
        except Exception as exc:
            logger.error(f"Cost sync failed: {exc}")
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

except Exception:
    pass  # Celery not available in dev mode


# ── Core async function ───────────────────────────────────────────────────────
async def sync_aws_costs_async(tenant_id: str | None = None) -> dict:
    """
    Sync real AWS costs into the database.
    """

    from app.core.database import AsyncSessionLocal
    from app.models.integration import Integration
    from app.models.cost_metric import CostMetric
    from app.models.cost_anomaly import CostAnomaly
    from app.models.savings import Savings
    from app.utils.encryption import decrypt

    summary = {
        "integrations": 0,
        "cost_records": 0,
        "anomalies": 0,
        "savings": 0
    }

    async with AsyncSessionLocal() as db:
        # Include both "connected" (verified) and "sync_failed" (credentials OK but
        # last sync hit a permissions or rate-limit error) so that retrying a sync
        # attempt doesn't require the user to disconnect and reconnect.
        # "credentials_invalid" is excluded — we never have valid creds to attempt a sync.
        from sqlalchemy import or_
        query = select(Integration).where(
            Integration.is_active == True,
            Integration.type == "aws",
            or_(
                Integration.status == "connected",
                Integration.status == "sync_failed",
            ),
        )

        if tenant_id:
            query = query.where(Integration.tenant_id == tenant_id)

        result = await db.execute(query)
        integrations = result.scalars().all()

        logger.info(
            f"[finops_data_load_attempt] "
            f"tenant={tenant_id[:8] if tenant_id else 'all'} "
            f"integrations_found={len(integrations)}"
        )

        for integration in integrations:
            try:
                logger.info(
                    f"[sync_started] integration={integration.name} "
                    f"id={integration.id[:8]} tenant={integration.tenant_id[:8]} "
                    f"prior_status={integration.status}"
                )
                creds = _decrypt_creds(integration.credentials)
                config = {**creds, **integration.config}

                from app.integrations.aws.cost_explorer import CostExplorer

                explorer = CostExplorer(config)

                # ── 1. Costs ─────────────────────────────────────────────
                logger.info(
                    f"[aws_cost_api_call] Calling ce:GetCostAndUsage "
                    f"integration={integration.name} id={integration.id[:8]}"
                )
                cost_items = await explorer.get_costs_by_service(months=3)
                logger.info(
                    f"[aws_cost_api_response] integration={integration.name} "
                    f"line_items_returned={len(cost_items)}"
                )

                inserted_costs = 0
                for item in cost_items:
                    await _upsert_cost_metric(db, integration, item)
                    summary["cost_records"] += 1
                    inserted_costs += 1

                logger.info(
                    f"[db_insert_count] cost_metrics upserted={inserted_costs} "
                    f"integration={integration.name} id={integration.id[:8]}"
                )

                # ── 2. Anomalies ─────────────────────────────────────────
                anomaly_items = await explorer.get_cost_anomalies()
                for item in anomaly_items:
                    await _upsert_anomaly(db, integration, item)
                    summary["anomalies"] += 1

                # ── 3. Savings ───────────────────────────────────────────
                rightsizing = await explorer.get_rightsizing_recommendations()
                ri_recs = []
                if hasattr(explorer, "get_reserved_instance_recommendations"):
                    ri_recs = await explorer.get_reserved_instance_recommendations()

                for r in rightsizing:
                    if r.get("monthly_savings", 0) > 0:
                        await _upsert_saving(db, integration, {
                            "title": f"Rightsize {r['current_type']} → {r['recommended_type']}",
                            "description": f"EC2 instance {r['resource_id']} can be rightsized",
                            "category": "Compute",
                            "potential_savings": r["monthly_savings"],
                            "effort": "low",
                            "resource": r["resource_id"],
                            "recommendation": (
                                f"Change instance type from {r['current_type']} "
                                f"to {r['recommended_type']}"
                            ),
                        })
                        summary["savings"] += 1

                for r in ri_recs:
                    if r.get("monthly_savings", 0) > 0:
                        await _upsert_saving(db, integration, {
                            "title": f"Reserved Instance: {r['instance_type']} in {r['region']}",
                            "description": "Switch to Reserved Instance for 1-year commitment",
                            "category": "Compute",
                            "potential_savings": r["monthly_savings"],
                            "effort": "low",
                            "resource": f"{r['instance_type']}/{r['region']}",
                            "recommendation": "Purchase 1-year No Upfront Reserved Instance",
                        })
                        summary["savings"] += 1

                integration.last_sync = datetime.now(timezone.utc)
                # Update status to "connected" after a successful sync
                # (it may have been "sync_failed" from a previous attempt)
                integration.status = "connected"
                integration.error_message = None
                await db.commit()

                logger.info(
                    f"[sync_costs_complete] ✓ integration={integration.name} "
                    f"id={integration.id[:8]} tenant={integration.tenant_id[:8]} "
                    f"cost_records={inserted_costs} "
                    f"anomalies={len(anomaly_items)} "
                    f"savings_recs={len(rightsizing) + len(ri_recs)}"
                )

                # Invalidate Redis cost cache so next API call returns fresh data
                try:
                    from app.core.cache import cost_cache_invalidate
                    await cost_cache_invalidate(integration.tenant_id)
                    logger.info(
                        f"[cache_invalidated] tenant={integration.tenant_id[:8]}"
                    )
                except Exception as cache_exc:
                    logger.debug(f"[sync_costs] Cache invalidation skipped: {cache_exc}")

                summary["integrations"] += 1
                logger.info(f"[sync_costs_summary] {summary}")

            except Exception as e:
                err_msg = str(e)[:400]
                logger.error(
                    f"[sync_failed_reason] integration={integration.name} "
                    f"id={integration.id[:8]} tenant={integration.tenant_id[:8]} "
                    f"error={err_msg}"
                )
                # Mark as sync_failed — NOT credentials_invalid.
                # The integration stays "configured" so the UI shows it and
                # allows the user to retry without having to re-enter credentials.
                try:
                    integration.status = "sync_failed"
                    integration.error_message = f"Last sync failed: {err_msg[:200]}"
                    await db.commit()
                except Exception:
                    await db.rollback()

    return summary


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _upsert_cost_metric(db, integration, item: dict):
    from app.models.cost_metric import CostMetric

    try:
        period_start = date.fromisoformat(item["period"][:10])
        if period_start.month == 12:
            period_end = date(period_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(period_start.year, period_start.month + 1, 1) - timedelta(days=1)
    except Exception:
        return

    existing = await db.execute(
        select(CostMetric).where(
            CostMetric.tenant_id == integration.tenant_id,
            CostMetric.integration_id == integration.id,
            CostMetric.period_start == period_start,
            CostMetric.service == item.get("service", "total"),
            CostMetric.provider == "aws",
        )
    )

    metric = existing.scalar_one_or_none()

    if metric:
        metric.amount = item["amount"]
        metric.updated_at = datetime.now(timezone.utc)
    else:
        db.add(CostMetric(
            tenant_id=integration.tenant_id,
            integration_id=integration.id,
            provider="aws",
            service=item.get("service", "total"),
            region=item.get("region", ""),
            amount=item["amount"],
            currency=item.get("unit", "USD"),
            period_start=period_start,
            period_end=period_end,
        ))


async def _upsert_anomaly(db, integration, item: dict):
    from app.models.cost_anomaly import CostAnomaly

    try:
        detected = date.fromisoformat(item["start_date"][:10])
    except Exception:
        detected = date.today()

    anomaly = CostAnomaly(
        tenant_id=integration.tenant_id,
        service=item.get("service", "Unknown"),
        description=f"AWS anomaly {item.get('anomaly_id', '')}",
        expected_cost=item.get("expected", 0),
        actual_cost=item.get("actual", 0),
        deviation=round(
            ((item.get("actual", 0) - item.get("expected", 1))
             / max(item.get("expected", 1), 0.01)) * 100,
            1,
        ),
        severity=item.get("severity", "medium"),
        status=item.get("status", "open"),
        detected_date=detected,
    )

    db.add(anomaly)
    await db.flush()


async def _upsert_saving(db, integration, item: dict):
    from app.models.savings import Savings

    existing = await db.execute(
        select(Savings).where(
            Savings.tenant_id == integration.tenant_id,
            Savings.title == item["title"],
            Savings.status == "open",
        )
    )

    if existing.scalar_one_or_none():
        return

    db.add(Savings(
        tenant_id=integration.tenant_id,
        title=item["title"],
        description=item.get("description", ""),
        category=item.get("category", "Compute"),
        provider="aws",
        potential_savings=item.get("potential_savings", 0),
        effort=item.get("effort", "low"),
        status="open",
        resource=item.get("resource"),
        recommendation=item.get("recommendation"),
    ))


def _decrypt_creds(credentials: dict) -> dict:
    from app.utils.encryption import decrypt

    result = {}
    # Must match IntegrationService.SENSITIVE_FIELDS so encrypted-at-rest
    # values are properly decrypted before being passed to boto3.
    SENSITIVE = {
        "access_key", "access_key_id",        # AWS key ID variants
        "secret_key", "secret_access_key",     # AWS secret variants
        "token", "access_token",
        "password", "private_key",
        "api_key", "webhook_secret", "client_secret",
    }

    for k, v in (credentials or {}).items():
        if k in SENSITIVE and v:
            try:
                result[k] = decrypt(str(v))
            except Exception:
                result[k] = v  # pass through if already plaintext
        else:
            result[k] = v

    # Normalise key names so boto3 always gets access_key_id / secret_access_key
    if "access_key" in result and "access_key_id" not in result:
        result["access_key_id"] = result.pop("access_key")
    if "secret_key" in result and "secret_access_key" not in result:
        result["secret_access_key"] = result.pop("secret_key")

    return result
