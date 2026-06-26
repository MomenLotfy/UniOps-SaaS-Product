from __future__ import annotations
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Repository, Scan
from app.models.vulnerability import Vulnerability
from app.models.threat import Threat
from app.models.security_policy import SecurityPolicy
from app.models.security_exception import SecurityException
from app.models.repository_risk import RepositoryRiskScore
from app.models.security_posture import SecurityPostureScore
from app.utils.logger import logger

class CopilotContextBuilder:
    """
    Gather and sanitize data from across the platform to provide
    comprehensive context to the AI Copilot.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_full_context(
        self,
        tenant_id: str,
        repo_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        scan_id: Optional[str] = None
    ) -> dict:
        """
        Constructs a complete snapshot of the security state relevant to the query.
        """
        context = {
            "tenant_id": tenant_id,
            "repository": await self._get_repo_context(tenant_id, repo_id),
            "scan": await self._get_scan_context(tenant_id, scan_id),
            "finding": await self._get_finding_context(tenant_id, finding_id),
            "posture": await self._get_posture_context(tenant_id),
            "policies": await self._get_policies_context(tenant_id),
        }

        # Sanitize secrets/tokens from the final context
        return self._sanitize_context(context)

    async def _get_repo_context(self, tenant_id: str, repo_id: Optional[str] | None) -> dict:
        if not repo_id:
            return {"status": "not_selected"}

        repo = (await self.db.execute(
            select(Repository).where(Repository.id == repo_id, Repository.tenant_id == tenant_id)
        )).scalar_one_or_none()

        if not repo:
            return {"error": "Repository not found"}

        risk = (await self.db.execute(
            select(RepositoryRiskScore).where(RepositoryRiskScore.repo_id == repo_id)
        )).scalar_one_or_none()

        return {
            "id": repo.id,
            "name": repo.full_name,
            "is_private": repo.is_private,
            "risk_rating": risk.risk_level if risk else "unknown",
            "security_score": risk.security_score if risk else None,
            "critical_findings": risk.critical_count if risk else 0,
        }

    async def _get_scan_context(self, tenant_id: str, scan_id: Optional[str] | None) -> dict:
        if not scan_id:
            return {"status": "not_selected"}

        scan = (await self.db.execute(
            select(Scan).where(Scan.id == scan_id, Scan.tenant_id == tenant_id)
        )).scalar_one_or_none()

        if not scan:
            return {"error": "Scan not found"}

        return {
            "id": scan.id,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "status": scan.status,
            "type": scan.scan_type,
        }

    async def _get_finding_context(self, tenant_id: str, finding_id: Optional[str] | None) -> dict:
        if not finding_id:
            return {"status": "not_selected"}

        # Check vulnerability first
        vuln = (await self.db.execute(
            select(Vulnerability).where(Vulnerability.id == finding_id, Vulnerability.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if vuln:
            return {
                "type": "vulnerability",
                "id": vuln.id,
                "cve": vuln.cve_id,
                "title": vuln.title,
                "severity": vuln.severity,
                "package": vuln.package_name,
                "version": vuln.package_version,
                "fixed_version": vuln.fixed_version,
                "description": vuln.description,
            }

        # Check threat
        threat = (await self.db.execute(
            select(Threat).where(Threat.id == finding_id, Threat.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if threat:
            return {
                "type": "threat",
                "id": threat.id,
                "title": threat.title,
                "severity": threat.severity,
                "category": threat.category,
                "description": threat.description,
            }

        return {"error": "Finding not found"}

    async def _get_posture_context(self, tenant_id: str) -> dict:
        posture = (await self.db.execute(
            select(SecurityPostureScore).where(SecurityPostureScore.tenant_id == tenant_id)
            .order_by(SecurityPostureScore.recorded_at.desc())
        )).scalar_one_or_none()

        if not posture:
            return {"status": "no_data"}

        return {
            "overall": posture.overall_score,
            "compliance": posture.compliance_score,
            "vulnerabilities": posture.vulnerability_score,
            "threats": posture.threat_score,
            "trend": posture.trend,
        }

    async def _get_policies_context(self, tenant_id: str) -> list[dict]:
        policies = (await self.db.execute(
            select(SecurityPolicy).where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.status == "active"
            )
        )).scalars().all()

        return [
            {"name": p.name, "enforcement": p.enforcement, "severity": p.severity}
            for p in policies
        ]

    def _sanitize_context(self, context: Any) -> Any:
        """
        Recursive scrubber to remove secrets, keys, and tokens before sending to AI.
        """
        if isinstance(context, dict):
            sanitized = {}
            for k, v in context.items():
                if any(kw in k.lower() for kw in ("secret", "token", "key", "password", "auth")):
                    sanitized[k] = "[MASKED]"
                else:
                    sanitized[k] = self._sanitize_context(v)
            return sanitized
        elif isinstance(context, list):
            return [self._sanitize_context(i) for i in context]
        return context
