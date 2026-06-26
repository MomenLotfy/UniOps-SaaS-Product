from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_db
from app.services.impact.engine import RelationshipIntelligenceEngine
from app.schemas.impact import ImpactSummary, BlastRadiusSchema, OwnershipSchema, DependencyChainSchema

router = APIRouter()

@router.get("/impact/{entity_id}", response_model=ImpactSummary)
async def get_impact_analysis(
    entity_id: str,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the full business and technical impact of a specific entity.
    """
    engine = RelationshipIntelligenceEngine(db)
    return await engine.get_full_impact_report(entity_id, tenant_id)

@router.get("/blast-radius/{entity_id}", response_model=BlastRadiusSchema)
async def get_blast_radius(
    entity_id: str,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Calculates the blast radius (immediate and extended) for a vulnerability.
    """
    engine = RelationshipIntelligenceEngine(db)
    return await engine.get_blast_radius(entity_id, tenant_id)

@router.get("/dependencies/{entity_id}", response_model=List[DependencyChainSchema])
async def get_dependencies(
    entity_id: str,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the transitive dependency chains for an entity.
    """
    engine = RelationshipIntelligenceEngine(db)
    return await engine.get_dependency_chains(entity_id, tenant_id)

@router.get("/ownership/{entity_id}", response_model=OwnershipSchema)
async def get_ownership(
    entity_id: str,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Resolves the ownership chain for an asset.
    """
    engine = RelationshipIntelligenceEngine(db)
    owner = await engine.resolve_ownership(entity_id, tenant_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Ownership could not be resolved")
    return owner
