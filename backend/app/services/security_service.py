from __future__ import annotations
"""Security service — threats, vulnerabilities, compliance, and real AWS remediation."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.compliance import Compliance
from app.models.integration import Integration
from app.models.audit_log import AuditLog
from app.schemas.threat import ThreatResponse, ThreatStats, ThreatUpdate, ThreatActionResult
from app.schemas.vulnerability import VulnerabilityResponse, VulnerabilityStats, VulnerabilityUpdate
from app.core.exceptions import NotFoundError, IntegrationError, ValidationError
from app.services.base import BaseService
from app.utils.logger import logger

# Statuses that are already closed — no point resolving again
_CLOSED = {"resolved", "suppressed", "closed"}


class SecurityService(BaseService):

    # ── Threats ───────────────────────────────────────────────────────────────

    async def list_threats(
        self, tenant_id: str, page: int = 1, page_size: int = 20,
        severity: Optional[str] = None, status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> dict:
        query = select(Threat).where(Threat.tenant_id == tenant_id)
        if severity: query = query.where(Threat.severity == severity)
        if status:   query = query.where(Threat.status == status)
        if category: query = query.where(Threat.category == category)
        total = await self._count(query)
        items = await self._paginate(query.order_by(Threat.created_at.desc()), page, page_size)
        return {
            "data": [ThreatResponse.model_validate(t) for t in items],
            "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def get_threat(self, threat_id: str) -> ThreatResponse:
        threat = await self._get_by_id(Threat, threat_id)
        return ThreatResponse.model_validate(threat)

    async def update_threat(self, threat_id: str, data: ThreatUpdate) -> ThreatResponse:
        threat = await self._get_by_id(Threat, threat_id)
        if data.status:
            threat.status = data.status
            if data.status == "resolved":
                threat.resolved_at = datetime.now(timezone.utc)
        if data.description:
            threat.description = data.description
        await self.db.flush()
        return ThreatResponse.model_validate(threat)

    async def resolve_threat(
        self,
        threat_id: str,
        resolved_by: str,
        note: str = "Resolved via UniOps Security Center",
    ) -> ThreatActionResult:
        """
        Resolve a threat both in UniOps DB and back in AWS Security Hub.

        Flow:
          1. Load threat — guard if already closed
          2. Find the AWS integration for this tenant
          3. Call SecurityHub.resolve_finding(finding_id) → AWS API
          4. Update threat.status = 'resolved' + resolved_at in DB
          5. Write AuditLog
        """
        threat = await self._get_by_id(Threat, threat_id)

        if threat.status in _CLOSED:
            raise ValidationError(
                f"Threat is already '{threat.status}' — cannot resolve again",
                field="status",
            )

        # Extract the AWS finding ID stored during sync
        finding_id = (threat.raw_data or {}).get("finding_id")
        aws_processed = None

        if finding_id and threat.source == "aws_security_hub":
            # Find the AWS integration for this tenant
            integration = await self._find_aws_integration(threat.tenant_id)
            if integration:
                from app.utils.encryption import decrypt
                creds = {k: self._safe_decrypt(v) for k, v in (integration.credentials or {}).items()}
                config = {**creds, **(integration.config or {})}

                from app.integrations.aws.security_hub import SecurityHub
                hub = SecurityHub(config)
                result = await hub.resolve_finding(finding_id, note=note)

                if not result["success"]:
                    raise IntegrationError(
                        "AWS Security Hub",
                        result.get("error", "resolve_finding failed"),
                    )
                aws_processed = result.get("processed", 0)
                logger.info(f"AWS SecurityHub finding resolved: {finding_id[:50]}...")
            else:
                logger.warning(
                    f"No active AWS integration found for tenant {threat.tenant_id} — "
                    "resolving in DB only"
                )

        # Update DB
        threat.status      = "resolved"
        threat.resolved_at = datetime.now(timezone.utc)
        threat.updated_at  = datetime.now(timezone.utc)
        await self.db.flush()

        await self._write_audit(
            tenant_id  = threat.tenant_id,
            user_id    = resolved_by,
            action     = "threat.resolve",
            resource   = "threat",
            resource_id= threat_id,
            details    = {
                "title":      threat.title,
                "severity":   threat.severity,
                "source":     threat.source,
                "finding_id": finding_id,
                "note":       note,
                "aws_synced": aws_processed is not None,
            },
        )

        return ThreatActionResult(
            success      = True,
            action       = "resolve",
            threat_id    = threat_id,
            finding_id   = finding_id,
            aws_processed= aws_processed,
            message      = (
                f"Threat resolved"
                + (f" and updated in AWS Security Hub ({aws_processed} finding(s))" if aws_processed else " (DB only — no AWS integration)")
            ),
        )

    async def suppress_threat(
        self,
        threat_id: str,
        suppressed_by: str,
        reason: str = "TOLERATED",
    ) -> ThreatActionResult:
        """
        Suppress a threat — marks as false positive or accepted risk.
        In AWS Security Hub: WorkflowStatus = SUPPRESSED.
        """
        threat = await self._get_by_id(Threat, threat_id)

        if threat.status in _CLOSED:
            raise ValidationError(f"Threat is already '{threat.status}'", field="status")

        finding_id    = (threat.raw_data or {}).get("finding_id")
        aws_processed = None

        if finding_id and threat.source == "aws_security_hub":
            integration = await self._find_aws_integration(threat.tenant_id)
            if integration:
                from app.utils.encryption import decrypt
                creds  = {k: self._safe_decrypt(v) for k, v in (integration.credentials or {}).items()}
                config = {**creds, **(integration.config or {})}
                from app.integrations.aws.security_hub import SecurityHub
                result = await SecurityHub(config).suppress_finding(finding_id, reason=reason)
                if not result["success"]:
                    raise IntegrationError("AWS Security Hub", result.get("error", "suppress failed"))
                aws_processed = result.get("processed", 0)

        threat.status      = "suppressed"
        threat.resolved_at = datetime.now(timezone.utc)
        threat.updated_at  = datetime.now(timezone.utc)
        await self.db.flush()

        await self._write_audit(
            tenant_id  = threat.tenant_id,
            user_id    = suppressed_by,
            action     = "threat.suppress",
            resource   = "threat",
            resource_id= threat_id,
            details    = {"title": threat.title, "reason": reason, "finding_id": finding_id},
        )

        return ThreatActionResult(
            success      = True,
            action       = "suppress",
            threat_id    = threat_id,
            finding_id   = finding_id,
            aws_processed= aws_processed,
            message      = f"Threat suppressed ({reason})" + (f" in AWS Security Hub" if aws_processed else " (DB only)"),
        )

    async def get_threat_stats(self, tenant_id: str) -> ThreatStats:
        result = await self.db.execute(
            select(Threat.severity, Threat.status, func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id)
            .group_by(Threat.severity, Threat.status)
        )
        stats = ThreatStats()
        for severity, status, count in result.fetchall():
            stats.total += count
            if severity == "critical": stats.critical += count
            elif severity == "high":   stats.high     += count
            elif severity == "medium": stats.medium   += count
            elif severity == "low":    stats.low      += count
            if status == "open":     stats.open     += count
            elif status == "resolved": stats.resolved += count
        return stats

    # ── Vulnerabilities ───────────────────────────────────────────────────────

    async def list_vulnerabilities(
        self, tenant_id: str, page: int = 1, page_size: int = 20,
        severity: Optional[str] = None, status: Optional[str] = None,
    ) -> dict:
        query = select(Vulnerability).where(Vulnerability.tenant_id == tenant_id)
        if severity: query = query.where(Vulnerability.severity == severity)
        if status:   query = query.where(Vulnerability.status == status)
        total = await self._count(query)
        items = await self._paginate(
            query.order_by(Vulnerability.cvss_score.desc().nullslast(), Vulnerability.created_at.desc()),
            page, page_size,
        )
        return {
            "data": [VulnerabilityResponse.model_validate(v) for v in items],
            "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def get_vulnerability(self, vuln_id: str) -> VulnerabilityResponse:
        vuln = await self._get_by_id(Vulnerability, vuln_id)
        return VulnerabilityResponse.model_validate(vuln)

    async def update_vulnerability(self, vuln_id: str, data: VulnerabilityUpdate) -> VulnerabilityResponse:
        vuln = await self._get_by_id(Vulnerability, vuln_id)
        if data.status:
            vuln.status = data.status
        await self.db.flush()
        return VulnerabilityResponse.model_validate(vuln)

    async def get_vulnerability_stats(self, tenant_id: str) -> VulnerabilityStats:
        result = await self.db.execute(
            select(Vulnerability.severity, Vulnerability.status, func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id)
            .group_by(Vulnerability.severity, Vulnerability.status)
        )
        stats = VulnerabilityStats()
        for severity, status, count in result.fetchall():
            stats.total += count
            if severity == "critical": stats.critical  += count
            elif severity == "high":   stats.high      += count
            elif severity == "medium": stats.medium    += count
            elif severity == "low":    stats.low       += count
            if status == "open":       stats.open      += count
            elif status == "patched":  stats.patched   += count
            elif status == "wont_fix": stats.wont_fix  += count
        return stats

    # ── Compliance ────────────────────────────────────────────────────────────

    async def list_compliance(self, tenant_id: str) -> list[dict]:
        result = await self.db.execute(
            select(Compliance).where(Compliance.tenant_id == tenant_id).order_by(Compliance.framework)
        )
        return [c.to_dict() for c in result.scalars().all()]

    async def get_compliance_score(self, tenant_id: str) -> dict:
        result = await self.db.execute(
            select(func.avg(Compliance.score)).where(Compliance.tenant_id == tenant_id)
        )
        avg_score = float(result.scalar() or 0)
        return {"overall_score": round(avg_score, 1), "status": "compliant" if avg_score >= 80 else "non_compliant"}

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _find_aws_integration(self, tenant_id: str) -> Optional[Integration]:
        result = await self.db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.type == "aws",
                Integration.is_active == True,
                Integration.status == "connected",
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
            self.db.add(AuditLog(
                tenant_id=tenant_id, user_id=user_id, action=action,
                resource=resource, resource_id=resource_id,
                details=details, status=status,
            ))
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Audit log write failed (non-fatal): {e}")
