from __future__ import annotations
"""SBOM (Software Bill of Materials) API endpoints."""
from typing import Optional
from fastapi import APIRouter, Query, Response, Body
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.schemas.sbom import (
    SBOMResponse,
    SBOMDetailResponse,
    SBOMListFilter,
    SBOMExportFilter,
    SBOMSummaryStats,
    DependencyTreeResponse,
    EnterprisePackage,
)
from app.services.sbom_service import SBOMService
from app.core.exceptions import NotFoundError
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=APIResponse[dict])
async def list_sboms(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    repo_id:      Optional[str] = Query(None, description="Filter SBOMs by repository"),
    format_filter: Optional[str] = Query(None, description="Filter by format (cyclonedx, spdx)"),
    page:         int = Query(1, ge=1, description="Page number"),
    page_size:    int = Query(50, ge=1, le=100, description="Items per page"),
):
    """List all SBOMs for the tenant, optionally filtered by repo."""
    svc = SBOMService(db)
    if repo_id:
        data = await svc.list_by_repo(tenant_id, repo_id, page=page, page_size=page_size)
    else:
        data = await svc.list_all(tenant_id, page=page, page_size=page_size, format_filter=format_filter)
    return APIResponse(data=data)


@router.get("/summary", response_model=APIResponse[SBOMSummaryStats])
async def get_sbom_summary(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    repo_id:      Optional[str] = Query(None, description="Filter by repository"),
    days:         int = Query(30, ge=7, le=365, description="Days of data to include"),
):
    """Get summary statistics for SBOMs."""
    svc = SBOMService(db)
    stats = await svc.get_summary_stats(tenant_id, repo_id=repo_id, days=days)
    return APIResponse(data=stats)


