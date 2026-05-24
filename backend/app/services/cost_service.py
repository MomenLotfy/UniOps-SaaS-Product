from __future__ import annotations
"""Cost service — manages cloud cost metrics, anomalies, and savings opportunities."""
import calendar
from datetime import datetime, date, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_metric import CostMetric
from app.models.cost_anomaly import CostAnomaly
from app.models.savings import Savings
from app.schemas.cost import (
    CostMetricResponse, CostAnomalyResponse,
    SavingsResponse, SavingActionResult,
)
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundError, IntegrationError, ValidationError
from app.services.base import BaseService
from app.utils.logger import logger


class CostService(BaseService):
    # ─────────────────────────────────────────────────────────────────────────
    # Metrics list
    # ─────────────────────────────────────────────────────────────────────────
    async def list_metrics(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        provider: Optional[str] = None,
        service: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PaginatedResponse:
        query = select(CostMetric).where(CostMetric.tenant_id == tenant_id)
        if provider:
            query = query.where(CostMetric.provider == provider)
        if service:
            query = query.where(CostMetric.service.ilike(f"%{service}%"))
        if start_date:
            query = query.where(CostMetric.period_start >= start_date)
        if end_date:
            query = query.where(CostMetric.period_end <= end_date)

        total = await self._count(query)
        query = query.order_by(CostMetric.period_start.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[CostMetricResponse.model_validate(i) for i in items],
            total=total, page=page, page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Summary — FIX: returns all fields frontend expects
    # ─────────────────────────────────────────────────────────────────────────
    async def get_summary(self, tenant_id: str) -> dict:
        """
        Returns a unified summary dict that satisfies BOTH:
          - Legacy fields:  total_cost, mtd_cost, forecast_eom, trend_pct, by_provider
          - Frontend fields: mtd, projected, daily_avg, ytd, connected
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        current_month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        # Safe prev month
        if today.month == 1:
            prev_month_start = date(today.year - 1, 12, 1)
        else:
            prev_month_start = date(today.year, today.month - 1, 1)

        days_elapsed = max(today.day, 1)
        days_in_month = calendar.monthrange(today.year, today.month)[1]

        # ── Single query approach using CASE WHEN ────────────────────────────
        result = await self.db.execute(
            select(
                # MTD
                func.sum(
                    CostMetric.amount
                ).filter(CostMetric.period_start >= current_month_start).label("mtd"),
                # Prev month
                func.sum(
                    CostMetric.amount
                ).filter(
                    CostMetric.period_start >= prev_month_start,
                    CostMetric.period_start < current_month_start,
                ).label("prev_month"),
                # YTD
                func.sum(
                    CostMetric.amount
                ).filter(CostMetric.period_start >= year_start).label("ytd"),
                # All time
                func.sum(CostMetric.amount).label("total"),
            )
            .where(CostMetric.tenant_id == tenant_id)
        )
        row = result.fetchone()

        mtd        = float(row.mtd        or 0)
        prev_month = float(row.prev_month or 0)
        ytd        = float(row.ytd        or 0)
        total_all  = float(row.total      or 0)

        daily_avg  = mtd / days_elapsed
        projected  = daily_avg * days_in_month

        trend_pct = 0.0
        if prev_month > 0:
            trend_pct = ((mtd - prev_month) / prev_month) * 100

        # By provider
        prov_rows = await self.db.execute(
            select(CostMetric.provider, func.sum(CostMetric.amount))
            .where(CostMetric.tenant_id == tenant_id)
            .group_by(CostMetric.provider)
        )
        by_provider = {
            r[0]: round(float(r[1]), 2)
            for r in prov_rows.fetchall() if r[0]
        }

        # Connected check — is there an active AWS integration?
        from app.models.integration import Integration
        count = (await self.db.execute(
            select(func.count()).select_from(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.type      == "aws",
                Integration.is_active == True,
                Integration.status    == "connected",
            )
        )).scalar() or 0
        has_aws = count > 0

        return {
            # ── Legacy fields (kept for backwards compat) ─────────────────
            "total_cost":   round(total_all, 2),
            "mtd_cost":     round(mtd, 2),
            "forecast_eom": round(projected, 2),
            "trend_pct":    round(trend_pct, 1),
            "by_provider":  by_provider,
            "by_service":   {},
            "by_region":    {},
            # ── Frontend-expected fields ──────────────────────────────────
            "mtd":          round(mtd, 2),
            "projected":    round(projected, 2),
            "daily_avg":    round(daily_avg, 4),
            "ytd":          round(ytd, 2),
            "connected":    has_aws,
            "prev_month":   round(prev_month, 2),
            "trend_pct":    round(trend_pct, 1),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Anomalies
    # ─────────────────────────────────────────────────────────────────────────
    async def list_anomalies(
        self, tenant_id: str, status: Optional[str] = None, severity: Optional[str] = None
    ) -> list[dict]:
        query = select(CostAnomaly).where(CostAnomaly.tenant_id == tenant_id)
        if status:
            query = query.where(CostAnomaly.status == status)
        if severity:
            query = query.where(CostAnomaly.severity == severity)
        query = query.order_by(CostAnomaly.detected_date.desc())
        result = await self.db.execute(query)
        rows = result.scalars().all()

        # Build dicts matching frontend expectations
        return [self._anomaly_to_dict(a) for a in rows]

    @staticmethod
    def _anomaly_to_dict(a: CostAnomaly) -> dict:
        return {
            "id":               a.id,
            "tenant_id":        a.tenant_id,
            "service":          a.service,
            "severity":         a.severity,
            "status":           a.status,
            "description":      a.description,
            "expected_amount":  a.expected_cost,
            "actual_amount":    a.actual_cost,
            "deviation_pct":    round(a.deviation, 1) if a.deviation else 0,
            "detected_date":    a.detected_date.isoformat() if a.detected_date else None,
            "root_cause":       getattr(a, "root_cause", None),
            "recommendation":   getattr(a, "recommendation", None),
            "created_at":       a.created_at.isoformat() if a.created_at else None,
        }

    async def update_anomaly_status(
        self,
        anomaly_id: str,
        tenant_id: str,
        new_status: str,
    ) -> dict:
        result = await self.db.execute(
            select(CostAnomaly).where(
                CostAnomaly.id        == anomaly_id,
                CostAnomaly.tenant_id == tenant_id,  # ← tenant isolation
            )
        )
        anomaly = result.scalar_one_or_none()
        if not anomaly:
            raise NotFoundError("Anomaly not found")

        allowed_transitions = {
            "open":          ["investigating", "resolved", "dismissed"],
            "investigating": ["resolved", "dismissed"],
            "resolved":      [],
            "dismissed":     [],
        }
        current = anomaly.status or "open"
        if new_status not in allowed_transitions.get(current, []):
            raise ValidationError(
                f"Cannot transition anomaly from '{current}' to '{new_status}'",
                field="status",
            )

        anomaly.status = new_status
        await self.db.flush()
        return self._anomaly_to_dict(anomaly)

    # ─────────────────────────────────────────────────────────────────────────
    # Savings
    # ─────────────────────────────────────────────────────────────────────────
    async def list_savings(
        self, tenant_id: str, status: Optional[str] = None, provider: Optional[str] = None
    ) -> list[SavingsResponse]:
        query = select(Savings).where(Savings.tenant_id == tenant_id)
        if status:
            query = query.where(Savings.status == status)
        if provider:
            query = query.where(Savings.provider == provider)
        query = query.order_by(Savings.potential_savings.desc())
        result = await self.db.execute(query)
        return [SavingsResponse.model_validate(i) for i in result.scalars().all()]

    async def dismiss_saving(self, saving_id: str, tenant_id: str, dismissed_by: str) -> SavingsResponse:
        saving = await self._get_saving_for_tenant(saving_id, tenant_id)
        if saving.status == "applied":
            raise ValidationError("Cannot dismiss an already-applied saving", field="status")
        saving.status = "dismissed"
        saving.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self._write_audit(
            tenant_id=tenant_id, user_id=dismissed_by,
            action="saving.dismiss", resource="saving", resource_id=saving_id,
            details={"title": saving.title, "category": saving.category},
        )
        return SavingsResponse.model_validate(saving)

    async def get_total_savings_opportunity(self, tenant_id: str) -> dict:
        result = await self.db.execute(
            select(func.sum(Savings.potential_savings)).where(
                Savings.tenant_id == tenant_id,
                Savings.status.in_(["open", "pending"]),
            )
        )
        total = float(result.scalar() or 0)
        return {"total_potential_savings": round(total, 2), "currency": "USD"}

    # ─────────────────────────────────────────────────────────────────────────
    # apply_saving — with tenant isolation + real AWS execution
    # ─────────────────────────────────────────────────────────────────────────
    async def apply_saving(self, saving_id: str, tenant_id: str, applied_by: str) -> SavingActionResult:
        """
        Apply a cost-saving recommendation.

        Security: tenant_id is always checked against the saving record
        so a user from tenant A cannot apply a saving belonging to tenant B.
        """
        saving = await self._get_saving_for_tenant(saving_id, tenant_id)

        if saving.status in ("applied", "dismissed"):
            raise ValidationError(
                f"Saving is already '{saving.status}' — cannot apply again",
                field="status",
            )

        category   = (saving.category or "").lower()
        resource   = saving.resource or ""
        aws_result = None

        integration = await self._find_aws_integration(tenant_id)
        if not integration:
            logger.warning(
                f"No active AWS integration for tenant {tenant_id} — "
                "applying saving in DB only"
            )
        else:
            creds  = {k: self._safe_decrypt(v) for k, v in (integration.credentials or {}).items()}
            config = {**creds, **(integration.config or {})}
            region = config.get("region", "us-east-1")

            from app.integrations.aws.cost_explorer import CostExplorer
            ce = CostExplorer(config)

            if category == "rightsizing":
                recommended_type = self._parse_recommended_type(saving)
                aws_result = await ce.apply_rightsizing(resource, recommended_type, region)
            elif category == "s3_lifecycle":
                bucket = resource.split(":::")[-1].split("/")[0]
                aws_result = await ce.apply_s3_lifecycle(bucket)
            elif category == "reserved_instance":
                offering_id = (getattr(saving, "metadata_", None) or {}).get("offering_id") or resource
                instance_count = (getattr(saving, "metadata_", None) or {}).get("instance_count", 1)
                aws_result = await ce.purchase_reserved_instance(offering_id, instance_count, region)
            elif category in ("stop_instance", "underutilized"):
                aws_result = await ce.stop_unused_instance(resource, region)
            else:
                logger.warning(f"Unknown saving category '{category}' — DB-only apply")

        if aws_result and not aws_result.get("success"):
            raise IntegrationError("AWS", aws_result.get("error", "AWS action failed"))

        saving.status     = "applied"
        saving.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        aws_action = self._describe_aws_action(category, resource, saving)
        await self._write_audit(
            tenant_id=tenant_id, user_id=applied_by,
            action="saving.apply", resource="saving", resource_id=saving_id,
            details={
                "title":       saving.title,
                "category":    category,
                "provider":    saving.provider,
                "resource":    resource,
                "savings_usd": saving.potential_savings,
                "aws_action":  aws_action,
                "aws_synced":  aws_result is not None and aws_result.get("success"),
            },
        )
        return SavingActionResult(
            success    = True,
            saving_id  = saving_id,
            category   = category,
            aws_action = aws_action,
            resource   = resource,
            message    = (
                f"Saving applied: {aws_action}"
                if aws_result
                else "Marked as applied (no AWS integration connected)"
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────
    async def _get_saving_for_tenant(self, saving_id: str, tenant_id: str) -> Savings:
        """Fetch saving with MANDATORY tenant isolation — raises 404 on mismatch."""
        result = await self.db.execute(
            select(Savings).where(
                Savings.id        == saving_id,
                Savings.tenant_id == tenant_id,   # ← security: always enforce
            )
        )
        saving = result.scalar_one_or_none()
        if not saving:
            # Return 404 regardless — don't reveal existence to wrong tenant
            raise NotFoundError("Saving not found")
        return saving

    def _parse_recommended_type(self, saving: Savings) -> str:
        meta = getattr(saving, "metadata_", None) or {}
        if meta.get("recommended_type"):
            return meta["recommended_type"]
        import re
        rec = saving.recommendation or saving.title or ""
        match = re.search(r"\b([a-z]\d+[a-z]*\.[a-z0-9]+)\b", rec)
        return match.group(1) if match else "t3.medium"

    @staticmethod
    def _describe_aws_action(category: str, resource: str, saving: Savings) -> str:
        category = (category or "").lower()
        short = resource.split("/")[-1][:30] if resource else "—"
        if category == "rightsizing":
            return f"EC2 instance {short} resized to recommended type"
        if category == "s3_lifecycle":
            return f"S3 lifecycle policy applied to bucket {short}"
        if category == "reserved_instance":
            return f"Reserved Instance purchased for {short}"
        if category in ("stop_instance", "underutilized"):
            return f"EC2 instance {short} stopped"
        return f"Saving marked as applied (category: {category})"

    async def _find_aws_integration(self, tenant_id: str):
        from app.models.integration import Integration
        result = await self.db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.type      == "aws",
                Integration.is_active == True,
                Integration.status    == "connected",
            ).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _safe_decrypt(value: str) -> str:
        try:
            from app.utils.encryption import decrypt
            return decrypt(value)
        except Exception:
            return value

    async def _write_audit(
        self, tenant_id: str, user_id: str, action: str,
        resource: str, resource_id: str, details: dict, status: str = "success",
    ) -> None:
        try:
            from app.models.audit_log import AuditLog
            self.db.add(AuditLog(
                tenant_id=tenant_id, user_id=user_id, action=action,
                resource=resource, resource_id=resource_id,
                details=details, status=status,
            ))
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Audit log write failed (non-fatal): {e}")
