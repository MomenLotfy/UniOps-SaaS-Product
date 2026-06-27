import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.base import BaseModel
from app.models.intelligence import ProviderMetadata, ProviderConfiguration, ProviderCapability, ProviderVersion, ProviderHealth, IntelligenceCacheEntry, NormalizationAudit, IntelligenceProvenance, SyncHistory, IntelligenceVersion
from app.models.cache import SyncJob, CacheMetadata, CacheVersion

async def main():
    engine = create_async_engine("postgresql+asyncpg://uniops:uniops_password@db:5432/uniops_db")
    async with engine.begin() as conn:
        # Create all intelligence tables
        await conn.run_sync(BaseModel.metadata.create_all)
        print("Tables created successfully")

if __name__ == "__main__":
    asyncio.run(main())
