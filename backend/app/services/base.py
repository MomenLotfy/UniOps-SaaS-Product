from __future__ import annotations
"""
Base service class providing common CRUD helpers and query utilities.
All domain services extend this.
"""
from typing import Any, Optional, Type, TypeVar
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError

ModelT = TypeVar("ModelT")


class BaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_by_id(self, model: Type[ModelT], resource_id: str) -> ModelT:
        result = await self.db.execute(select(model).where(model.id == resource_id))
        obj = result.scalar_one_or_none()
        if obj is None:
            raise NotFoundError(model.__name__, resource_id)
        return obj

    async def _get_or_none(self, model: Type[ModelT], resource_id: str) -> Optional[ModelT]:
        result = await self.db.execute(select(model).where(model.id == resource_id))
        return result.scalar_one_or_none()

    async def _count(self, query) -> int:
        count_q = select(func.count()).select_from(query.subquery())
        result = await self.db.execute(count_q)
        return result.scalar() or 0

    async def _paginate(self, query, page: int, page_size: int) -> list:
        q = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def _soft_delete(self, model: Type[ModelT], resource_id: str) -> None:
        obj = await self._get_by_id(model, resource_id)
        obj.is_active = False
        await self.db.flush()

    async def _update_fields(self, obj: Any, data: dict) -> Any:
        for field, value in data.items():
            if value is not None and hasattr(obj, field):
                setattr(obj, field, value)
        await self.db.flush()
        return obj
