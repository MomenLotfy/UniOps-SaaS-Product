from __future__ import annotations
"""Compliance API — production-grade Compliance Management Center."""
from datetime import datetime, timezone
from typing import Optional, List, Any
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.security_service import SecurityService
from app.models.compliance import Compliance
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.security_policy import SecurityPolicy
from app.models.asset import Asset
from app.models.scan import Scan

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_controls(compliance_rows: list[Compliance]) -> list[dict]:
    """
    Flatten controls from the JSON `details` field on each Compliance row.
    Each entry in details is expected to be a control dict.
    Also synthesises a minimal control dict if details is missing.
    """
    controls = []
    for row in compliance_rows:
        details = row.details or []
        if not details:
            # Create synthetic placeholder based on row-level stats
            controls.append({
                "id": f"{row.framework}-overview",
                "control_id": "OVERVIEW",
                "title": f"{row.framework} Overview",
                "framework": row.framework,
                "framework_db_id": row.id,
                "category": "General",
                "severity": "medium",
                "status": row.status,
                "evidence_count": 0,
                "has_evidence": False,
                "owner": None,
                "last_evaluated": row.updated_at.isoformat() if row.updated_at else None,
                "next_evaluation": None,
                "description": None,
                "mapped_policies": [],
                "mapped_assets": [],
                "mapped_repos": [],
                "mapped_k8s": [],
                "related_findings": [],
                "exceptions": [],
                "score": row.score,
            })
        else:
            for ctrl in details:
                if not isinstance(ctrl, dict):
                    continue
                ctrl.setdefault("framework", row.framework)
                ctrl.setdefault("framework_db_id", row.id)
                ctrl.setdefault("status", "unknown")
                ctrl.setdefault("severity", "medium")
                ctrl.setdefault("category", "General")
                ctrl.setdefault("evidence_count", 0)
                ctrl.setdefault("has_evidence", False)
                ctrl.setdefault("owner", None)
                ctrl.setdefault("last_evaluated", row.updated_at.isoformat() if row.updated_at else None)
                ctrl.setdefault("next_evaluation", None)
                ctrl.setdefault("description", None)
                ctrl.setdefault("mapped_policies", [])
                ctrl.setdefault("mapped_assets", [])
                ctrl.setdefault("mapped_repos", [])
                ctrl.setdefault("mapped_k8s", [])
                ctrl.setdefault("related_findings", [])
                ctrl.setdefault("exceptions", [])
                ctrl.setdefault("id", ctrl.get("control_id", str(len(controls))))
                controls.append(ctrl)
    return controls


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_compliance_summary(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
):
    """Headline KPIs for the Compliance dashboard."""
    rows_q = await db.execute(
        select(Compliance).where(Compliance.tenant_id == tenant_id)
    )
    rows = rows_q.scalars().all()

    controls = _extract_controls(list(rows))

    total_controls   = len(controls)
    passing          = sum(1 for c in controls if c["status"] in ("pass", "passing", "compliant"))
    failing          = sum(1 for c in controls if c["status"] in ("fail", "failing", "non_compliant"))
    missing_evidence = sum(1 for c in controls if not c.get("has_evidence") and c["status"] not in ("not_applicable", "na"))
    critical_findings= sum(1 for c in controls if c["severity"] == "critical" and c["status"] in ("fail","failing","non_compliant"))

    # Cross-ref open vulnerabilities/threats as compliance findings
    open_vulns_q = await db.execute(
        select(func.count(Vulnerability.id))
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
    )
    open_vulns = open_vulns_q.scalar() or 0

    open_threats_q = await db.execute(
        select(func.count(Threat.id))
        .where(Threat.tenant_id == tenant_id, Threat.status == "open")
    )
    open_threats = open_threats_q.scalar() or 0

    # Latest assessment from latest scan
    last_scan_q = await db.execute(
        select(Scan.completed_at)
        .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
        .order_by(Scan.completed_at.desc())
        .limit(1)
    )
    last_scan = last_scan_q.scalar_one_or_none()

    avg_score = (
        sum(r.score for r in rows) / len(rows) if rows else 0.0
    )

    # Assets
    assets_q = await db.execute(
        select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
    )
    total_assets = assets_q.scalar() or 0

    # Frameworks breakdown
    compliant_fw = sum(1 for r in rows if r.status in ("compliant", "pass"))
    non_compliant_fw = sum(1 for r in rows if r.status in ("non_compliant", "fail", "failing"))

    return APIResponse(data={
        "overall_score":        round(avg_score, 1),
        "enabled_frameworks":   len(rows),
        "compliant_frameworks": compliant_fw,
        "non_compliant_frameworks": non_compliant_fw,
        "total_controls":       total_controls,
        "passing_controls":     passing,
        "failing_controls":     failing,
        "missing_evidence":     missing_evidence,
        "critical_findings":    critical_findings,
        "open_vulnerabilities": open_vulns,
        "open_threats":         open_threats,
        "total_assets":         total_assets,
        "non_compliant_assets": 0,
        "last_assessment":      last_scan.isoformat() if last_scan else None,
        "open_remediations":    0,
    })


