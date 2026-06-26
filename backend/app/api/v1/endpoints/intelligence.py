from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_db
from app.services.intelligence.service import IntelligenceService
from app.schemas.intelligence import ProviderHealthSchema, ProviderDetailsSchema, ProviderCapabilitySchema

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

    # Map to Pydantic schema
    return [
        ProviderHealthSchema(
            provider_id=h["provider_id"],
            name=h.get("name", "Unknown"),
            status=h["status"],
            latency_ms=h.get("latency_ms"),
            last_check_at=h["last_check_at"]
        ) for h in health
    ]

@router.get("/providers", response_model=List[ProviderDetailsSchema])
async def get_providers(
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all registered providers with their metadata and capabilities.
    """
    service = IntelligenceService(db)

    # Fetch metadata from DB
    from app.models.intelligence import ProviderMetadata
    from sqlalchemy import select
    result = await db.execute(select(ProviderMetadata))
    metadata_list = result.scalars().all()

    # Fetch real-time health and capabilities from Manager
    manager = service.manager
    health_report = await manager.get_health_report()

    providers_details = []
    for m in metadata_list:
        # Build capability list (stubs currently)
        provider_instance = await manager.get_provider(m.provider_id)
        capabilities = []
        if provider_instance:
            for cap in provider_instance.supported_lookup_types:
                capabilities.append(ProviderCapabilitySchema(
                    provider_id=m.provider_id,
                    capability_type=cap,
                    is_supported=True,
                    confidence_level=1.0
                ))

        providers_details.append(ProviderDetailsSchema(
            provider_id=m.provider_id,
            name=m.name,
            description=m.description,
            version=m.version,
            provider_type="official" if "nvd" in m.provider_id else "community",
            is_active=m.is_active,
            capabilities=capabilities,
            config={}, # Placeholder for DB config
            health=None if m.provider_id not in health_report else ProviderHealthSchema(
                provider_id=m.provider_id,
                name=m.name,
                status=health_report[m.provider_id]["status"],
                latency_ms=health_report[m.provider_id]["latency_ms"],
                last_check_at=health_report[m.provider_id]["last_check_at"]
            )
        ))

    return providers_details

@router.get("/providers/{provider_id}", response_model=ProviderDetailsSchema)
async def get_provider_details(
    provider_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Detailed metadata and configuration for a specific provider.
    """
    service = IntelligenceService(db)

    from app.models.intelligence import ProviderMetadata
    from sqlalchemy import select
    result = await db.execute(select(ProviderMetadata).where(ProviderMetadata.provider_id == provider_id))
    m = result.scalar_one_or_none()

    if not m:
        raise HTTPException(status_code=404, detail="Provider not found")

    manager = service.manager
    provider_instance = await manager.get_provider(provider_id)

    capabilities = []
    if provider_instance:
        for cap in provider_instance.supported_lookup_types:
            capabilities.append(ProviderCapabilitySchema(
                provider_id=m.provider_id,
                capability_type=cap,
                is_supported=True,
                confidence_level=1.0
            ))

    health_report = await manager.get_health_report()

    return ProviderDetailsSchema(
        provider_id=m.provider_id,
        name=m.name,
        description=m.description,
        version=m.version,
        provider_type="official" if "nvd" in m.provider_id else "community",
        is_active=m.is_active,
        capabilities=capabilities,
        config={},
        health=None if m.provider_id not in health_report else ProviderHealthSchema(
            provider_id=m.provider_id,
            name=m.name,
            status=health_report[m.provider_id]["status"],
            latency_ms=health_report[m.provider_id]["latency_ms"],
            last_check_at=health_report[m.provider_id]["last_check_at"]
        )
    )

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
