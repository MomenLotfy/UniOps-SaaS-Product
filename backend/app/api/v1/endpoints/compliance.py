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


# ── Policy Mapping ────────────────────────────────────────────────────────────

@router.get("/policy-mapping")
async def get_policy_mapping(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    framework: Optional[str] = Query(None),
):
    """
    Framework → Control → Policy → Finding → Remediation drill-down chain.
    Returns a tree that lets auditors trace every compliance obligation to
    concrete evidence in the environment.
    """
    # Load frameworks
    fw_stmt = select(Compliance).where(Compliance.tenant_id == tenant_id)
    if framework:
        fw_stmt = fw_stmt.where(Compliance.framework == framework)
    rows_q = await db.execute(fw_stmt)
    rows = rows_q.scalars().all()

    # Load all active policies
    policies_q = await db.execute(
        select(SecurityPolicy).where(SecurityPolicy.tenant_id == tenant_id, SecurityPolicy.status == "active")
    )
    all_policies = policies_q.scalars().all()

    # Load open threats
    threats_q = await db.execute(
        select(Threat)
        .where(Threat.tenant_id == tenant_id, Threat.status == "open")
        .order_by(Threat.detected_at.desc())
        .limit(200)
    )
    threats = threats_q.scalars().all()

    # Load open vulnerabilities
    vulns_q = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        .order_by(Vulnerability.cvss_score.desc().nullslast())
        .limit(200)
    )
    vulns = vulns_q.scalars().all()

    # Build per-framework tree
    tree = []
    for row in rows:
        controls = _extract_controls([row])
        fw_node = {
            "framework":      row.framework,
            "framework_id":   row.id,
            "score":          round(row.score, 1),
            "status":         row.status,
            "controls":       [],
        }

        # Policies that mention this framework
        fw_policies = [
            p for p in all_policies if row.framework in (p.frameworks or [])
        ]

        for ctrl in controls[:50]:  # cap per framework
            # Policies for this control (by framework match)
            policy_nodes = []
            for p in fw_policies:
                # Findings linked to this policy (by category/source heuristic)
                finding_nodes: list[dict] = []
                for t in threats:
                    if p.category and p.category.lower() in (t.category or "").lower():
                        finding_nodes.append({
                            "id":       t.id,
                            "type":     "threat",
                            "title":    t.title,
                            "severity": t.severity,
                            "status":   t.status,
                            "source":   t.source,
                            "resource": t.resource,
                            "remediation": {
                                "available": False,
                                "action":    f"Investigate: {t.title}",
                            },
                        })
                for v in vulns:
                    if v.severity in ("critical", "high"):
                        finding_nodes.append({
                            "id":       v.id,
                            "type":     "vulnerability",
                            "title":    v.title,
                            "severity": v.severity,
                            "status":   v.status,
                            "cve_id":   v.cve_id,
                            "cvss":     v.cvss_score,
                            "remediation": {
                                "available":        bool(v.fixed_version),
                                "fixed_version":    v.fixed_version,
                                "action":           f"Upgrade {v.package_name} to {v.fixed_version}" if v.fixed_version else "No fix available",
                            },
                        })

                policy_nodes.append({
                    "id":          p.id,
                    "name":        p.name,
                    "category":    p.category,
                    "severity":    p.severity,
                    "enforcement": p.enforcement,
                    "violations":  p.violations_count,
                    "findings":    finding_nodes[:10],
                    "finding_count": len(finding_nodes),
                })

            fw_node["controls"].append({
                "id":          ctrl.get("id"),
                "control_id":  ctrl.get("control_id"),
                "title":       ctrl.get("title"),
                "category":    ctrl.get("category"),
                "severity":    ctrl.get("severity"),
                "status":      ctrl.get("status"),
                "has_evidence":ctrl.get("has_evidence"),
                "policies":    policy_nodes,
                "policy_count": len(policy_nodes),
            })

        tree.append(fw_node)

    return APIResponse(data=tree)


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/timeline")
async def get_compliance_timeline(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    framework: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Ordered timeline of compliance-relevant events:
    Assessment Started, Evidence Collected, Control Evaluated,
    Violation Detected, Remediation Started, Control Passed, Audit Logged.
    """
    from app.models.audit_log import AuditLog

    events: list[dict] = []

    # Assessment events from scans
    scans_q = await db.execute(
        select(Scan)
        .where(Scan.tenant_id == tenant_id, Scan.status == "completed")
        .order_by(Scan.completed_at.desc())
        .limit(30)
    )
    for scan in scans_q.scalars().all():
        if scan.started_at:
            events.append({
                "type":       "assessment_started",
                "label":      "Assessment Started",
                "description": f"Security scan initiated (branch: {scan.branch or 'default'})",
                "timestamp":  scan.started_at.isoformat(),
                "actor":      scan.triggered_by,
                "severity":   "info",
                "icon":       "play",
            })
        if scan.completed_at:
            events.append({
                "type":       "evidence_collected",
                "label":      "Evidence Collected",
                "description": f"Scan complete — {(scan.critical_count or 0) + (scan.high_count or 0)} critical/high findings",
                "timestamp":  scan.completed_at.isoformat(),
                "actor":      "system",
                "severity":   "critical" if (scan.critical_count or 0) > 0 else "info",
                "icon":       "file-check",
            })
            events.append({
                "type":       "control_evaluated",
                "label":      "Control Evaluated",
                "description": f"Compliance controls re-evaluated after scan",
                "timestamp":  scan.completed_at.isoformat(),
                "actor":      "system",
                "severity":   "info",
                "icon":       "check-square",
            })

    # Violation events from threats
    threats_q = await db.execute(
        select(Threat)
        .where(Threat.tenant_id == tenant_id, Threat.detected_at.isnot(None))
        .order_by(Threat.detected_at.desc())
        .limit(30)
    )
    for t in threats_q.scalars().all():
        events.append({
            "type":       "violation_detected",
            "label":      "Violation Detected",
            "description": t.title,
            "timestamp":  t.detected_at.isoformat() if t.detected_at else None,
            "actor":      t.source,
            "severity":   t.severity,
            "icon":       "alert-triangle",
            "resource":   t.resource,
        })
        if t.resolved_at:
            events.append({
                "type":       "control_passed",
                "label":      "Control Passed",
                "description": f"Threat resolved: {t.title}",
                "timestamp":  t.resolved_at.isoformat(),
                "actor":      "system",
                "severity":   "info",
                "icon":       "check-circle",
            })

    # Compliance row updates
    rows_q = await db.execute(
        select(Compliance).where(Compliance.tenant_id == tenant_id)
    )
    for row in rows_q.scalars().all():
        if framework and row.framework != framework:
            continue
        events.append({
            "type":       "control_evaluated",
            "label":      "Framework Evaluated",
            "description": f"{row.framework} — score: {round(row.score, 1)}%",
            "timestamp":  row.updated_at.isoformat() if row.updated_at else None,
            "actor":      "compliance_engine",
            "severity":   "info" if row.score >= 80 else "medium" if row.score >= 60 else "high",
            "icon":       "shield",
        })

    # Audit log events
    audit_q = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    for log in audit_q.scalars().all():
        events.append({
            "type":       "audit_logged",
            "label":      "Audit Logged",
            "description": f"{log.action} on {log.resource}",
            "timestamp":  log.created_at.isoformat() if log.created_at else None,
            "actor":      log.user_id,
            "severity":   "info",
            "icon":       "file-text",
            "status":     log.status,
        })

    # Sort descending
    events = [e for e in events if e.get("timestamp")]
    events.sort(key=lambda e: e["timestamp"], reverse=True)

    return APIResponse(data=events[:limit])


# ── PDF Export ────────────────────────────────────────────────────────────────

@router.get("/export/pdf")
async def export_compliance_pdf(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    framework: Optional[str] = Query(None, description="Filter to a single framework, or all if omitted"),
):
    """
    Generate a formal compliance audit report PDF.
    Returns a PDF binary response suitable for direct browser download.
    """
    import io
    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether,
    )
    from reportlab.platypus.flowables import BalancedColumns

    # ── Fetch data ────────────────────────────────────────────────────────────

    fw_stmt = select(Compliance).where(Compliance.tenant_id == tenant_id)
    if framework:
        fw_stmt = fw_stmt.where(Compliance.framework == framework)
    rows_q  = await db.execute(fw_stmt)
    rows    = rows_q.scalars().all()

    policies_q  = await db.execute(select(SecurityPolicy).where(SecurityPolicy.tenant_id == tenant_id))
    policies    = policies_q.scalars().all()

    threats_q   = await db.execute(
        select(Threat).where(Threat.tenant_id == tenant_id, Threat.status == "open").limit(200)
    )
    threats = threats_q.scalars().all()

    vulns_q     = await db.execute(
        select(Vulnerability).where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open").limit(200)
    )
    vulns = vulns_q.scalars().all()

    scans_q     = await db.execute(
        select(Scan).where(Scan.tenant_id == tenant_id, Scan.status == "completed")
        .order_by(Scan.completed_at.desc()).limit(10)
    )
    scans = scans_q.scalars().all()

    from app.models.security_exception import SecurityException
    exc_q       = await db.execute(select(SecurityException).where(SecurityException.tenant_id == tenant_id))
    exceptions  = exc_q.scalars().all()

    # ── Computed metrics ──────────────────────────────────────────────────────

    total_score   = round(sum(r.score for r in rows) / len(rows), 1) if rows else 0.0
    total_passed  = sum(r.passed  for r in rows)
    total_failed  = sum(r.failed  for r in rows)
    total_controls= sum(r.total   for r in rows)
    critical_vulns= sum(1 for v in vulns if v.severity == "critical")
    high_vulns    = sum(1 for v in vulns if v.severity == "high")
    last_scan_ts  = scans[0].completed_at.strftime("%Y-%m-%d %H:%M UTC") if scans else "N/A"
    generated_at  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fw_label      = framework if framework else "All Frameworks"
    tenant_email  = current_user.email if hasattr(current_user, "email") else "—"

    # ── Colour palette ────────────────────────────────────────────────────────

    BG_DARK   = colors.HexColor("#0f1117")
    BG_CARD   = colors.HexColor("#1c1e26")
    BORDER    = colors.HexColor("#2a2d38")
    ACCENT    = colors.HexColor("#3b82f6")
    GREEN     = colors.HexColor("#22c55e")
    YELLOW    = colors.HexColor("#eab308")
    RED       = colors.HexColor("#ef4444")
    ORANGE    = colors.HexColor("#f97316")
    TEXT_MAIN = colors.HexColor("#f1f5f9")
    TEXT_MUTED= colors.HexColor("#94a3b8")
    WHITE     = colors.white

    score_color = GREEN if total_score >= 80 else YELLOW if total_score >= 60 else RED

    # ── Styles ────────────────────────────────────────────────────────────────

    styles = getSampleStyleSheet()

    def S(name, **kw):
        base = styles["Normal"]
        return ParagraphStyle(name, parent=base, **kw)

    H1   = S("H1",   fontSize=22, textColor=TEXT_MAIN, spaceAfter=4,  leading=28, fontName="Helvetica-Bold")
    H2   = S("H2",   fontSize=13, textColor=TEXT_MAIN, spaceAfter=6,  leading=18, fontName="Helvetica-Bold")
    H3   = S("H3",   fontSize=10, textColor=ACCENT,    spaceAfter=4,  leading=14, fontName="Helvetica-Bold")
    BODY = S("BODY", fontSize=8,  textColor=TEXT_MAIN, spaceAfter=2,  leading=12)
    MUTED= S("MUTED",fontSize=7,  textColor=TEXT_MUTED,spaceAfter=2,  leading=10)
    CTR  = S("CTR",  fontSize=8,  textColor=TEXT_MUTED,alignment=TA_CENTER)
    BIG  = S("BIG",  fontSize=32, textColor=score_color, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=40)
    COVER_SUB = S("CSUB", fontSize=10, textColor=TEXT_MUTED, spaceAfter=4, alignment=TA_CENTER)

    TH_STYLE = ParagraphStyle("TH", parent=styles["Normal"],
        fontSize=7, textColor=TEXT_MUTED, fontName="Helvetica-Bold",
        leading=10, spaceAfter=0)
    TD_STYLE = ParagraphStyle("TD", parent=styles["Normal"],
        fontSize=7.5, textColor=TEXT_MAIN, leading=11, spaceAfter=0)
    TD_MONO  = ParagraphStyle("TDMONO", parent=styles["Normal"],
        fontSize=7, textColor=ACCENT, fontName="Courier", leading=10)

    def table_style(header_rows=1, zebra=True):
        cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0),          BG_CARD),
            ("TEXTCOLOR",     (0, 0), (-1, 0),          TEXT_MUTED),
            ("FONTNAME",      (0, 0), (-1, 0),          "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),          7),
            ("ROWBACKGROUND", (0, 0), (-1, -1),         BG_DARK),
            ("GRID",          (0, 0), (-1, -1),         0.4, BORDER),
            ("LEFTPADDING",   (0, 0), (-1, -1),         6),
            ("RIGHTPADDING",  (0, 0), (-1, -1),         6),
            ("TOPPADDING",    (0, 0), (-1, -1),         4),
            ("BOTTOMPADDING", (0, 0), (-1, -1),         4),
            ("VALIGN",        (0, 0), (-1, -1),         "MIDDLE"),
        ]
        if zebra:
            cmds.append(("ROWBACKGROUND", (0, 1), (-1, -1), BG_CARD))
        return TableStyle(cmds)

    def badge(text: str, color: colors.Color):
        return Paragraph(
            f'<font color="#{_hex(color)}">[{text.upper()}]</font>',
            ParagraphStyle("badge", parent=styles["Normal"],
                fontSize=6.5, fontName="Helvetica-Bold", leading=9, textColor=color)
        )

    def _hex(c: colors.Color) -> str:
        return "".join(f"{int(x*255):02x}" for x in (c.red, c.green, c.blue))

    def sev_color(sev: str) -> colors.Color:
        return {"critical": RED, "high": ORANGE, "medium": YELLOW, "low": ACCENT, "info": TEXT_MUTED}.get(sev, TEXT_MUTED)

    # ── Document setup ────────────────────────────────────────────────────────

    buf = io.BytesIO()
    PAGE_W, PAGE_H = A4
    MARGIN = 1.8 * cm

    page_num = [0]

    def on_page(canvas, doc):
        page_num[0] += 1
        canvas.saveState()
        # Header bar
        canvas.setFillColor(BG_CARD)
        canvas.rect(0, PAGE_H - 1.1*cm, PAGE_W, 1.1*cm, fill=1, stroke=0)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 0.15*cm, PAGE_W, 0.15*cm, fill=1, stroke=0)
        canvas.setFillColor(TEXT_MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, PAGE_H - 0.75*cm, f"UniOps Compliance Report — {fw_label}")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.75*cm, f"Generated {generated_at}")
        # Footer
        canvas.setFillColor(BG_CARD)
        canvas.rect(0, 0, PAGE_W, 0.9*cm, fill=1, stroke=0)
        canvas.setFillColor(TEXT_MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, 0.35*cm, f"CONFIDENTIAL  ·  {tenant_email}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.35*cm, f"Page {page_num[0]}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.6*cm, bottomMargin=1.2*cm,
    )

    story = []
    W = PAGE_W - 2 * MARGIN

    def section_title(text: str) -> list:
        return [
            Spacer(1, 0.4*cm),
            Paragraph(text, H2),
            HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=6),
        ]

    # ══ COVER PAGE ════════════════════════════════════════════════════════════

    story += [Spacer(1, 2.5*cm)]

    # Logo-like block
    story += [
        Paragraph("🛡 UniOps", S("LOGO", fontSize=24, textColor=ACCENT,
            fontName="Helvetica-Bold", alignment=TA_CENTER, leading=30)),
        Spacer(1, 0.3*cm),
        Paragraph("Compliance Audit Report", H1),
        Spacer(1, 0.2*cm),
        Paragraph(fw_label, COVER_SUB),
        Spacer(1, 1.2*cm),
    ]

    # Score circle (table-simulated)
    cover_tbl = Table([[
        Paragraph(f"{total_score}%", BIG),
    ]], colWidths=[W])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BG_CARD),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 18),
        ("BOTTOMPADDING",(0,0),(-1,-1),18),
        ("ROUNDEDCORNERS",(0,0),(-1,-1), 8),
        ("BOX",        (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story += [cover_tbl, Spacer(1, 0.3*cm)]
    story += [Paragraph("Overall Compliance Score", COVER_SUB), Spacer(1, 1.2*cm)]

    # Cover meta table
    meta_data = [
        [Paragraph("Framework", TH_STYLE), Paragraph("Assessment Date", TH_STYLE),
         Paragraph("Generated By", TH_STYLE), Paragraph("Classification", TH_STYLE)],
        [Paragraph(fw_label, TD_STYLE), Paragraph(last_scan_ts, TD_STYLE),
         Paragraph(tenant_email, TD_STYLE), Paragraph("CONFIDENTIAL", TD_STYLE)],
    ]
    meta_tbl = Table(meta_data, colWidths=[W/4]*4)
    meta_tbl.setStyle(table_style())
    story += [meta_tbl, PageBreak()]

    # ══ EXECUTIVE SUMMARY ════════════════════════════════════════════════════

    story += section_title("Executive Summary")

    kpi_data = [
        ["METRIC", "VALUE", "METRIC", "VALUE"],
        ["Compliance Score",       f"{total_score}%",
         "Enabled Frameworks",     str(len(rows))],
        ["Passing Controls",       str(total_passed),
         "Failing Controls",       str(total_failed)],
        ["Total Controls",         str(total_controls),
         "Pass Rate",              f"{round(total_passed/total_controls*100,1)}%" if total_controls else "—"],
        ["Open Threats",           str(len(threats)),
         "Open Vulnerabilities",   str(len(vulns))],
        ["Critical Vulnerabilities",str(critical_vulns),
         "High Vulnerabilities",   str(high_vulns)],
        ["Active Policies",        str(len(policies)),
         "Compliance Exceptions",  str(len(exceptions))],
        ["Last Assessment",        last_scan_ts,
         "Report Generated",       generated_at],
    ]
    kpi_tbl = Table(
        [[Paragraph(str(c), TH_STYLE if i == 0 else (TD_STYLE if j%2==0 else S("VAL", fontSize=9, textColor=ACCENT, fontName="Helvetica-Bold", leading=12)))
          for j, c in enumerate(row)]
         for i, row in enumerate(kpi_data)],
        colWidths=[W*0.30, W*0.20, W*0.30, W*0.20]
    )
    kpi_tbl.setStyle(table_style())
    story += [kpi_tbl, Spacer(1, 0.5*cm)]

    # Score interpretation
    if total_score >= 80:
        verdict = "COMPLIANT"
        v_color = GREEN
        v_text  = "The organisation meets or exceeds the required compliance thresholds across all evaluated frameworks."
    elif total_score >= 60:
        verdict = "AT RISK"
        v_color = YELLOW
        v_text  = "The organisation partially meets compliance requirements. Remediation is recommended before the next formal assessment."
    else:
        verdict = "NON-COMPLIANT"
        v_color = RED
        v_text  = "The organisation does not meet the minimum compliance thresholds. Immediate remediation is required."

    verdict_tbl = Table([[
        Paragraph(verdict, S("VERDICT", fontSize=14, textColor=v_color,
            fontName="Helvetica-Bold", alignment=TA_CENTER, leading=18)),
        Paragraph(v_text, S("VT", fontSize=8, textColor=TEXT_MAIN, leading=12)),
    ]], colWidths=[W*0.22, W*0.78])
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), BG_CARD),
        ("BOX",           (0,0),(-1,-1), 0.5, v_color),
        ("GRID",          (0,0),(-1,-1), 0, colors.transparent),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story += [verdict_tbl]

    # ══ FRAMEWORK DETAILS ════════════════════════════════════════════════════

    story += section_title("Framework Details")

    fw_header = ["Framework", "Version", "Score", "Passed", "Failed", "N/A", "Status", "Last Assessment"]
    fw_rows   = [[
        Paragraph(r.framework, TD_STYLE),
        Paragraph(r.details[0].get("version","—") if r.details and isinstance(r.details,list) and r.details else "—", TD_STYLE),
        Paragraph(f"{round(r.score,1)}%", S("SC", fontSize=8, fontName="Helvetica-Bold",
            textColor=GREEN if r.score>=80 else YELLOW if r.score>=60 else RED, leading=11)),
        Paragraph(str(r.passed), S("P", fontSize=8, textColor=GREEN, leading=11)),
        Paragraph(str(r.failed), S("F", fontSize=8, textColor=RED,   leading=11)),
        Paragraph(str(max(0, r.total - r.passed - r.failed)), TD_STYLE),
        Paragraph(r.status.upper(), S("ST", fontSize=6.5, textColor=GREEN if "compliant"==r.status else RED, fontName="Helvetica-Bold", leading=9)),
        Paragraph(r.updated_at.strftime("%Y-%m-%d") if r.updated_at else "—", TD_STYLE),
    ] for r in rows]

    fw_tbl = Table(
        [[Paragraph(h, TH_STYLE) for h in fw_header]] + fw_rows,
        colWidths=[W*0.20, W*0.09, W*0.09, W*0.08, W*0.08, W*0.08, W*0.15, W*0.13],
    )
    fw_tbl.setStyle(table_style())
    story += [fw_tbl]

    # ══ CONTROLS SUMMARY ═════════════════════════════════════════════════════

    story += section_title("Controls Summary")

    all_controls = _extract_controls(rows)
    failing_controls = [c for c in all_controls if c.get("status") in ("non_compliant","failing","fail")]
    passing_controls = [c for c in all_controls if c.get("status") in ("compliant","passing","pass")]

    story += [Paragraph(
        f"Total controls evaluated: <b>{len(all_controls)}</b>  ·  "
        f"Passing: <b>{len(passing_controls)}</b>  ·  "
        f"Failing: <b>{len(failing_controls)}</b>",
        BODY
    ), Spacer(1, 0.2*cm)]

    if failing_controls:
        story += [Paragraph("Failing Controls", H3)]
        fail_header = ["Control ID", "Title", "Framework", "Severity", "Evidence"]
        fail_rows   = [[
            Paragraph(c.get("control_id","—"), TD_MONO),
            Paragraph((c.get("title","") or "")[:55], TD_STYLE),
            Paragraph(c.get("framework","—"), TD_STYLE),
            Paragraph(c.get("severity","—").upper(), S("SEV", fontSize=7, fontName="Helvetica-Bold",
                textColor=sev_color(c.get("severity","info")), leading=10)),
            Paragraph("Yes" if c.get("has_evidence") else "No",
                S("EV", fontSize=7, textColor=GREEN if c.get("has_evidence") else RED, leading=10)),
        ] for c in failing_controls[:40]]
        fail_tbl = Table(
            [[Paragraph(h, TH_STYLE) for h in fail_header]] + fail_rows,
            colWidths=[W*0.18, W*0.38, W*0.22, W*0.12, W*0.10],
        )
        fail_tbl.setStyle(table_style())
        story += [fail_tbl]

    # ══ VULNERABILITIES ═══════════════════════════════════════════════════════

    if vulns:
        story += section_title("Open Vulnerabilities (Critical & High)")
        crit_high = [v for v in vulns if v.severity in ("critical","high")][:30]
        if crit_high:
            vul_header = ["CVE ID", "Package", "Severity", "CVSS", "Status", "Fix Available"]
            vul_rows   = [[
                Paragraph(v.cve_id or "—", TD_MONO),
                Paragraph(f"{v.package_name or '—'} {v.package_version or ''}", TD_STYLE),
                Paragraph(v.severity.upper(), S("SEV2", fontSize=7, fontName="Helvetica-Bold",
                    textColor=sev_color(v.severity), leading=10)),
                Paragraph(f"{v.cvss_score:.1f}" if v.cvss_score else "—", TD_STYLE),
                Paragraph(v.status.upper(), TD_STYLE),
                Paragraph(f"→ {v.fixed_version}" if v.fixed_version else "None", TD_STYLE),
            ] for v in crit_high]
            vul_tbl = Table(
                [[Paragraph(h, TH_STYLE) for h in vul_header]] + vul_rows,
                colWidths=[W*0.18, W*0.25, W*0.12, W*0.08, W*0.12, W*0.25],
            )
            vul_tbl.setStyle(table_style())
            story += [vul_tbl]

    # ══ OPEN THREATS ══════════════════════════════════════════════════════════

    if threats:
        story += section_title("Open Threats")
        thr_header = ["Title", "Severity", "Source", "Resource", "Detected"]
        thr_rows   = [[
            Paragraph((t.title or "")[:50], TD_STYLE),
            Paragraph(t.severity.upper(), S("TSEV", fontSize=7, fontName="Helvetica-Bold",
                textColor=sev_color(t.severity), leading=10)),
            Paragraph(t.source or "—", TD_STYLE),
            Paragraph((t.resource or "—")[:35], TD_MONO),
            Paragraph(t.detected_at.strftime("%Y-%m-%d") if t.detected_at else "—", TD_STYLE),
        ] for t in threats[:30]]
        thr_tbl = Table(
            [[Paragraph(h, TH_STYLE) for h in thr_header]] + thr_rows,
            colWidths=[W*0.32, W*0.12, W*0.14, W*0.26, W*0.16],
        )
        thr_tbl.setStyle(table_style())
        story += [thr_tbl]

    # ══ ACTIVE POLICIES ═══════════════════════════════════════════════════════

    if policies:
        story += section_title("Active Policies")
        pol_header = ["Policy Name", "Category", "Severity", "Enforcement", "Violations"]
        pol_rows   = [[
            Paragraph(p.name or "—", TD_STYLE),
            Paragraph(p.category or "—", TD_STYLE),
            Paragraph((p.severity or "—").upper(), S("PSEV", fontSize=7, fontName="Helvetica-Bold",
                textColor=sev_color(p.severity or "info"), leading=10)),
            Paragraph((p.enforcement or "—").upper(), TD_STYLE),
            Paragraph(str(p.violations_count or 0),
                S("VIO", fontSize=8, fontName="Helvetica-Bold",
                  textColor=RED if (p.violations_count or 0)>0 else GREEN, leading=11)),
        ] for p in policies[:30]]
        pol_tbl = Table(
            [[Paragraph(h, TH_STYLE) for h in pol_header]] + pol_rows,
            colWidths=[W*0.32, W*0.18, W*0.12, W*0.18, W*0.20],
        )
        pol_tbl.setStyle(table_style())
        story += [pol_tbl]

    # ══ COMPLIANCE EXCEPTIONS ════════════════════════════════════════════════

    story += section_title("Compliance Exceptions & Waivers")
    if exceptions:
        exc_header = ["Exception", "Type", "Owner", "Approved By", "Expires", "Status"]
        exc_rows   = [[
            Paragraph((e.title or "—")[:45], TD_STYLE),
            Paragraph((e.exception_type or "—").replace("_"," ").title(), TD_STYLE),
            Paragraph((e.requested_by or "—")[:20], TD_STYLE),
            Paragraph((e.approved_by or "—")[:20], TD_STYLE),
            Paragraph(e.expires_at.strftime("%Y-%m-%d") if e.expires_at else "—", TD_STYLE),
            Paragraph((e.status or "—").upper(), S("ESEV", fontSize=7, fontName="Helvetica-Bold",
                textColor=GREEN if e.status=="approved" else YELLOW if e.status=="pending" else RED, leading=10)),
        ] for e in exceptions]
        exc_tbl = Table(
            [[Paragraph(h, TH_STYLE) for h in exc_header]] + exc_rows,
            colWidths=[W*0.28, W*0.15, W*0.15, W*0.15, W*0.12, W*0.15],
        )
        exc_tbl.setStyle(table_style())
        story += [exc_tbl]
    else:
        story += [Paragraph("No compliance exceptions recorded.", MUTED)]

    # ══ RECENT ASSESSMENTS ═══════════════════════════════════════════════════

    if scans:
        story += section_title("Recent Security Assessments")
        scan_header = ["Scan ID", "Branch", "Status", "Critical", "High", "Started", "Completed"]
        scan_rows   = [[
            Paragraph(str(s.id)[:12], TD_MONO),
            Paragraph(s.branch or "default", TD_STYLE),
            Paragraph(s.status.upper(), TD_STYLE),
            Paragraph(str(s.critical_count or 0),
                S("CR", fontSize=8, fontName="Helvetica-Bold", textColor=RED, leading=11)),
            Paragraph(str(s.high_count or 0),
                S("HI", fontSize=8, fontName="Helvetica-Bold", textColor=ORANGE, leading=11)),
            Paragraph(s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "—", TD_STYLE),
            Paragraph(s.completed_at.strftime("%Y-%m-%d %H:%M") if s.completed_at else "—", TD_STYLE),
        ] for s in scans]
        scan_tbl = Table(
            [[Paragraph(h, TH_STYLE) for h in scan_header]] + scan_rows,
            colWidths=[W*0.12, W*0.12, W*0.10, W*0.09, W*0.09, W*0.24, W*0.24],
        )
        scan_tbl.setStyle(table_style())
        story += [scan_tbl]

    # ══ CLOSING ══════════════════════════════════════════════════════════════

    story += [
        PageBreak(),
        Spacer(1, 3*cm),
        Paragraph("End of Compliance Audit Report", S("END", fontSize=11, textColor=TEXT_MUTED,
            alignment=TA_CENTER, fontName="Helvetica-Bold", leading=16)),
        Spacer(1, 0.4*cm),
        Paragraph(f"Generated by UniOps on {generated_at}  ·  {tenant_email}", COVER_SUB),
        Spacer(1, 0.4*cm),
        Paragraph(
            "This report is confidential and intended solely for the authorised recipient. "
            "Redistribution is prohibited without prior written consent.",
            S("DISC", fontSize=7, textColor=TEXT_MUTED, alignment=TA_CENTER, leading=10)),
    ]

    # ── Build ─────────────────────────────────────────────────────────────────

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buf.seek(0)

    safe_name = (framework or "all-frameworks").lower().replace(" ", "-").replace("/", "-")
    filename  = f"compliance-report-{safe_name}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Score (existing) ──────────────────────────────────────────────────────────

@router.get("/score")
async def get_compliance_score(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = SecurityService(db)
    score = await svc.get_compliance_score(tenant_id)
    return APIResponse(data=score)
