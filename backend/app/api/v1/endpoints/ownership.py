"""Ownership management API endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query, Body, HTTPException, BackgroundTasks
from pydantic import BaseModel as PydanticModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.schemas.ownership import (
    OwnershipAssignRequest,
    OwnershipBulkAssignRequest,
    OwnershipImportRequest,
    OwnershipExportFilter,
)
from app.services.ownership_service import OwnershipService
from app.services.user_service import UserService
from app.models.user import User

router = APIRouter()


# ============================================
# Summary Endpoints
# ============================================


@router.get("/summary", response_model=APIResponse)
async def get_ownership_summary(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get ownership summary statistics."""
    svc = OwnershipService(db)
    summary = await svc.get_summary(tenant_id)
    return APIResponse(data=summary)


@router.get("/coverage", response_model=APIResponse)
async def get_ownership_coverage(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get ownership coverage data for charts."""
    svc = OwnershipService(db)
    coverage = await svc.get_coverage_data(tenant_id)
    return APIResponse(data=coverage)


# ============================================
# Owner Profile Endpoints
# ============================================


@router.get("/owner/{owner_name}/profile", response_model=APIResponse)
async def get_owner_profile(
    owner_name: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get detailed profile for a specific owner."""
    svc = OwnershipService(db)
    profile = await svc.get_owner_profile(tenant_id, owner_name)
    return APIResponse(data=profile)


@router.get("/owner/{owner_name}/resources", response_model=APIResponse)
async def get_owner_resources(
    owner_name: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    """Get resources assigned to a specific owner."""
    svc = OwnershipService(db)
    resources = await svc.list_ownership(
        tenant_id=tenant_id,
        owner=owner_name,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return APIResponse(data=resources)


# ============================================
# List and Filter Endpoints
# ============================================


@router.get("", response_model=APIResponse)
async def list_ownership(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    entity_type: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    business_unit: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    cloud_provider: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    is_assigned: Optional[bool] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    """List entities with their ownership metadata, filterable by multiple criteria."""
    svc = OwnershipService(db)
    data = await svc.list_ownership(
        tenant_id=tenant_id,
        entity_type=entity_type,
        owner=owner,
        team=team,
        department=department,
        business_unit=business_unit,
        environment=environment,
        cloud_provider=cloud_provider,
        risk_level=risk_level,
        is_assigned=is_assigned,
        limit=limit,
        offset=offset,
    )
    return APIResponse(data=data)


@router.get("/{entity_type}/{entity_id}", response_model=APIResponse)
async def get_ownership(
    entity_type: str,
    entity_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Get ownership details for a specific entity."""
    svc = OwnershipService(db)
    data = await svc.get_ownership(tenant_id, entity_type, entity_id)
    if not data:
        raise HTTPException(status_code=404, detail="Ownership not found")
    return APIResponse(data=data)


# ============================================
# Create/Update Endpoints
# ============================================


@router.patch("/{entity_type}/{entity_id}", response_model=APIResponse)
async def set_ownership(
    entity_type: str,
    entity_id: str,
    body: OwnershipAssignRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    """Set owner, team, and/or department for any security entity."""
    svc = OwnershipService(db)
    data = await svc.set_ownership(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        owner=body.owner,
        owner_type=body.owner_type,
        team=body.team,
        department=body.department,
        business_unit=body.business_unit,
        backup_owner=body.backup_owner,
        escalation_chain=body.escalation_chain,
        business_criticality=body.business_criticality,
        environment=body.environment,
        risk_level=body.risk_level,
        cloud_provider=body.cloud_provider,
        cloud_account_id=body.cloud_account_id,
        cluster_name=body.cluster_name,
        namespace=body.namespace,
        region=body.region,
        updated_by=current_user.id,
    )
    return APIResponse(data=data, message="Ownership updated")


# ============================================
# Bulk Operations
# ============================================


@router.post("/bulk-assign", response_model=APIResponse)
async def bulk_assign_ownership(
    body: OwnershipBulkAssignRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Bulk assign ownership to multiple entities."""
    svc = OwnershipService(db)
    count = await svc.bulk_assign_ownership(
        tenant_id=tenant_id,
        entity_type=body.entity_type,
        entity_ids=body.entity_ids,
        owner=body.owner,
        owner_type=body.owner_type,
        team=body.team,
        department=body.department,
        business_unit=body.business_unit,
        business_criticality=body.business_criticality,
        environment=body.environment,
        risk_level=body.risk_level,
        updated_by=current_user.id,
    )
    return APIResponse(
        data={"assigned": count},
        message=f"Bulk assigned ownership to {count} entities",
    )


# ============================================
# Import/Export Endpoints
# ============================================


@router.post("/import", response_model=APIResponse)
async def import_ownership(
    body: OwnershipImportRequest,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    """Import ownership mappings from CSV content."""
    svc = OwnershipService(db)
    result = await svc.import_ownership(
        tenant_id=tenant_id,
        csv_content=body.content,
        mapping_type=body.mapping_type,
    )
    if result["failures"] > 0:
        return APIResponse(data=result, message=f"Import completed with {result['failures']} errors")
    return APIResponse(data=result, message="Import completed successfully")


@router.get("/export", response_model=APIResponse)
async def export_ownership(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    filters: OwnershipExportFilter = Depends(),
):
    """Export ownership mappings as CSV."""
    svc = OwnershipService(db)
    csv_content = await svc.export_ownership(
        tenant_id=tenant_id,
        filters=filters.model_dump(exclude_none=True),
    )

    # Return as download
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="ownership_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"',
        },
    )


# ============================================
# Audit Log Endpoints
# ============================================


@router.get("/{entity_type}/{entity_id}/audit", response_model=APIResponse)
async def get_entity_audit_logs(
    entity_type: str,
    entity_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """Get audit history for a specific entity."""
    svc = OwnershipService(db)
    logs = await svc.get_audit_logs(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
    return APIResponse(data=logs)


@router.get("/audit", response_model=APIResponse)
async def get_audit_logs(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    owner: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """Get ownership audit logs with filters."""
    svc = OwnershipService(db)
    logs = await svc.get_audit_logs(
        tenant_id=tenant_id,
        owner=owner,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return APIResponse(data=logs)


# ============================================
# Auto-Assignment Endpoints
# ============================================


@router.post("/defaults", response_model=APIResponse)
async def set_ownership_default(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    entity_type: str = Body(...),
    owner: str = Body(...),
    team: Optional[str] = Body(None),
    department: Optional[str] = Body(None),
):
    """Set default ownership for a resource type."""
    # TODO: Implement ownership defaults with rule-based assignment
    return APIResponse(
        data={"message": "Default ownership not yet implemented"},
        message="Feature not yet implemented",
    )


# ============================================
# Resource Type Details
# ============================================


@router.get("/resource-types", response_model=APIResponse)
async def get_resource_types(
    current_user: CurrentUser,
):
    """Get list of supported resource types."""
    from app.models.ownership import RESOURCE_TYPES

    return APIResponse(data=RESOURCE_TYPES)


@router.get("/owner-types", response_model=APIResponse)
async def get_owner_types(
    current_user: CurrentUser,
):
    """Get list of supported owner types."""
    from app.models.ownership import OWNER_TYPES

    return APIResponse(data=list(OWNER_TYPES))
