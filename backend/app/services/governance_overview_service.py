from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_posture import SecurityPostureScore
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.compliance import Compliance
from app.models.asset import Asset
from app.models.security_policy import SecurityPolicy
from app.models.security_exception import SecurityException
from app.models.ownership import OwnershipMapping
from app.models.scan import Scan as ScanModel, Repository
from app.models.k8s_security import K8sScan
from app.models.repository_risk import RepositoryRiskScore
from app.models.repository_risk_history import RepositoryRiskHistory
from app.models.sla import SLA, SLAMonitoring
from app.models.remediation import RemediationTask
from app.models.compliance_check import ComplianceCheck
from app.schemas.governance_overview import (
    GovernanceOverviewResponse,
    GovernanceSummary,
    HealthIndicator,
    RiskDistribution,
    OwnershipSummary,
    SLASummary,
    RemediationOverview,
    ComplianceOverview,
    PolicyOverview,
    ThreatIntelligence,
    ExecutiveTimeline,
    BusinessImpact,
)
from app.services.base import BaseService
from app.utils.logger import logger


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


class GovernanceOverviewService(BaseService):

    async def get_overview(self, tenant_id: str, days: int = 30) -> GovernanceOverviewResponse:
        """Generate comprehensive governance overview for the dashboard."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        # Compute base scores
        scores = await self._compute_scores(tenant_id)
        risk_scores = await self._compute_risk_scores(tenant_id)

        # Summary
        summary = await self._build_summary(tenant_id, scores, risk_scores)

        # Health indicators
        health_indicators = await self._build_health_indicators(tenant_id)

        # Risk distribution
        risk_distribution = await self._build_risk_distribution(tenant_id, cutoff)

        # Ownership summary
        ownership_summary = await self._build_ownership_summary(tenant_id)

        # SLA summary
        sla_summary = await self._build_sla_summary(tenant_id)

        # Remediation overview
        remediation_overview = await self._build_remediation_overview(tenant_id, cutoff)

        # Compliance overview
        compliance_overview = await self._build_compliance_overview(tenant_id)

        # Policy overview
        policy_overview = await self._build_policy_overview(tenant_id)

        # Threat intelligence
        threat_intelligence = await self._build_threat_intelligence(tenant_id)

        # Executive timeline
        executive_timeline = await self._build_executive_timeline(tenant_id, cutoff)

        # Business impact
        business_impact = await self._build_business_impact(tenant_id)

        return GovernanceOverviewResponse(
            summary=summary,
            health_indicators=health_indicators,
            risk_distribution=risk_distribution,
            ownership_summary=ownership_summary,
            sla_summary=sla_summary,
            remediation_overview=remediation_overview,
            compliance_overview=compliance_overview,
            policy_overview=policy_overview,
            threat_intelligence=threat_intelligence,
            executive_timeline=executive_timeline,
            business_impact=business_impact,
        )

    async def _compute_scores(self, tenant_id: str) -> dict:
        """Compute all security scores for the tenant."""
        # Threat score
        t_total = (await self.db.execute(
            select(func.count(Threat.id)).where(Threat.tenant_id == tenant_id)
        )).scalar() or 0
        t_open = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id, Threat.status.in_(["open", "active"]))
        )).scalar() or 0
        t_crit = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id, Threat.severity == "critical", Threat.status.in_(["open", "active"]))
        )).scalar() or 0
        threat_score = _clamp(100 - (t_open * 3) - (t_crit * 7)) if t_total > 0 else 100.0

        # Vulnerability score
        v_total = (await self.db.execute(
            select(func.count(Vulnerability.id)).where(Vulnerability.tenant_id == tenant_id)
        )).scalar() or 0
        v_open = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        )).scalar() or 0
        v_crit = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.severity == "critical", Vulnerability.status == "open")
        )).scalar() or 0
        vuln_score = _clamp(100 - (v_open * 1.5) - (v_crit * 5)) if v_total > 0 else 100.0

        # Compliance score
        comp_result = await self.db.execute(
            select(Compliance.score).where(Compliance.tenant_id == tenant_id)
        )
        scores_list = [r[0] for r in comp_result.all()]
        compliance_score = (sum(scores_list) / len(scores_list)) if scores_list else 0.0

        # Asset score
        a_total = (await self.db.execute(
            select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
        )).scalar() or 0
        a_critical = (await self.db.execute(
            select(func.count(Asset.id))
            .where(Asset.tenant_id == tenant_id, Asset.risk_level == "critical")
        )).scalar() or 0
        asset_score = _clamp(100 - (a_critical / max(a_total, 1)) * 50) if a_total > 0 else 100.0

        # Policy score
        p_total = (await self.db.execute(
            select(func.count(SecurityPolicy.id)).where(SecurityPolicy.tenant_id == tenant_id)
        )).scalar() or 0
        p_active = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id, SecurityPolicy.status == "active")
        )).scalar() or 0
        policy_score = (p_active / max(p_total, 1)) * 100 if p_total > 0 else 0.0

        # Overall score (weighted)
        overall = _clamp(
            threat_score * 0.30 +
            vuln_score * 0.25 +
            compliance_score * 0.25 +
            asset_score * 0.10 +
            policy_score * 0.10
        )

        return {
            "overall": round(overall, 1),
            "threat": round(threat_score, 1),
            "vulnerability": round(vuln_score, 1),
            "compliance": round(compliance_score, 1),
            "asset": round(asset_score, 1),
            "policy": round(policy_score, 1),
            "breakdown": {
                "threats": {"open": t_open, "critical": t_crit, "total": t_total},
                "vulnerabilities": {"open": v_open, "critical": v_crit, "total": v_total},
                "assets": {"total": a_total, "critical_risk": a_critical},
                "policies": {"total": p_total, "active": p_active},
            },
        }

    async def _compute_risk_scores(self, tenant_id: str) -> dict:
        """Compute risk-related scores."""
        # Average risk score
        avg_risk_raw = (await self.db.execute(
            select(func.avg(RepositoryRiskScore.risk_score))
            .where(RepositoryRiskScore.tenant_id == tenant_id)
        )).scalar()
        overall_risk = round(float(avg_risk_raw), 1) if avg_risk_raw is not None else 0.0

        # Repository risk trend
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        risk_trend_rows = (await self.db.execute(
            select(
                func.date_trunc("day", RepositoryRiskHistory.recorded_at).label("day"),
                func.avg(RepositoryRiskHistory.risk_score).label("avg_risk"),
            )
            .where(
                RepositoryRiskHistory.tenant_id == tenant_id,
                RepositoryRiskHistory.recorded_at >= cutoff,
            )
            .group_by(text("1"))
            .order_by(text("1"))
        )).all()

        risk_trend = [
            {
                "date": row.day.strftime("%Y-%m-%d"),
                "avg_risk": round(float(row.avg_risk), 1),
            }
            for row in risk_trend_rows
        ]

        return {
            "overall_risk": overall_risk,
            "risk_trend": risk_trend,
        }

    async def _build_summary(self, tenant_id: str, scores: dict, risk_scores: dict) -> GovernanceSummary:
        """Build the governance summary KPIs."""
        # Open findings (vulnerabilities + threats)
        open_threats = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id, Threat.status.in_(["open", "active"]))
        )).scalar() or 0

        open_vulns = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        )).scalar() or 0

        critical_vulns = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == "critical",
                Vulnerability.status == "open",
            )
        )).scalar() or 0

        # Open exceptions
        open_exceptions = (await self.db.execute(
            select(func.count(SecurityException.id))
            .where(SecurityException.tenant_id == tenant_id, SecurityException.status == "pending")
        )).scalar() or 0

        # Breached SLAs
        breached_slas = (await self.db.execute(
            select(func.count(SLAMonitoring.id))
            .where(
                SLAMonitoring.tenant_id == tenant_id,
                SLAMonitoring.status == "breached"
            )
        )).scalar() or 0

        # Policy violations (active policies that are violated)
        policy_violations = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.status == "active",
                SecurityPolicy.violation_count > 0
            )
        )).scalar() or 0

        # Remediation progress
        total_remediations = (await self.db.execute(
            select(func.count(RemediationTask.id))
            .where(RemediationTask.tenant_id == tenant_id)
        )).scalar() or 0
        resolved_remediations = (await self.db.execute(
            select(func.count(RemediationTask.id))
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.status == "resolved"
            )
        )).scalar() or 0
        remediation_progress = round((resolved_remediations / max(total_remediations, 1)) * 100, 1)

        # Average MTTR (from remediation tasks)
        mttr_result = (await self.db.execute(
            select(func.avg(RemediationTask.mttr_hours))
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.mttr_hours.isnot(None)
            )
        )).scalar()
        average_mttr = round(float(mttr_result), 1) if mttr_result else 0.0

        # Protected assets
        total_assets = (await self.db.execute(
            select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
        )).scalar() or 0
        owned_assets = (await self.db.execute(
            select(func.count(OwnershipMapping.id))
            .where(OwnershipMapping.tenant_id == tenant_id)
        )).scalar() or 0
        protected_percentage = round((owned_assets / max(total_assets, 1)) * 100, 1)

        # Repositories covered
        total_repos = (await self.db.execute(
            select(func.count(Repository.id)).where(Repository.tenant_id == tenant_id)
        )).scalar() or 0
        covered_repos = owned_assets  # Reuse for repositories with ownership
        repos_covered_percentage = round((covered_repos / max(total_repos, 1)) * 100, 1)

        # Compliance percentage
        compliance_overall = scores.get("compliance", 0)

        return GovernanceSummary(
            overall_security_score=scores.get("overall", 0),
            governance_score=scores.get("overall", 0),
            compliance_percentage=compliance_overall,
            risk_score=risk_scores.get("overall_risk", 0),
            open_findings=open_vulns + open_threats,
            critical_findings=critical_vulns,
            breached_slas=breached_slas,
            open_exceptions=open_exceptions,
            remediation_progress_percentage=remediation_progress,
            policy_violations=policy_violations,
            protected_assets_percentage=protected_percentage,
            repositories_covered_percentage=repos_covered_percentage,
            average_mttr=average_mttr,
        )

    async def _build_health_indicators(self, tenant_id: str) -> list[HealthIndicator]:
        """Build health indicators for all resource types."""
        indicators = []

        # Repositories
        repos_result = (await self.db.execute(
            select(
                func.count(Repository.id).label("total"),
                func.sum(func.case((Repository.security_score >= 80, 1), else_=0)).label("healthy"),
                func.sum(func.case((and_(Repository.security_score >= 50, Repository.security_score < 80), 1), else_=0)).label("warning"),
                func.sum(func.case((Repository.security_score < 50, 1), else_=0)).label("critical"),
            )
            .where(Repository.tenant_id == tenant_id)
        )).one_or_none()
        if repos_result:
            indicators.append(HealthIndicator(
                resource_type="Repository",
                total=repos_result.total or 0,
                healthy=repos_result.healthy or 0,
                warning=repos_result.warning or 0,
                critical=repos_result.critical or 0,
                unknown=0,
            ))

        # Infrastructure (Virtual Machines)
        infra_result = (await self.db.execute(
            select(
                func.count(Asset.id).label("total"),
                func.sum(func.case((Asset.risk_level.in_(["low", "medium"]), 1), else_=0)).label("healthy"),
                func.sum(func.case((Asset.risk_level == "high", 1), else_=0)).label("warning"),
                func.sum(func.case((Asset.risk_level == "critical", 1), else_=0)).label("critical"),
            )
            .where(
                Asset.tenant_id == tenant_id,
                or_(
                    Asset.resource_type == "virtual_machine",
                    Asset.resource_type == "server",
                )
            )
        )).one_or_none()
        if infra_result:
            indicators.append(HealthIndicator(
                resource_type="Infrastructure",
                total=infra_result.total or 0,
                healthy=infra_result.healthy or 0,
                warning=infra_result.warning or 0,
                critical=infra_result.critical or 0,
                unknown=0,
            ))

        # Cloud Accounts
        cloud_result = (await self.db.execute(
            select(
                func.count(Asset.id).label("total"),
                func.sum(func.case((Asset.risk_level.in_(["low", "medium"]), 1), else_=0)).label("healthy"),
                func.sum(func.case((Asset.risk_level == "high", 1), else_=0)).label("warning"),
                func.sum(func.case((Asset.risk_level == "critical", 1), else_=0)).label("critical"),
            )
            .where(
                Asset.tenant_id == tenant_id,
                or_(
                    Asset.resource_type == "cloud_account",
                    Asset.source.in_(["aws", "azure", "gcp"]),
                )
            )
        )).one_or_none()
        if cloud_result:
            indicators.append(HealthIndicator(
                resource_type="Cloud Account",
                total=cloud_result.total or 0,
                healthy=cloud_result.healthy or 0,
                warning=cloud_result.warning or 0,
                critical=cloud_result.critical or 0,
                unknown=0,
            ))

        # Kubernetes Clusters
        k8s_result = (await self.db.execute(
            select(
                func.count(K8sScan.id).label("total"),
                func.sum(func.case((K8sScan.risk_score < 30, 1), else_=0)).label("healthy"),
                func.sum(func.case((and_(K8sScan.risk_score >= 30, K8sScan.risk_score < 60), 1), else_=0)).label("warning"),
                func.sum(func.case((K8sScan.risk_score >= 60, 1), else_=0)).label("critical"),
            )
            .where(K8sScan.tenant_id == tenant_id, K8sScan.status == "completed")
        )).one_or_none()
        if k8s_result:
            indicators.append(HealthIndicator(
                resource_type="Kubernetes Cluster",
                total=k8s_result.total or 0,
                healthy=k8s_result.healthy or 0,
                warning=k8s_result.warning or 0,
                critical=k8s_result.critical or 0,
                unknown=0,
            ))

        # Assets
        assets_result = (await self.db.execute(
            select(
                func.count(Asset.id).label("total"),
                func.sum(func.case((Asset.risk_level.in_(["low", "medium"]), 1), else_=0)).label("healthy"),
                func.sum(func.case((Asset.risk_level == "high", 1), else_=0)).label("warning"),
                func.sum(func.case((Asset.risk_level == "critical", 1), else_=0)).label("critical"),
            )
            .where(Asset.tenant_id == tenant_id)
        )).one_or_none()
        if assets_result:
            indicators.append(HealthIndicator(
                resource_type="Asset",
                total=assets_result.total or 0,
                healthy=assets_result.healthy or 0,
                warning=assets_result.warning or 0,
                critical=assets_result.critical or 0,
                unknown=0,
            ))

        # Applications
        apps_result = (await self.db.execute(
            select(
                func.count(Asset.id).label("total"),
                func.sum(func.case((Asset.risk_level.in_(["low", "medium"]), 1), else_=0)).label("healthy"),
                func.sum(func.case((Asset.risk_level == "high", 1), else_=0)).label("warning"),
                func.sum(func.case((Asset.risk_level == "critical", 1), else_=0)).label("critical"),
            )
            .where(
                Asset.tenant_id == tenant_id,
                or_(
                    Asset.resource_type == "application",
                    Asset.resource_type == "service",
                )
            )
        )).one_or_none()
        if apps_result:
            indicators.append(HealthIndicator(
                resource_type="Application",
                total=apps_result.total or 0,
                healthy=apps_result.healthy or 0,
                warning=apps_result.warning or 0,
                critical=apps_result.critical or 0,
                unknown=0,
            ))

        # Services
        services_result = (await self.db.execute(
            select(
                func.count(Asset.id).label("total"),
                func.sum(func.case((Asset.risk_level.in_(["low", "medium"]), 1), else_=0)).label("healthy"),
                func.sum(func.case((Asset.risk_level == "high", 1), else_=0)).label("warning"),
                func.sum(func.case((Asset.risk_level == "critical", 1), else_=0)).label("critical"),
            )
            .where(
                Asset.tenant_id == tenant_id,
                Asset.resource_type == "service"
            )
        )).one_or_none()
        if services_result:
            indicators.append(HealthIndicator(
                resource_type="Service",
                total=services_result.total or 0,
                healthy=services_result.healthy or 0,
                warning=services_result.warning or 0,
                critical=services_result.critical or 0,
                unknown=0,
            ))

        return indicators

    async def _build_risk_distribution(self, tenant_id: str, cutoff: datetime) -> RiskDistribution:
        """Build risk distribution data for charts."""
        # By severity (vulnerabilities)
        sev_result = (await self.db.execute(
            select(
                Vulnerability.severity.label("severity"),
                func.count(Vulnerability.id).label("count"),
            )
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
            .group_by(Vulnerability.severity)
        )).all()
        by_severity = {row.severity: row.count for row in sev_result}

        # By repository
        repo_result = (await self.db.execute(
            select(
                Repository.name.label("repository"),
                func.count(Vulnerability.id).label("count"),
            )
            .join(ScanModel, ScanModel.repo_id == Repository.id)
            .join(Vulnerability, Vulnerability.scan_id == ScanModel.id)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.status == "open"
            )
            .group_by(Repository.name)
            .order_by(func.count(Vulnerability.id).desc())
            .limit(10)
        )).all()
        by_repository = {row.repository: row.count for row in repo_result}

        # By business unit (from ownership)
        bu_result = (await self.db.execute(
            select(
                OwnershipMapping.business_unit.label("business_unit"),
                func.count(OwnershipMapping.id).label("count"),
            )
            .where(OwnershipMapping.tenant_id == tenant_id)
            .group_by(OwnershipMapping.business_unit)
        )).all()
        by_business_unit = {row.business_unit: row.count for row in bu_result}

        # By team
        team_result = (await self.db.execute(
            select(
                OwnershipMapping.team.label("team"),
                func.count(OwnershipMapping.id).label("count"),
            )
            .where(OwnershipMapping.tenant_id == tenant_id)
            .group_by(OwnershipMapping.team)
        )).all()
        by_team = {row.team: row.count for row in team_result}

        # By environment
        env_result = (await self.db.execute(
            select(
                OwnershipMapping.environment.label("environment"),
                func.count(OwnershipMapping.id).label("count"),
            )
            .where(OwnershipMapping.tenant_id == tenant_id)
            .group_by(OwnershipMapping.environment)
        )).all()
        by_environment = {row.environment: row.count for row in env_result}

        # By cloud provider
        cloud_result = (await self.db.execute(
            select(
                OwnershipMapping.cloud_provider.label("cloud_provider"),
                func.count(OwnershipMapping.id).label("count"),
            )
            .where(OwnershipMapping.tenant_id == tenant_id)
            .group_by(OwnershipMapping.cloud_provider)
        )).all()
        by_cloud_provider = {row.cloud_provider: row.count for row in cloud_result}

        # Trend data
        risk_trend = (await self.db.execute(
            select(
                func.date_trunc("day", RepositoryRiskHistory.recorded_at).label("day"),
                func.avg(RepositoryRiskHistory.risk_score).label("avg_risk"),
            )
            .where(
                RepositoryRiskHistory.tenant_id == tenant_id,
                RepositoryRiskHistory.recorded_at >= cutoff,
            )
            .group_by(text("1"))
            .order_by(text("1"))
        )).all()
        trend = [
            {
                "date": row.day.strftime("%Y-%m-%d"),
                "avg_risk": round(float(row.avg_risk), 1),
            }
            for row in risk_trend
        ]

        return RiskDistribution(
            by_severity=by_severity,
            by_repository=by_repository,
            by_business_unit=by_business_unit,
            by_team=by_team,
            by_environment=by_environment,
            by_cloud_provider=by_cloud_provider,
            trend=trend,
        )

    async def _build_ownership_summary(self, tenant_id: str) -> OwnershipSummary:
        """Build ownership summary."""
        total_owned = (await self.db.execute(
            select(func.count(OwnershipMapping.id))
            .where(OwnershipMapping.tenant_id == tenant_id)
        )).scalar() or 0

        teams_result = (await self.db.execute(
            select(func.count(func.distinct(OwnershipMapping.team)))
            .where(OwnershipMapping.tenant_id == tenant_id)
        )).scalar() or 0

        departments_result = (await self.db.execute(
            select(func.count(func.distinct(OwnershipMapping.department)))
            .where(OwnershipMapping.tenant_id == tenant_id)
        )).scalar() or 0

        owners_result = (await self.db.execute(
            select(
                OwnershipMapping.owner.label("owner"),
                func.count(OwnershipMapping.id).label("count"),
                func.max(OwnershipMapping.last_updated).label("last_updated"),
            )
            .where(OwnershipMapping.tenant_id == tenant_id, OwnershipMapping.owner.isnot(None))
            .group_by(OwnershipMapping.owner)
            .order_by(func.count(OwnershipMapping.id).desc())
            .limit(10)
        )).all()

        owners = [
            {"name": row.owner, "count": row.count, "last_updated": row.last_updated.isoformat() if row.last_updated else None}
            for row in owners_result
        ]

        return OwnershipSummary(
            total_owned=total_owned,
            teams_responsible=teams_result,
            departments_responsible=departments_result,
            owners=owners,
        )

    async def _build_sla_summary(self, tenant_id: str) -> SLASummary:
        """Build SLA summary."""
        total_sla = (await self.db.execute(
            select(func.count(SLA.id))
            .where(SLA.tenant_id == tenant_id)
        )).scalar() or 0

        compliant = (await self.db.execute(
            select(func.count(SLAMonitoring.id))
            .where(
                SLAMonitoring.tenant_id == tenant_id,
                SLAMonitoring.status == "compliant"
            )
        )).scalar() or 0

        breached = (await self.db.execute(
            select(func.count(SLAMonitoring.id))
            .where(
                SLAMonitoring.tenant_id == tenant_id,
                SLAMonitoring.status == "breached"
            )
        )).scalar() or 0

        at_risk = (await self.db.execute(
            select(func.count(SLAMonitoring.id))
            .where(
                SLAMonitoring.tenant_id == tenant_id,
                SLAMonitoring.status == "at_risk"
            )
        )).scalar() or 0

        compliance_rate = round((compliant / max(total_sla, 1)) * 100, 1)

        # Average response time
        response_result = (await self.db.execute(
            select(func.avg(SLAMonitoring.response_time_minutes))
            .where(
                SLAMonitoring.tenant_id == tenant_id,
                SLAMonitoring.response_time_minutes.isnot(None)
            )
        )).scalar()
        avg_response = round(float(response_result) / 60, 1) if response_result else 0.0

        return SLASummary(
            total_sla=total_sla,
            compliant=compliant,
            breached=breached,
            at_risk=at_risk,
            compliance_rate=compliance_rate,
            avg_response_time_hours=avg_response,
        )

    async def _build_remediation_overview(self, tenant_id: str, cutoff: datetime) -> RemediationOverview:
        """Build remediation overview."""
        total_open = (await self.db.execute(
            select(func.count(RemediationTask.id))
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.status.in_(["open", "in_progress"])
            )
        )).scalar() or 0

        total_resolved = (await self.db.execute(
            select(func.count(RemediationTask.id))
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.status == "resolved"
            )
        )).scalar() or 0

        # By severity
        sev_result = (await self.db.execute(
            select(
                RemediationTask.severity.label("severity"),
                func.count(RemediationTask.id).label("count"),
            )
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.status == "open"
            )
            .group_by(RemediationTask.severity)
        )).all()
        by_severity = {row.severity: row.count for row in sev_result}

        # By resource type
        type_result = (await self.db.execute(
            select(
                RemediationTask.resource_type.label("resource_type"),
                func.count(RemediationTask.id).label("count"),
            )
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.status == "open"
            )
            .group_by(RemediationTask.resource_type)
        )).all()
        by_resource_type = {row.resource_type: row.count for row in type_result}

        # MTTR
        mttr_result = (await self.db.execute(
            select(func.avg(RemediationTask.mttr_hours))
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.mttr_hours.isnot(None)
            )
        )).scalar()
        avg_mttr = round(float(mttr_result), 1) if mttr_result else 0.0

        # Trends (weekly counts)
        trend_result = (await self.db.execute(
            select(
                func.date_trunc("week", RemediationTask.created_at).label("week"),
                func.count(RemediationTask.id).label("total"),
                func.sum(func.case((RemediationTask.status == "resolved", 1), else_=0)).label("resolved"),
            )
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.created_at >= cutoff
            )
            .group_by(text("1"))
            .order_by(text("1"))
        )).all()

        trends = [
            {
                "week": row.week.strftime("%Y-%m-%d"),
                "total": row.total,
                "resolved": row.resolved,
            }
            for row in trend_result
        ]

        return RemediationOverview(
            total_open=total_open,
            total_resolved=total_resolved,
            avg_mttr_hours=avg_mttr,
            by_severity=by_severity,
            by_resource_type=by_resource_type,
            trends=trends,
        )

    async def _build_compliance_overview(self, tenant_id: str) -> ComplianceOverview:
        """Build compliance overview."""
        total_checks = (await self.db.execute(
            select(func.count(ComplianceCheck.id))
            .where(ComplianceCheck.tenant_id == tenant_id)
        )).scalar() or 0

        passed = (await self.db.execute(
            select(func.count(ComplianceCheck.id))
            .where(
                ComplianceCheck.tenant_id == tenant_id,
                ComplianceCheck.status == "passed"
            )
        )).scalar() or 0

        failed = (await self.db.execute(
            select(func.count(ComplianceCheck.id))
            .where(
                ComplianceCheck.tenant_id == tenant_id,
                ComplianceCheck.status == "failed"
            )
        )).scalar() or 0

        passed_rate = round((passed / max(total_checks, 1)) * 100, 1)

        # By category
        cat_result = (await self.db.execute(
            select(
                ComplianceCheck.category.label("category"),
                func.count(ComplianceCheck.id).label("count"),
            )
            .where(
                ComplianceCheck.tenant_id == tenant_id,
                ComplianceCheck.status == "passed"
            )
            .group_by(ComplianceCheck.category)
        )).all()
        by_category = {row.category: row.count for row in cat_result}

        # By standard
        std_result = (await self.db.execute(
            select(
                ComplianceCheck.standard.label("standard"),
                func.count(ComplianceCheck.id).label("count"),
            )
            .where(
                ComplianceCheck.tenant_id == tenant_id,
                ComplianceCheck.status == "passed"
            )
            .group_by(ComplianceCheck.standard)
        )).all()
        by_standard = {row.standard: row.count for row in std_result}

        return ComplianceOverview(
            total_checks=total_checks,
            passed=passed,
            failed=failed,
            passed_rate=passed_rate,
            by_category=by_category,
            by_standard=by_standard,
        )

    async def _build_policy_overview(self, tenant_id: str) -> PolicyOverview:
        """Build policy overview."""
        total_policies = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id)
        )).scalar() or 0

        active = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.status == "active"
            )
        )).scalar() or 0

        violated = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.violation_count > 0
            )
        )).scalar() or 0

        # By category
        cat_result = (await self.db.execute(
            select(
                SecurityPolicy.category.label("category"),
                func.count(SecurityPolicy.id).label("count"),
            )
            .where(SecurityPolicy.tenant_id == tenant_id)
            .group_by(SecurityPolicy.category)
        )).all()
        by_category = {row.category: row.count for row in cat_result}

        # By status
        status_result = (await self.db.execute(
            select(
                SecurityPolicy.status.label("status"),
                func.count(SecurityPolicy.id).label("count"),
            )
            .where(SecurityPolicy.tenant_id == tenant_id)
            .group_by(SecurityPolicy.status)
        )).all()
        by_status = {row.status: row.count for row in status_result}

        return PolicyOverview(
            total_policies=total_policies,
            active=active,
            violated=violated,
            by_category=by_category,
            by_status=by_status,
        )

    async def _build_threat_intelligence(self, tenant_id: str) -> ThreatIntelligence:
        """Build threat intelligence summary."""
        total_threats = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id)
        )).scalar() or 0

        open_threats = (await self.db.execute(
            select(func.count(Threat.id))
            .where(
                Threat.tenant_id == tenant_id,
                Threat.status.in_(["open", "active"])
            )
        )).scalar() or 0

        critical_threats = (await self.db.execute(
            select(func.count(Threat.id))
            .where(
                Threat.tenant_id == tenant_id,
                Threat.severity == "critical",
                Threat.status.in_(["open", "active"])
            )
        )).scalar() or 0

        # By severity
        sev_result = (await self.db.execute(
            select(
                Threat.severity.label("severity"),
                func.count(Threat.id).label("count"),
            )
            .where(Threat.tenant_id == tenant_id, Threat.status.in_(["open", "active"]))
            .group_by(Threat.severity)
        )).all()
        by_severity = {row.severity: row.count for row in sev_result}

        # By source
        src_result = (await self.db.execute(
            select(
                Threat.source.label("source"),
                func.count(Threat.id).label("count"),
            )
            .where(Threat.tenant_id == tenant_id, Threat.status.in_(["open", "active"]))
            .group_by(Threat.source)
        )).all()
        by_source = {row.source: row.count for row in src_result}

        # Top threats
        top_result = (await self.db.execute(
            select(Threat)
            .where(Threat.tenant_id == tenant_id, Threat.status.in_(["open", "active"]))
            .order_by(Threat.severity.desc(), Threat.created_at.desc())
            .limit(5)
        )).scalars().all()

        top_threats = [
            {
                "id": t.id,
                "title": t.title,
                "severity": t.severity,
                "source": t.source,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in top_result
        ]

        return ThreatIntelligence(
            total_threats=total_threats,
            open_threats=open_threats,
            critical_threats=critical_threats,
            by_severity=by_severity,
            by_source=by_source,
            top_threats=top_threats,
        )

    async def _build_executive_timeline(self, tenant_id: str, cutoff: datetime) -> ExecutiveTimeline:
        """Build executive timeline."""
        # Recent events (last 7 days)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        # Vulnerability events
        vuln_result = (await self.db.execute(
            select(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.created_at >= recent_cutoff
            )
            .order_by(Vulnerability.created_at.desc())
            .limit(5)
        )).scalars().all()

        # Policy events
        policy_result = (await self.db.execute(
            select(SecurityPolicy)
            .where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.updated_at >= recent_cutoff
            )
            .order_by(SecurityPolicy.updated_at.desc())
            .limit(5)
        )).scalars().all()

        # Compliance events
        comp_result = (await self.db.execute(
            select(ComplianceCheck)
            .where(
                ComplianceCheck.tenant_id == tenant_id,
                ComplianceCheck.created_at >= recent_cutoff
            )
            .order_by(ComplianceCheck.created_at.desc())
            .limit(5)
        )).scalars().all()

        recent_events = []

        for v in vuln_result:
            recent_events.append({
                "type": "vulnerability",
                "title": f"New vulnerability: {v.cve_id or 'Unknown'}",
                "description": f"Severity: {v.severity}, Resource: {v.resource_name}",
                "timestamp": v.created_at.isoformat() if v.created_at else None,
            })

        for p in policy_result:
            recent_events.append({
                "type": "policy",
                "title": f"Policy update: {p.name}",
                "description": f"Category: {p.category}, Status: {p.status}",
                "timestamp": p.updated_at.isoformat() if p.updated_at else None,
            })

        for c in comp_result:
            recent_events.append({
                "type": "compliance",
                "title": f"Compliance check: {c.check_name}",
                "description": f"Result: {c.status}, Standard: {c.standard}",
                "timestamp": c.created_at.isoformat() if c.created_at else None,
            })

        # Sort and limit
        recent_events.sort(key=lambda x: x["timestamp"], reverse=True)
        recent_events = recent_events[:10]

        # Upcoming tasks (remediations due soon)
        upcoming_cutoff = datetime.now(timezone.utc) + timedelta(days=7)
        upcoming_result = (await self.db.execute(
            select(RemediationTask)
            .where(
                RemediationTask.tenant_id == tenant_id,
                RemediationTask.due_date >= datetime.now(timezone.utc),
                RemediationTask.due_date <= upcoming_cutoff,
                RemediationTask.status.in_(["open", "in_progress"])
            )
            .order_by(RemediationTask.due_date.asc())
            .limit(5)
        )).scalars().all()

        upcoming_tasks = [
            {
                "title": f"Remediation: {r.resource_name}",
                "description": f"Due: {r.due_date.strftime('%Y-%m-%d') if r.due_date else 'N/A'}, Severity: {r.severity}",
                "due_date": r.due_date.isoformat() if r.due_date else None,
            }
            for r in upcoming_result
        ]

        # Alerts (critical items)
        alerts_result = (await self.db.execute(
            select(Threat)
            .where(
                Threat.tenant_id == tenant_id,
                Threat.severity == "critical",
                Threat.status.in_(["open", "active"])
            )
            .limit(5)
        )).scalars().all()

        alerts = [
            {
                "severity": "critical",
                "title": a.title,
                "description": a.description or "",
                "timestamp": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts_result
        ]

        return ExecutiveTimeline(
            recent_events=recent_events,
            upcoming_tasks=upcoming_tasks,
            alerts=alerts,
        )

    async def _build_business_impact(self, tenant_id: str) -> BusinessImpact:
        """Build business impact analysis."""
        # High risk business units (with breached SLAs or critical assets)
        hu_result = (await self.db.execute(
            select(
                OwnershipMapping.business_unit.label("business_unit"),
                func.count(OwnershipMapping.id).label("critical_count"),
                func.sum(func.case((OwnershipMapping.risk_level == "critical", 1), else_=0)).label("crit_risk"),
            )
            .where(
                OwnershipMapping.tenant_id == tenant_id,
                or_(
                    OwnershipMapping.risk_level == "critical",
                    OwnershipMapping.sla_status == "breached",
                )
            )
            .group_by(OwnershipMapping.business_unit)
            .order_by(func.count(OwnershipMapping.id).desc())
        )).all()

        high_risk_bu = [
            {
                "name": row.business_unit,
                "critical_count": row.critical_count or 0,
                "crit_risk": row.crit_risk or 0,
            }
            for row in hu_result
        ]

        # Critical applications
        app_result = (await self.db.execute(
            select(
                Asset.resource_name.label("application"),
                Asset.resource_type.label("type"),
                Asset.risk_level.label("risk"),
            )
            .where(
                Asset.tenant_id == tenant_id,
                or_(
                    Asset.risk_level == "critical",
                    Asset.is_critical == True
                )
            )
            .order_by(Asset.risk_level.desc())
            .limit(10)
        )).all()

        critical_apps = [
            {
                "name": row.application,
                "type": row.type,
                "risk": row.risk,
            }
            for row in app_result
        ]

        # Service affected count
        affected_result = (await self.db.execute(
            select(func.count(func.distinct(OwnershipMapping.service_name)))
            .where(
                OwnershipMapping.tenant_id == tenant_id,
                OwnershipMapping.sla_status == "breached"
            )
        )).scalar() or 0

        # Estimated impact score (based on critical assets and breached SLAs)
        critical_count = (await self.db.execute(
            select(func.count(Asset.id))
            .where(
                Asset.tenant_id == tenant_id,
                Asset.risk_level == "critical"
            )
        )).scalar() or 0
        breached_count = (await self.db.execute(
            select(func.count(SLAMonitoring.id))
            .where(
                SLAMonitoring.tenant_id == tenant_id,
                SLAMonitoring.status == "breached"
            )
        )).scalar() or 0

        estimated_impact = round(min(100, (critical_count * 10) + (breached_count * 5)), 1)

        return BusinessImpact(
            high_risk_business_units=high_risk_bu,
            critical_applications=critical_apps,
            service_affected_count=affected_count,
            estimated_impact_score=estimated_impact,
        )
