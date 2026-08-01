from __future__ import annotations
"""Governance Overview API - executive dashboard data and analytics."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query
from app.api.deps import SecurityReadUser, AuditReadUser, TenantID, DBSession
from app.schemas.governance_overview import (
    GovernanceOverviewResponse,
    GovernanceExportFilter,
)
from app.schemas.common import APIResponse
from app.services.governance_overview_service import GovernanceOverviewService
from app.utils.logger import logger

router = APIRouter()


@router.get("/overview", response_model=APIResponse[GovernanceOverviewResponse])
async def get_governance_overview(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    days: int = Query(30, ge=7, le=365),
):
    """Get comprehensive governance overview dashboard data."""
    logger.info(f"[governance:overview] tenant={tenant_id[:8]} days={days}")
    svc = GovernanceOverviewService(db)
    overview = await svc.get_overview(tenant_id, days=days)
    return APIResponse(data=overview)


@router.get("/summary", response_model=APIResponse[dict])
async def get_governance_summary(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get just the governance summary KPIs for cards."""
    logger.info(f"[governance:summary] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    scores = await svc._compute_scores(tenant_id)
    risk_scores = await svc._compute_risk_scores(tenant_id)
    summary = await svc._build_summary(tenant_id, scores, risk_scores)
    return APIResponse(data={
        "overall_security_score": summary.overall_security_score,
        "governance_score": summary.governance_score,
        "compliance_percentage": summary.compliance_percentage,
        "risk_score": summary.risk_score,
        "open_findings": summary.open_findings,
        "critical_findings": summary.critical_findings,
        "breached_slas": summary.breached_slas,
        "open_exceptions": summary.open_exceptions,
        "remediation_progress_percentage": summary.remediation_progress_percentage,
        "policy_violations": summary.policy_violations,
        "protected_assets_percentage": summary.protected_assets_percentage,
        "repositories_covered_percentage": summary.repositories_covered_percentage,
        "average_mttr": summary.average_mttr,
    })


@router.get("/health", response_model=APIResponse[list[dict]])
async def get_health_indicators(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get health indicators for all resource types."""
    logger.info(f"[governance:health] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    indicators = await svc._build_health_indicators(tenant_id)
    return APIResponse(data=[i.model_dump() for i in indicators])


@router.get("/risk", response_model=APIResponse[dict])
async def get_risk_distribution(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    days: int = Query(30, ge=7, le=90),
):
    """Get risk distribution data for charts."""
    logger.info(f"[governance:risk] tenant={tenant_id[:8]} days={days}")
    svc = GovernanceOverviewService(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    distribution = await svc._build_risk_distribution(tenant_id, cutoff)
    return APIResponse(data=distribution.model_dump())


@router.get("/ownership-summary", response_model=APIResponse[dict])
async def get_ownership_summary(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get ownership summary."""
    logger.info(f"[governance:ownership] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    summary = await svc._build_ownership_summary(tenant_id)
    return APIResponse(data=summary.model_dump())


@router.get("/sla-summary", response_model=APIResponse[dict])
async def get_sla_summary(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get SLA summary."""
    logger.info(f"[governance:sla] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    summary = await svc._build_sla_summary(tenant_id)
    return APIResponse(data=summary.model_dump())


@router.get("/remediation", response_model=APIResponse[dict])
async def get_remediation_overview(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    days: int = Query(30, ge=7, le=365),
):
    """Get remediation overview."""
    logger.info(f"[governance:remediation] tenant={tenant_id[:8]} days={days}")
    svc = GovernanceOverviewService(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    overview = await svc._build_remediation_overview(tenant_id, cutoff)
    return APIResponse(data=overview.model_dump())


@router.get("/compliance", response_model=APIResponse[dict])
async def get_compliance_overview(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get compliance overview."""
    logger.info(f"[governance:compliance] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    overview = await svc._build_compliance_overview(tenant_id)
    return APIResponse(data=overview.model_dump())


@router.get("/policy", response_model=APIResponse[dict])
async def get_policy_overview(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get policy overview."""
    logger.info(f"[governance:policy] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    overview = await svc._build_policy_overview(tenant_id)
    return APIResponse(data=overview.model_dump())


@router.get("/threats", response_model=APIResponse[dict])
async def get_threat_intelligence(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get threat intelligence."""
    logger.info(f"[governance:threats] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    intelligence = await svc._build_threat_intelligence(tenant_id)
    return APIResponse(data=intelligence.model_dump())


@router.get("/timeline", response_model=APIResponse[dict])
async def get_executive_timeline(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get executive timeline."""
    logger.info(f"[governance:timeline] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    timeline = await svc._build_executive_timeline(tenant_id, cutoff)
    return APIResponse(data=timeline.model_dump())


@router.get("/business-impact", response_model=APIResponse[dict])
async def get_business_impact(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get business impact analysis."""
    logger.info(f"[governance:impact] tenant={tenant_id[:8]}")
    svc = GovernanceOverviewService(db)
    impact = await svc._build_business_impact(tenant_id)
    return APIResponse(data=impact.model_dump())


@router.post("/export", response_model=APIResponse[dict])
async def export_governance_data(
    current_user: AuditReadUser,
    tenant_id: TenantID,
    db: DBSession,
    filters: GovernanceExportFilter,
):
    """Export governance data in specified format."""
    logger.info(f"[governance:export] tenant={tenant_id[:8]} format={filters.format}")
    svc = GovernanceOverviewService(db)
    overview = await svc.get_overview(tenant_id, days=30)

    # Generate export based on format
    if filters.format == "json":
        return APIResponse(data={
            "format": "json",
            "data": overview.model_dump(),
        })
    elif filters.format == "csv":
        # Generate CSV content
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Summary section
        writer.writerow(["Governance Summary"])
        summary = overview.summary
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Overall Security Score", summary.overall_security_score])
        writer.writerow(["Governance Score", summary.governance_score])
        writer.writerow(["Compliance %", summary.compliance_percentage])
        writer.writerow(["Risk Score", summary.risk_score])
        writer.writerow(["Open Findings", summary.open_findings])
        writer.writerow(["Critical Findings", summary.critical_findings])
        writer.writerow(["Breached SLAs", summary.breached_slas])
        writer.writerow(["Open Exceptions", summary.open_exceptions])
        writer.writerow(["Remediation Progress %", summary.remediation_progress_percentage])
        writer.writerow(["Policy Violations", summary.policy_violations])
        writer.writerow(["Protected Assets %", summary.protected_assets_percentage])
        writer.writerow(["Repos Covered %", summary.repositories_covered_percentage])
        writer.writerow(["Average MTTR", summary.average_mttr])

        return APIResponse(data={
            "format": "csv",
            "data": output.getvalue(),
        })
    elif filters.format == "excel":
        # Placeholder for Excel export
        return APIResponse(data={
            "format": "excel",
            "message": "Excel export requires openpyxl - contact admin",
        })

    return APIResponse(data={"format": "unknown"})
