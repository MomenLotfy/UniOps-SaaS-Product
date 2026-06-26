from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_db
from app.services.intelligence.service import IntelligenceService
from app.schemas.intelligence import ProviderHealthSchema

router = APIRouter()

@router.get("/health", response_model=List[ProviderHealthSchema])
async def get_intelligence_health(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the current health status of all intelligence providers.
    """
    service = IntelligenceService(db)
    health = await service.get_provider_health()

    # Map DB model to Pydantic schema
    return [
        ProviderHealthSchema(
            provider_id=h["provider_id"],
            name=h["provider"].name if hasattr(h.get("provider"), "name") else "Unknown",
            status=h["status"],
            latency_ms=h["latency_ms"],
            last_check_at=h["last_check_at"]
        ) for h in health
    ]

@router.get("/status", response_model=List[Any])
async def get_intelligence_status(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns operational status and versioning for all intelligence providers.
    """
    service = IntelligenceService(db)
    return await service.get_provider_status()

@router.get("/lookup/{intel_id}")
async def lookup_intelligence(
    intel_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Read-only lookup for a specific vulnerability or package ID.
    """
    service = IntelligenceService(db)

    # Determine if it's a CVE or a PURL
    if intel_id.startswith("CVE-"):
        res = await service.get_vulnerability(intel_id)
    elif "pkg:" in intel_id:
        res = await service.get_package(intel_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid intelligence ID format")

    if not res:
        raise HTTPException(status_code=404, detail="Intelligence not found in cache")

    return res
