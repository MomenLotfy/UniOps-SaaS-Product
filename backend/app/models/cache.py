from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class SyncJob(BaseModel):
    """
    Represents a synchronization job for a specific provider.
    """
    __tablename__ = "intelligence_sync_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(100), ForeignKey("intelligence_provider_metadata.provider_id"), index=True)

    # Lifecycle state
    status: Mapped[str] = mapped_column(String(50), default="created") # created, queued, preparing, synchronizing, normalizing, merging, caching, completed, failed, cancelled, paused
    progress: Mapped[float] = mapped_column(Float, default=0.0)

    # Sync Type
    sync_type: Mapped[str] = mapped_column(String(50)) # full, incremental, delta
    checkpoint_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Results
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(JSON)

    provider: Mapped["ProviderMetadata"] = relationship()

# ... (keep other classes) ...

class CacheMetadata(BaseModel):
# ...
class CacheMetadata(BaseModel):
    """
    Tracks metadata and statistics for cached intelligence entities.
    """
    __tablename__ = "intelligence_cache_metadata"

    intel_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Versioning
    cache_version: Mapped[str] = mapped_column(String(50))
    normalization_version: Mapped[str] = mapped_column(String(50))
    merge_version: Mapped[str] = mapped_column(String(50))

    # Policy
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    expiration_type: Mapped[str] = mapped_column(String(50)) # absolute, sliding

    # Stats
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    miss_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class CacheVersion(BaseModel):
    """
    Tracks global cache versions for coordinated invalidation.
    """
    __tablename__ = "intelligence_cache_versions"

    version_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