# ── Frameworks ────────────────────────────────────────────────────────────────

@router.get("")
async def list_compliance(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    """Basic list of compliance frameworks (backward-compat with old frontend)."""
    svc = SecurityService(db)
    items = await svc.list_compliance(tenant_id)
    return APIResponse(data=items)


@router.get("/frameworks")
async def list_frameworks(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    """Enriched framework list with per-framework stats and linked policies."""
    rows_q = await db.execute(
        select(Compliance).where(Compliance.tenant_id == tenant_id).order_by(Compliance.framework)
    )
    rows = rows_q.scalars().all()

    # Load policies and index by framework
    policies_q = await db.execute(
        select(SecurityPolicy).where(SecurityPolicy.tenant_id == tenant_id)
    )
    all_policies = policies_q.scalars().all()
    policy_by_framework: dict[str, list[dict]] = {}
    for p in all_policies:
        for fw in (p.frameworks or []):
            policy_by_framework.setdefault(fw, []).append({
                "id": p.id, "name": p.name, "category": p.category,
                "severity": p.severity, "status": p.status,
            })

    result = []
    for r in rows:
        controls = _extract_controls([r])
        na = sum(1 for c in controls if c["status"] in ("not_applicable", "na"))
        result.append({
            "id":            r.id,
            "framework":     r.framework,
            "version":       (r.details[0].get("version") if r.details and isinstance(r.details, list) and r.details else None),
            "score":         round(r.score, 1),
            "passed":        r.passed,
            "failed":        r.failed,
            "not_applicable":na,
            "total":         r.total,
            "status":        r.status,
            "last_assessment": r.updated_at.isoformat() if r.updated_at else None,
            "mapped_policies": policy_by_framework.get(r.framework, []),
            "controls_count": len(controls),
        })

    return APIResponse(data=result)


# ── Controls ──────────────────────────────────────────────────────────────────

@router.get("/controls")
async def list_controls(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    framework: Optional[str] = Query(None),
    severity:  Optional[str] = Query(None),
    status:    Optional[str] = Query(None),
    category:  Optional[str] = Query(None),
    owner:     Optional[str] = Query(None),
    search:    Optional[str] = Query(None),
    evidence:  Optional[str] = Query(None),  # "missing" | "present"
):
    """Paginated, server-side filtered controls table."""
    stmt = select(Compliance).where(Compliance.tenant_id == tenant_id)
    if framework:
        stmt = stmt.where(Compliance.framework == framework)

    rows_q = await db.execute(stmt)
    rows = rows_q.scalars().all()
    controls = _extract_controls(list(rows))

    # Apply filters
    if severity:
        controls = [c for c in controls if c["severity"] == severity.lower()]
    if status:
        controls = [c for c in controls if c["status"] == status.lower()]
    if category:
        controls = [c for c in controls if (c.get("category") or "").lower() == category.lower()]
    if owner:
        controls = [c for c in controls if (c.get("owner") or "").lower() == owner.lower()]
    if evidence == "missing":
        controls = [c for c in controls if not c.get("has_evidence")]
    elif evidence == "present":
        controls = [c for c in controls if c.get("has_evidence")]
    if search:
        s = search.lower()
        controls = [c for c in controls if s in " ".join([
            str(c.get("control_id", "")),
            str(c.get("title", "")),
            str(c.get("framework", "")),
            str(c.get("category", "")),
            str(c.get("owner", "")),
        ]).lower()]

    total = len(controls)
    offset = (page - 1) * page_size
    page_data = controls[offset: offset + page_size]

    return APIResponse(data={
        "data": page_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    })


@router.get("/controls/{control_id}")
async def get_control(
    control_id: str,
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    framework: Optional[str] = Query(None),
):
    """Single control detail with all mapped entities and related findings."""
    stmt = select(Compliance).where(Compliance.tenant_id == tenant_id)
    if framework:
        stmt = stmt.where(Compliance.framework == framework)
    rows_q = await db.execute(stmt)
    rows = rows_q.scalars().all()
    controls = _extract_controls(list(rows))

    ctrl = next((c for c in controls if c.get("id") == control_id or c.get("control_id") == control_id), None)
    if not ctrl:
        return APIResponse(data=None)

    # Enrich: linked findings from threat + vulnerability tables
    threats_q = await db.execute(
        select(Threat)
        .where(Threat.tenant_id == tenant_id, Threat.status == "open")
        .limit(5)
    )
    threats = threats_q.scalars().all()
    ctrl["related_threats"] = [
        {"id": t.id, "title": t.title, "severity": t.severity, "status": t.status}
        for t in threats
    ]

    vulns_q = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        .order_by(Vulnerability.cvss_score.desc().nullslast())
        .limit(5)
    )
    vulns = vulns_q.scalars().all()
    ctrl["related_vulnerabilities"] = [
        {"id": v.id, "title": v.title, "severity": v.severity, "cve_id": v.cve_id, "cvss_score": v.cvss_score}
        for v in vulns
    ]

    # Policies mapped to framework
    policies_q = await db.execute(
        select(SecurityPolicy).where(SecurityPolicy.tenant_id == tenant_id)
    )
    all_policies = policies_q.scalars().all()
    fw = ctrl.get("framework", "")
    ctrl["mapped_policies"] = [
        {"id": p.id, "name": p.name, "category": p.category, "severity": p.severity, "status": p.status}
        for p in all_policies if fw in (p.frameworks or [])
    ]

    return APIResponse(data=ctrl)


# ── Evidence ──────────────────────────────────────────────────────────────────

@router.get("/evidence")
async def list_evidence(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    framework: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Evidence items aggregated from compliance row details.
    Each control with evidence_count > 0 generates evidence entries.
    """
    stmt = select(Compliance).where(Compliance.tenant_id == tenant_id)
    if framework:
        stmt = stmt.where(Compliance.framework == framework)
    rows_q = await db.execute(stmt)
    rows = rows_q.scalars().all()

    evidence_items = []
    for row in rows:
        details = row.details or []
        for ctrl in (details if isinstance(details, list) else []):
            if not isinstance(ctrl, dict):
                continue
            for ev in (ctrl.get("evidence") or []):
                evidence_items.append({
                    "id": ev.get("id", f"{row.id}-{len(evidence_items)}"),
                    "control_id": ctrl.get("control_id"),
                    "framework": row.framework,
                    "source": ev.get("source", "automated"),
                    "collection_time": ev.get("collected_at") or row.updated_at.isoformat(),
                    "collected_by": ev.get("collected_by", "system"),
                    "status": ev.get("status", "verified"),
                    "verification": ev.get("verification", "automated"),
                    "evidence_type": ev.get("type", "log"),
                    "description": ev.get("description"),
                    "download_url": ev.get("download_url"),
                })

        # Also create synthetic scan-based evidence from latest scan
        last_scan_q = await db.execute(
            select(Scan)
            .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
            .order_by(Scan.completed_at.desc())
            .limit(1)
        )
        last_scan = last_scan_q.scalar_one_or_none()
        if last_scan and not any(e.get("framework") == row.framework for e in evidence_items):
            evidence_items.append({
                "id": f"scan-{row.id}",
                "control_id": None,
                "framework": row.framework,
                "source": "security_scanner",
                "collection_time": last_scan.completed_at.isoformat() if last_scan.completed_at else None,
                "collected_by": "system",
                "status": "verified",
                "verification": "automated",
                "evidence_type": "scan_result",
                "description": f"Security scan completed: {last_scan.critical_count} critical, {last_scan.high_count} high findings",
                "download_url": None,
            })

    total = len(evidence_items)
    offset = (page - 1) * page_size
    return APIResponse(data={
        "data": evidence_items[offset: offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    })


# ── Non-compliant Resources ───────────────────────────────────────────────────

@router.get("/resources")
async def list_non_compliant_resources(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Resources with open compliance-related findings.
    Aggregates from Threats + Vulnerabilities to surface non-compliant resources.
    """
    resources: list[dict] = []

    # Assets with open threats
    threats_q = await db.execute(
        select(Threat)
        .where(Threat.tenant_id == tenant_id, Threat.status == "open")
        .order_by(Threat.detected_at.desc())
        .limit(200)
    )
    threats = threats_q.scalars().all()

    seen_resources: set[str] = set()
    for t in threats:
        resource_key = t.resource or t.namespace or t.source
        if not resource_key or resource_key in seen_resources:
            continue
        seen_resources.add(resource_key)

        rtype = (
            "cluster"    if t.namespace else
            "repository" if t.source in ("github", "gitlab", "git") else
            "cloud"      if t.source in ("aws", "azure", "gcp") else
            "container"  if t.source in ("trivy", "grype", "docker") else
            "vm"
        )
        if resource_type and rtype != resource_type:
            continue

        resources.append({
            "id": t.id,
            "resource": resource_key,
            "resource_type": rtype,
            "reason": t.title,
            "severity": t.severity,
            "source": t.source,
            "namespace": t.namespace,
            "related_controls": [],
            "suggested_remediation": f"Investigate and resolve: {t.title}",
            "detected_at": t.detected_at.isoformat() if t.detected_at else None,
            "status": t.status,
        })

    # Repositories with open vulnerabilities
    vulns_q = await db.execute(
        select(Vulnerability.repo_id, func.count(Vulnerability.id), func.max(Vulnerability.cvss_score))
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open", Vulnerability.repo_id.isnot(None))
        .group_by(Vulnerability.repo_id)
        .limit(100)
    )
    for repo_id, vuln_count, max_cvss in vulns_q.fetchall():
        if resource_type and resource_type != "repository":
            continue
        resources.append({
            "id": f"repo-{repo_id}",
            "resource": repo_id,
            "resource_type": "repository",
            "reason": f"{vuln_count} open vulnerabilities (max CVSS: {max_cvss or 'N/A'})",
            "severity": "high" if (max_cvss or 0) >= 7 else "medium",
            "source": "vulnerability_scanner",
            "namespace": None,
            "related_controls": [],
            "suggested_remediation": "Patch all open vulnerabilities",
            "detected_at": None,
            "status": "open",
        })

    total = len(resources)
    offset = (page - 1) * page_size
    return APIResponse(data={
        "data": resources[offset: offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    })


# ── Assessment History ────────────────────────────────────────────────────────

@router.get("/assessments")
async def list_assessments(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Assessment history derived from completed scans + compliance updates."""
    scans_q = await db.execute(
        select(Scan)
        .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
        .order_by(Scan.completed_at.desc())
        .limit(100)
    )
    scans = scans_q.scalars().all()

    # Compliance rows for framework names
    rows_q = await db.execute(select(Compliance).where(Compliance.tenant_id == tenant_id))
    rows = rows_q.scalars().all()
    framework_names = [r.framework for r in rows] or ["General"]

    assessments = []
    for i, scan in enumerate(scans):
        fw = framework_names[i % len(framework_names)]
        total_findings = (scan.critical_count or 0) + (scan.high_count or 0) + (scan.medium_count or 0) + (scan.low_count or 0)
        passed = max(0, total_findings - (scan.critical_count or 0) - (scan.high_count or 0))
        failed = (scan.critical_count or 0) + (scan.high_count or 0)
        score = round((passed / total_findings * 100) if total_findings else 100.0, 1)
        duration_s = (
            (scan.completed_at - scan.started_at).total_seconds()
            if scan.completed_at and scan.started_at else None
        )
        assessments.append({
            "id": scan.id,
            "assessment_date": scan.completed_at.isoformat() if scan.completed_at else None,
            "framework": fw,
            "score": score,
            "passed": passed,
            "failed": failed,
            "evidence_count": total_findings,
            "duration_seconds": duration_s,
            "status": scan.status,
        })

    # Also synthesize per-framework rows from Compliance updated_at
    for row in rows:
        assessments.append({
            "id": f"fw-{row.id}",
            "assessment_date": row.updated_at.isoformat() if row.updated_at else None,
            "framework": row.framework,
            "score": round(row.score, 1),
            "passed": row.passed,
            "failed": row.failed,
            "evidence_count": 0,
            "duration_seconds": None,
            "status": row.status,
        })

    assessments.sort(key=lambda a: a["assessment_date"] or "", reverse=True)
    total = len(assessments)
    offset = (page - 1) * page_size
    return APIResponse(data={
        "data": assessments[offset: offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    })


# ── Exceptions ────────────────────────────────────────────────────────────────

@router.get("/exceptions")
async def list_compliance_exceptions(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Compliance exceptions / waivers from security_exceptions data."""
    from app.models.security_exception import SecurityException
    stmt = select(SecurityException).where(SecurityException.tenant_id == tenant_id)
    exc_q = await db.execute(stmt)
    exceptions = exc_q.scalars().all()

    result = [
        {
            "id": e.id,
            "title": e.title,
            "reason": e.justification,
            "expiration": e.expires_at.isoformat() if e.expires_at else None,
            "owner": e.requested_by,
            "approved_by": e.approved_by,
            "status": e.status,
            "exception_type": e.exception_type,
            "finding_type": e.finding_type,
            "framework": None,
            "control_id": None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in exceptions
    ]

    total = len(result)
    offset = (page - 1) * page_size
    return APIResponse(data={
        "data": result[offset: offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    })


# ── Score (existing) ──────────────────────────────────────────────────────────

@router.get("/score")
async def get_compliance_score(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = SecurityService(db)
    score = await svc.get_compliance_score(tenant_id)
    return APIResponse(data=score)