@router.get("/{sbom_id}", response_model=APIResponse[SBOMDetailResponse])
async def get_sbom(
    sbom_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Get SBOM metadata by ID."""
    svc  = SBOMService(db)
    sbom = await svc.get(sbom_id, tenant_id)
    if not sbom:
        raise NotFoundError("SBOM", sbom_id)

    # Get full content
    content = await svc.get_content(sbom_id, tenant_id)
    meta = sbom.get("meta", {}) or {}
    sbom.update({
        "content": content or "",
        "meta": meta,
    })

    return APIResponse(data=sbom)


@router.get("/{sbom_id}/components", response_model=APIResponse[dict])
async def get_sbom_components(
    sbom_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    page:         int = Query(1, ge=1),
    page_size:    int = Query(100, ge=1, le=500),
    search:       Optional[str] = Query(None, description="Search by name, version, purl"),
    sort_by:      Optional[str] = Query(None, description="Sort by: name, version, risk_score, license"),
    sort_order:   str = Query("asc", description="Sort order: asc, desc"),
):
    """Get components from an SBOM with pagination and filtering."""
    svc = SBOMService(db)
    data = await svc.get_components(
        sbom_id, tenant_id, page=page, page_size=page_size,
        search=search, sort_by=sort_by, sort_order=sort_order
    )
    return APIResponse(data=data)


@router.get("/{sbom_id}/package/{package_name}", response_model=APIResponse[dict])
async def get_package_details(
    sbom_id:      str,
    package_name: str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    package_version: Optional[str] = Query(None, description="Filter by specific version"),
):
    """Get detailed information about a specific package in an SBOM."""
    svc = SBOMService(db)
    details = await svc.get_package_details(sbom_id, tenant_id, package_name, package_version)
    if not details:
        raise NotFoundError("Package", f"{package_name}@{package_version or 'any'}")
    return APIResponse(data=details)


@router.get("/{sbom_id}/dependency-tree", response_model=APIResponse[DependencyTreeResponse])
async def get_dependency_tree(
    sbom_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Get the full dependency tree for an SBOM."""
    svc = SBOMService(db)
    tree = await svc.get_dependency_tree(sbom_id, tenant_id)
    if not tree:
        raise NotFoundError("SBOM", sbom_id)
    return APIResponse(data=tree)


@router.get("/{sbom_id}/download", response_model=APIResponse)
async def download_sbom(
    sbom_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    export_format: str = Query("json", description="Export format: json, cyclonedx, spdx"),
):
    """Download the SBOM content in various formats."""
    svc     = SBOMService(db)
    meta    = await svc.get(sbom_id, tenant_id)
    if not meta:
        raise NotFoundError("SBOM", sbom_id)

    content = await svc.get_content(sbom_id, tenant_id)
    if not content:
        raise NotFoundError("SBOM content", sbom_id)

    # Export in requested format
    export_result = await svc.export_sbom(sbom_id, tenant_id, export_format)
    if not export_result:
        raise NotFoundError("SBOM content", sbom_id)

    filename = export_result["filename"]
    content_type = export_result["content_type"]
    content_str = export_result["content"]

    return Response(
        content=content_str,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{sbom_id}/enterprise-packages", response_model=APIResponse[dict])
async def get_enterprise_packages(
    sbom_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    page:         int = Query(1, ge=1),
    page_size:    int = Query(100, ge=1, le=500),
    search:       Optional[str] = Query(None, description="Search by name"),
    min_risk:     Optional[float] = Query(None, description="Minimum risk score filter"),
    max_vulns:    Optional[int] = Query(None, description="Maximum vulnerability count filter"),
):
    """Get enterprise package table data with risk analysis."""
    svc = SBOMService(db)

    # Get components
    components_result = await svc.get_components(
        sbom_id, tenant_id, page=page, page_size=page_size, search=search
    )
    components = components_result.get("data", [])

    # Build enterprise packages with risk analysis
    packages: list[EnterprisePackage] = []
    for comp in components:
        name = comp.get("name", "")
        version = comp.get("version", "")

        # Get vulnerabilities for this package
        vulns = []  # TODO: Query vulnerabilities table
        risk_score = 0.0
        cvss_max = None
        cves = []
        kev = False

        packages.append(EnterprisePackage(
            id=f"{name}@{version}",
            name=name,
            version=version,
            latest_version=None,  # TODO: Fetch from package registry
            purl=comp.get("purl"),
            cpe=None,  # TODO: Generate CPE
            sha256=None,
            license=comp.get("license"),
            supplier=comp.get("supplier"),
            maintainer=comp.get("maintainer"),
            homepage=comp.get("homepage"),
            repository=comp.get("repository"),
            description=comp.get("description"),
            risk_score=risk_score,
            vulnerability_count=len(vulns),
            cvss_max=cvss_max,
            epss_score=None,  # TODO: Fetch from EPSS
            kev=kev,
            cves=cves,
            dependency_depth=0,  # TODO: Calculate from dependency tree
            dependency_type="direct",
            last_updated=comp.get("timestamp", ""),
        ))

    return APIResponse(data={
        "data": [p.model_dump() for p in packages],
        "total": components_result.get("total", 0),
        "page": page,
        "page_size": page_size,
        "pages": components_result.get("pages", 0),
    })


@router.post("/export", response_model=APIResponse[dict])
async def export_sboms(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    filters:      SBOMExportFilter = Body(...),
):
    """Export SBOMs based on filters."""
    svc = SBOMService(db)

    # Build export based on filters
    if filters.format == "json":
        # Get all SBOMs and export as combined JSON
        sboms = await svc.list_all(tenant_id)
        combined = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "filters": filters.model_dump(),
            "sboms": sboms.get("data", []),
        }
        import io
        output = io.StringIO()
        import json
        json.dump(combined, output, indent=2)

        return APIResponse(data={
            "format": "json",
            "filename": f"sbom-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
            "content": output.getvalue(),
        })

    elif filters.format == "cyclonedx":
        # Export latest SBOM in CycloneDX format
        sboms = await svc.list_all(tenant_id, format_filter="cyclonedx")
        if sboms.get("data"):
            latest = sboms["data"][0]
            content = await svc.get_content(latest["id"], tenant_id)
            return APIResponse(data={
                "format": "cyclonedx",
                "filename": f"sbom-cyclonedx-{latest['repo_name'].replace('/', '-')}.json",
                "content": content or "",
            })

    elif filters.format == "spdx":
        # Export latest SBOM in SPDX format
        sboms = await svc.list_all(tenant_id, format_filter="spdx")
        if sboms.get("data"):
            latest = sboms["data"][0]
            content = await svc.get_content(latest["id"], tenant_id)
            return APIResponse(data={
                "format": "spdx",
                "filename": f"sbom-spdx-{latest['repo_name'].replace('/', '-')}.json",
                "content": content or "",
            })

    return APIResponse(data={"error": "No SBOMs found matching filters"})
