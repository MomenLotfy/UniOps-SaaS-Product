from __future__ import annotations
"""Vulnerabilities API — CVE and container vulnerability management."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.vulnerability import VulnerabilityResponse, VulnerabilityUpdate, VulnerabilityStats
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.security_service import SecurityService

router = APIRouter()


@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_vulnerabilities(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    svc = SecurityService(db)
    result = await svc.list_vulnerabilities(tenant_id, page, page_size, severity, status)
    return APIResponse(data=result)


@router.get("/stats", response_model=APIResponse[VulnerabilityStats])
async def get_vuln_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = SecurityService(db)
    stats = await svc.get_vulnerability_stats(tenant_id)
    return APIResponse(data=stats)


@router.get("/{vuln_id}", response_model=APIResponse[VulnerabilityResponse])
async def get_vulnerability(vuln_id: str, current_user: CurrentUser, db: DBSession):
    svc = SecurityService(db)
    vuln = await svc.get_vulnerability(vuln_id)
    return APIResponse(data=vuln)


@router.patch("/{vuln_id}", response_model=APIResponse[VulnerabilityResponse])
async def update_vulnerability(vuln_id: str, data: VulnerabilityUpdate, current_user: CurrentUser, db: DBSession):
    svc = SecurityService(db)
    vuln = await svc.update_vulnerability(vuln_id, data)
    return APIResponse(data=vuln)
