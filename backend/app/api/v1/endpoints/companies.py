from __future__ import annotations
"""Companies API — tenant profile, settings, stats, and domain verification."""
from fastapi import APIRouter
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.company import TenantUpdate, TenantResponse, TenantStats, DomainVerificationRequest
from app.schemas.common import APIResponse
from app.services.company_service import CompanyService

router = APIRouter()


@router.get("", response_model=APIResponse[TenantResponse])
async def get_company(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = CompanyService(db)
    tenant = await svc.get_by_id(tenant_id)
    return APIResponse(data=tenant)


@router.put("", response_model=APIResponse[TenantResponse])
async def update_company(data: TenantUpdate, current_user: AdminUser, tenant_id: TenantID, db: DBSession):
    svc = CompanyService(db)
    tenant = await svc.update(tenant_id, data)
    return APIResponse(data=tenant)


@router.get("/stats", response_model=APIResponse[TenantStats])
async def get_stats(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = CompanyService(db)
    stats = await svc.get_stats(tenant_id)
    return APIResponse(data=stats)


@router.post("/domain/verify/initiate")
async def initiate_domain_verification(
    data: DomainVerificationRequest, current_user: AdminUser, tenant_id: TenantID, db: DBSession
):
    svc = CompanyService(db)
    result = await svc.initiate_domain_verification(tenant_id, data.domain)
    return APIResponse(data=result)


@router.post("/domain/verify/confirm")
async def confirm_domain_verification(current_user: AdminUser, tenant_id: TenantID, db: DBSession):
    svc = CompanyService(db)
    result = await svc.verify_domain(tenant_id)
    return APIResponse(data=result, message="Domain verified successfully")
