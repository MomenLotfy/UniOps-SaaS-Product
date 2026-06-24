from __future__ import annotations
"""
Asset Inventory API
===================
GET    /assets                 — list assets with filters + pagination
GET    /assets/stats           — summary counts by type / risk / env
GET    /assets/sync/status     — last sync metadata per source
POST   /assets/sync            — trigger full background sync
POST   /assets/sync/{source}   — trigger single-source sync
GET    /assets/{id}            — asset detail + relationships
PATCH  /assets/{id}            — update owner / environment / tags
DELETE /assets/{id}            — soft-delete (status=decommissioned)
"""
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Body, BackgroundTasks, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from pydantic import BaseModel as PydanticModel

from app.api.deps import CurrentUser, TenantID, DBSession
from app.models.asset import Asset, AssetRelationship
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.asset_discovery_service import AssetDiscoveryService
from app.utils.logger import logger

router = APIRouter()

VALID_SOURCES = {"github", "gitlab", "aws", "kubernetes", "docker"}

# ── Background sync state tracker (in-memory; replace with Redis for multi-pod)
_SYNC_STATE: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
# List / Stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=APIResponse[PaginatedResponse])
async def list_assets(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    asset_type: Optional[str] = Query(None, alias="type"),
    source: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="active|inactive|decommissioned"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("risk_level", description="risk_level|name|type|last_synced_at"),
    sort_dir: str = Query("desc"),
):
    query = select(Asset).where(Asset.tenant_id == tenant_id, Asset.status != "decommissioned")

    if asset_type:
        query = query.where(Asset.type == asset_type)
    if source:
        query = query.where(Asset.source == source)
    if environment:
        query = query.where(Asset.environment == environment)
    if risk_level:
        query = query.where(Asset.risk_level == risk_level)
    if status:
        query = query.where(Asset.status == status)
    if search:
        query = query.where(Asset.name.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
    SORT_COLUMNS = {
        "name": Asset.name,
        "type": Asset.type,
        "environment": Asset.environment,
        "last_synced_at": Asset.last_synced_at,
        "last_scanned_at": Asset.last_scanned_at,
        "open_findings": Asset.open_findings,
    }
    if sort_by in SORT_COLUMNS:
        col = SORT_COLUMNS[sort_by]
        query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())
    else:
        query = query.order_by(Asset.open_findings.desc(), Asset.last_synced_at.desc())

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    assets = result.scalars().all()

    # Attach relationship counts
    asset_ids = [a.id for a in assets]
    rel_counts: dict[str, int] = {}
    if asset_ids:
        rc_result = await db.execute(
            select(
                AssetRelationship.source_asset_id,
                func.count().label("cnt"),
            ).where(
                AssetRelationship.source_asset_id.in_(asset_ids)
            ).group_by(AssetRelationship.source_asset_id)
        )
        for row in rc_result:
            rel_counts[row.source_asset_id] = row.cnt
        rc2_result = await db.execute(
            select(
                AssetRelationship.target_asset_id,
                func.count().label("cnt"),
            ).where(
                AssetRelationship.target_asset_id.in_(asset_ids)
            ).group_by(AssetRelationship.target_asset_id)
        )
        for row in rc2_result:
            rel_counts[row.target_asset_id] = rel_counts.get(row.target_asset_id, 0) + row.cnt

    data = []
    for a in assets:
        d = a.to_dict()
        d["relationship_count"] = rel_counts.get(a.id, 0)
        data.append(d)

    return APIResponse(data=PaginatedResponse(
        data=data, total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    ))


