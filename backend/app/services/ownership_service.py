"""
Ownership management for security findings and assets.
Stores owner/team/department inline on each entity via ALTER TABLE columns,
and maintains the entity's SLA record when ownership changes.
"""
from __future__ import annotations
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.scan import Repository
from app.models.asset import Asset
from app.utils.logger import logger


ENTITY_MODEL = {
    "threat":          Threat,
    "vulnerability":   Vulnerability,
    "repository":      Repository,
    "asset":           Asset,
}


class OwnershipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ownership(self, tenant_id: str, entity_type: str, entity_id: str) -> dict | None:
        model = ENTITY_MODEL.get(entity_type)
        if not model:
            return None
        result = await self.db.execute(
            select(model).where(
                model.tenant_id == tenant_id,
                model.id        == entity_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "entity_type": entity_type,
            "entity_id":   entity_id,
            "owner":       getattr(row, "owner",      None),
            "team":        getattr(row, "team",        None),
            "department":  getattr(row, "department",  None),
        }

    async def set_ownership(
        self,
        tenant_id:   str,
        entity_type: str,
        entity_id:   str,
        owner:       str | None = None,
        team:        str | None = None,
        department:  str | None = None,
    ) -> dict:
        model = ENTITY_MODEL.get(entity_type)
        if not model:
            raise ValueError(f"Unknown entity_type: {entity_type}")

        fields: dict = {}
        if owner      is not None: fields["owner"]      = owner
        if team       is not None: fields["team"]        = team
        if department is not None: fields["department"]  = department

        if fields:
            await self.db.execute(
                update(model)
                .where(model.tenant_id == tenant_id, model.id == entity_id)
                .values(**fields)
            )
            await self.db.commit()

        return await self.get_ownership(tenant_id, entity_type, entity_id) or {}

    async def list_ownership(
        self,
        tenant_id:   str,
        entity_type: str | None = None,
        owner:       str | None = None,
        team:        str | None = None,
        department:  str | None = None,
        limit:       int = 100,
        offset:      int = 0,
    ) -> list[dict]:
        results = []
        models_to_query = (
            [(entity_type, ENTITY_MODEL[entity_type])]
            if entity_type and entity_type in ENTITY_MODEL
            else list(ENTITY_MODEL.items())
        )
        for etype, model in models_to_query:
            q = select(model).where(model.tenant_id == tenant_id)
            if owner:
                q = q.where(model.owner == owner)
            if team:
                q = q.where(model.team == team)
            if department:
                q = q.where(model.department == department)
            q = q.limit(limit).offset(offset)
            rows = (await self.db.execute(q)).scalars().all()
            for row in rows:
                entry: dict = {
                    "entity_type": etype,
                    "entity_id":   row.id,
                    "owner":       getattr(row, "owner",      None),
                    "team":        getattr(row, "team",        None),
                    "department":  getattr(row, "department",  None),
                    "created_at":  row.created_at.isoformat() if row.created_at else None,
                }
                # Extra context per type
                if etype == "threat":
                    entry.update({"title": row.title, "severity": row.severity, "status": row.status})
                elif etype == "vulnerability":
                    entry.update({"title": row.title, "severity": row.severity, "status": row.status, "cve_id": row.cve_id})
                elif etype == "repository":
                    entry.update({"title": row.full_name, "provider": row.provider})
                elif etype == "asset":
                    entry.update({"title": row.name, "type": row.type, "risk_level": row.risk_level})
                results.append(entry)
        return results
