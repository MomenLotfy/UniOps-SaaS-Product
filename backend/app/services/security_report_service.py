from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_report import SecurityReport
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.compliance import Compliance
from app.models.security_policy import SecurityPolicy
from app.models.security_exception import SecurityException
from app.schemas.security_report import SecurityReportGenerate, SecurityReportResponse
from app.core.exceptions import NotFoundError
from app.services.base import BaseService
from app.utils.logger import logger


REPORT_TYPES = {
    "executive_summary":    "Executive Security Summary",
    "threat_assessment":    "Threat Assessment Report",
    "vulnerability_report": "Vulnerability Report",
    "compliance_report":    "Compliance Status Report",
    "posture_report":       "Security Posture Report",
    "exception_report":     "Exception Management Report",
    "full_audit":           "Full Security Audit Report",
}


class SecurityReportService(BaseService):

    async def list_reports(
        self, tenant_id: str, page: int = 1, page_size: int = 20,
        report_type: Optional[str] = None, status: Optional[str] = None,
    ) -> dict:
        query = select(SecurityReport).where(SecurityReport.tenant_id == tenant_id)
        if report_type: query = query.where(SecurityReport.report_type == report_type)
        if status:      query = query.where(SecurityReport.status == status)

        total = await self._count(query)
        items = await self._paginate(query.order_by(SecurityReport.created_at.desc()), page, page_size)
        return {
            "data": [SecurityReportResponse.model_validate(r) for r in items],
            "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def generate_report(
        self, tenant_id: str, data: SecurityReportGenerate, generated_by: str,
    ) -> SecurityReportResponse:
        report = SecurityReport(
            tenant_id=tenant_id,
            generated_by=generated_by,
            status="generating",
            **data.model_dump(),
        )
        self.db.add(report)
        await self.db.flush()

        try:
            findings, summary = await self._compile_report(tenant_id, data)
            report.findings = findings
            report.summary = summary
            report.status = "completed"
            report.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            report.status = "failed"
            report.error = str(e)
            logger.error(f"[report:generate] failed: {e}")

        await self.db.flush()
        logger.info(f"[report:generate] id={report.id[:8]} type={data.report_type} status={report.status}")
        return SecurityReportResponse.model_validate(report)

    async def _compile_report(self, tenant_id: str, data: SecurityReportGenerate) -> tuple[dict, dict]:
        period_filter = {}
        if data.period_start:
            period_filter["start"] = data.period_start
        if data.period_end:
            period_filter["end"] = data.period_end

        threats_q  = select(func.count(Threat.id)).where(Threat.tenant_id == tenant_id)
        vulns_q    = select(func.count(Vulnerability.id)).where(Vulnerability.tenant_id == tenant_id)
        policies_q = select(func.count(SecurityPolicy.id)).where(SecurityPolicy.tenant_id == tenant_id)
        excepts_q  = select(func.count(SecurityException.id)).where(SecurityException.tenant_id == tenant_id)

        t_total   = (await self.db.execute(threats_q)).scalar() or 0
        t_open    = (await self.db.execute(threats_q.where(Threat.status == "open"))).scalar() or 0
        t_crit    = (await self.db.execute(threats_q.where(Threat.severity == "critical"))).scalar() or 0

        v_total   = (await self.db.execute(vulns_q)).scalar() or 0
        v_open    = (await self.db.execute(vulns_q.where(Vulnerability.status == "open"))).scalar() or 0
        v_crit    = (await self.db.execute(vulns_q.where(Vulnerability.severity == "critical"))).scalar() or 0

        p_total   = (await self.db.execute(policies_q)).scalar() or 0
        p_active  = (await self.db.execute(policies_q.where(SecurityPolicy.status == "active"))).scalar() or 0

        e_total   = (await self.db.execute(excepts_q)).scalar() or 0
        e_pending = (await self.db.execute(excepts_q.where(SecurityException.status == "pending"))).scalar() or 0

        # Compliance aggregate
        comp_result = await self.db.execute(
            select(Compliance.framework, Compliance.score)
            .where(Compliance.tenant_id == tenant_id)
        )
        compliance_data = [{"framework": r[0], "score": r[1]} for r in comp_result.all()]
        avg_compliance = (
            sum(c["score"] for c in compliance_data) / len(compliance_data)
            if compliance_data else 0.0
        )

        summary = {
            "report_type": data.report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_threats": t_total,
            "open_threats": t_open,
            "critical_threats": t_crit,
            "total_vulnerabilities": v_total,
            "open_vulnerabilities": v_open,
            "critical_vulnerabilities": v_crit,
            "total_policies": p_total,
            "active_policies": p_active,
            "total_exceptions": e_total,
            "pending_exceptions": e_pending,
            "avg_compliance_score": round(avg_compliance, 1),
            "compliance_frameworks": len(compliance_data),
        }
        findings = {
            "threats": {"total": t_total, "open": t_open, "critical": t_crit},
            "vulnerabilities": {"total": v_total, "open": v_open, "critical": v_crit},
            "compliance": compliance_data,
            "policies": {"total": p_total, "active": p_active},
            "exceptions": {"total": e_total, "pending": e_pending},
        }
        return findings, summary

    async def get_report(self, report_id: str) -> SecurityReportResponse:
        report = await self._get_by_id(SecurityReport, report_id)
        return SecurityReportResponse.model_validate(report)

    async def delete_report(self, report_id: str) -> None:
        report = await self._get_by_id(SecurityReport, report_id)
        await self.db.delete(report)
