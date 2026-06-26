from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_db
from app.services.graph.engine import KnowledgeGraphEngine
from app.schemas.graph import EntitySchema, RelationshipSchema, GraphQueryResponse, GraphStatsSchema

router = APIRouter()

@router.get("/entities", response_model=List[EntitySchema])
async def list_graph_entities(
    entity_type: Optional[str] = None,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Lists graph entities, optionally filtered by type.
    """
    engine = KnowledgeGraphEngine(db)
    if entity_type:
        entities = await engine.repo.find_entities_by_type(entity_type, tenant_id)
    else:
        # In real impl: fetch all
        entities = []

    return [EntitySchema.from_orm(e) for e in entities]

@router.get("/entities/{entity_id}", response_model=EntitySchema)
async def get_graph_entity(
    entity_id: str,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Detailed view of a specific graph node.
    """
    engine = KnowledgeGraphEngine(db)
    entity = await engine.repo.get_entity(entity_id, tenant_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found in graph")
    return EntitySchema.from_orm(entity)

@router.get("/query", response_model=GraphQueryResponse)
async def query_graph(
    cve_id: str,
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Performs a graph traversal to find all assets affected by a CVE.
    """
    engine = KnowledgeGraphEngine(db)
    return await engine.query_impact(cve_id, tenant_id)

@router.get("/statistics", response_model=GraphStatsSchema)
async def get_graph_stats(
    tenant_id: str = "tenant-1",
    db: AsyncSession = Depends(get_db)
):
    """
    Returns graph health and distribution metrics.
    """
    engine = KnowledgeGraphEngine(db)
    return await engine.get_graph_stats(tenant_id)
