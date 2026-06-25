from __future__ import annotations
"""SBOM (Software Bill of Materials) API endpoints."""
from typing import Optional
from fastapi import APIRouter, Query, Response
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.sbom_service import SBOMService
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=APIResponse)
async def list_sboms(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    repo_id:      Optional[str] = Query(None, description="Filter SBOMs by repository"),
):
    """List all SBOMs for the tenant, optionally filtered by repo."""
    svc = SBOMService(db)
    if repo_id:
        data = await svc.list_by_repo(tenant_id, repo_id)
    else:
        data = await svc.list_all(tenant_id)
    return APIResponse(data=data)


@router.get("/{sbom_id}", response_model=APIResponse)
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
    return APIResponse(data=sbom)


@router.get("/{sbom_id}/download")
async def download_sbom(
    sbom_id:      str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Download the raw SBOM JSON file."""
    svc     = SBOMService(db)
    meta    = await svc.get(sbom_id, tenant_id)
    if not meta:
        raise NotFoundError("SBOM", sbom_id)
    content = await svc.get_content(sbom_id, tenant_id)
    if not content:
        raise NotFoundError("SBOM content", sbom_id)

    fmt      = meta["format"]
    filename = f"sbom-{meta['repo_name'].replace('/', '-')}-{fmt}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