@router.get("/stats")
async def get_asset_stats(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    base = select(Asset).where(Asset.tenant_id == tenant_id, Asset.status != "decommissioned")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    by_type_result = await db.execute(
        select(Asset.type, func.count().label("cnt"))
        .where(Asset.tenant_id == tenant_id, Asset.status != "decommissioned")
        .group_by(Asset.type)
    )
    by_type = {row.type: row.cnt for row in by_type_result}

    by_risk_result = await db.execute(
        select(Asset.risk_level, func.count().label("cnt"))
        .where(Asset.tenant_id == tenant_id, Asset.status != "decommissioned")
        .group_by(Asset.risk_level)
    )
    by_risk = {row.risk_level: row.cnt for row in by_risk_result}

    by_env_result = await db.execute(
        select(Asset.environment, func.count().label("cnt"))
        .where(Asset.tenant_id == tenant_id, Asset.status != "decommissioned")
        .group_by(Asset.environment)
    )
    by_env = {row.environment: row.cnt for row in by_env_result}

    by_source_result = await db.execute(
        select(Asset.source, func.count().label("cnt"))
        .where(Asset.tenant_id == tenant_id, Asset.status != "decommissioned")
        .group_by(Asset.source)
    )
    by_source = {row.source: row.cnt for row in by_source_result}

    critical_assets = (await db.execute(
        select(func.count()).where(
            Asset.tenant_id == tenant_id,
            Asset.risk_level == "critical",
            Asset.status != "decommissioned",
        )
    )).scalar() or 0

    return APIResponse(data={
        "total": total,
        "critical_assets": critical_assets,
        "by_type": by_type,
        "by_risk": by_risk,
        "by_environment": by_env,
        "by_source": by_source,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Sync
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sync/status")
async def get_sync_status(current_user: CurrentUser, tenant_id: TenantID):
    state = _SYNC_STATE.get(tenant_id, {})
    return APIResponse(data={
        "running": state.get("running", False),
        "last_sync_at": state.get("last_sync_at"),
        "last_result": state.get("last_result"),
        "error": state.get("error"),
    })


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync_all(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    if _SYNC_STATE.get(tenant_id, {}).get("running"):
        raise HTTPException(status_code=409, detail="sync_already_running")

    _SYNC_STATE[tenant_id] = {"running": True, "last_sync_at": None, "error": None}
    logger.info(f"[assets:sync] tenant={tenant_id[:8]} trigger=all user={current_user['user_id'][:8]}")
    background_tasks.add_task(_run_sync, tenant_id, None, db)
    return APIResponse(data={"queued": True, "source": "all"}, message="Asset sync started")


@router.post("/sync/{source}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync_source(
    source: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    if source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source. Valid: {', '.join(VALID_SOURCES)}")

    sync_key = f"{tenant_id}:{source}"
    if _SYNC_STATE.get(sync_key, {}).get("running"):
        raise HTTPException(status_code=409, detail="sync_already_running")

    _SYNC_STATE[sync_key] = {"running": True, "last_sync_at": None, "error": None}
    logger.info(f"[assets:sync] tenant={tenant_id[:8]} source={source} user={current_user['user_id'][:8]}")
    background_tasks.add_task(_run_sync, tenant_id, source, db)
    return APIResponse(data={"queued": True, "source": source}, message=f"Asset sync started for {source}")


# ─────────────────────────────────────────────────────────────────────────────
# Detail / Update / Delete
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    rel_result = await db.execute(
        select(AssetRelationship, Asset).join(
            Asset, Asset.id == AssetRelationship.target_asset_id,
        ).where(
            AssetRelationship.source_asset_id == asset_id,
        )
    )
    outgoing = [
        {**rel.to_dict(), "target": target.to_dict()}
        for rel, target in rel_result
    ]

    rel_result2 = await db.execute(
        select(AssetRelationship, Asset).join(
            Asset, Asset.id == AssetRelationship.source_asset_id,
        ).where(
            AssetRelationship.target_asset_id == asset_id,
        )
    )
    incoming = [
        {**rel.to_dict(), "source": src.to_dict()}
        for rel, src in rel_result2
    ]

    d = asset.to_dict()
    d["relationships"] = {"outgoing": outgoing, "incoming": incoming}
    return APIResponse(data=d)


class AssetUpdate(PydanticModel):
    owner: Optional[str] = None
    team: Optional[str] = None
    environment: Optional[str] = None
    risk_level: Optional[str] = None
    is_critical: Optional[bool] = None
    tags: Optional[dict] = None
    description: Optional[str] = None


@router.patch("/{asset_id}")
async def update_asset(
    asset_id: str,
    data: AssetUpdate,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    update_dict = data.model_dump(exclude_none=True)
    for k, v in update_dict.items():
        setattr(asset, k, v)
    asset.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return APIResponse(data=asset.to_dict())


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: DBSession,
):
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.status = "decommissioned"
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Background task
# ─────────────────────────────────────────────────────────────────────────────

async def _run_sync(tenant_id: str, source: str | None, db) -> None:
    state_key = f"{tenant_id}:{source}" if source else tenant_id
    try:
        from app.core.database import get_db as _get_db
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            svc = AssetDiscoveryService(session)
            if source:
                result = await svc.sync_source(tenant_id, source)
            else:
                result = await svc.sync_all(tenant_id)
            await session.commit()

        _SYNC_STATE[state_key] = {
            "running": False,
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "last_result": result,
            "error": None,
        }
        logger.info(f"[assets:sync:done] tenant={tenant_id[:8]} result={result}")

    except Exception as exc:
        logger.error(f"[assets:sync:error] tenant={tenant_id[:8]} error={exc}")
        _SYNC_STATE[state_key] = {
            "running": False,
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "last_result": None,
            "error": str(exc)[:300],
        }
