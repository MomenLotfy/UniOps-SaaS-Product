from __future__ import annotations
from typing import Any, Dict, List, Optional, Type
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.logger import logger

class SearchEngine:
    """
    The SearchEngine provides deterministic entity lookup across multiple security domains.
    It maps search terms to the appropriate entity models and fields.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        # Mapping of entity types to their models and searchable fields
        self._entity_map = {}

    def register_entity_type(self, entity_type: str, model: Any, searchable_fields: List[str]):
        """
        Registers a model and its searchable fields for a given entity type.
        """
        self._entity_map[entity_type] = {
            "model": model,
            "fields": searchable_fields
        }

    async def search(self, query: str, entity_types: List[str], limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Performs a case-insensitive search across registered entities.
        """
        logger.info(f"[SearchEngine] Searching for '{query}' in {entity_types}")

        all_results = []

        # Determine which entities to search
        targets = entity_types if entity_types != ["all"] else list(self._entity_map.keys())

        for target in targets:
            if target not in self._entity_map:
                continue

            config = self._entity_map[target]
            model = config["model"]
            fields = config["fields"]

            # Build an OR expression for all searchable fields
            conditions = []
            for field in fields:
                col = getattr(model, field)
                conditions.append(col.ilike(f"%{query}%"))

            stmt = select(model).where(or_(*conditions)).offset(offset).limit(limit)
            result = await self.db.execute(stmt)
            entities = result.scalars().all()

            # Convert entities to a generic dict format
            for entity in entities:
                all_results.append({
                    "entity_id": entity.id,
                    "entity_type": target,
                    "summary": getattr(entity, "name", getattr(entity, "id", "Unknown")),
                    "metadata": {} # Populate with a few key fields if needed
                })

        return all_results

    async def get_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        Provides deterministic search suggestions based on common entity names.
        """
        # In a real system, this would hit a prefix-tree or a dedicated suggestion index
        # For now, we'll return common security terms if the query is short
        suggestions = []

        # Mocking a few deterministic suggestions based on current entity types
        if not partial_query:
            return ["CVE", "Repository", "Asset", "Package", "Team"]

        # Filter the common types
        for t in ["CVE", "Repository", "Asset", "Package", "Team"]:
            if t.lower().startswith(partial_query.lower()):
                suggestions.append(t)

        return suggestions[:limit]
