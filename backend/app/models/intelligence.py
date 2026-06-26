from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class ProviderMetadata(BaseModel):
    """
    Configuration and metadata for an intelligence provider.
    """
    __tablename__ = "intelligence_provider_metadata"

    provider_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Connection & Auth
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(500))
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(String(1000))

    # Operational Params
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    refresh_interval_seconds: Mapped[int] = mapped_column(Integer, default=86400) # Default 24h
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class ProviderHealth(BaseModel):
    """
    Real-time health status of intelligence providers.
    """
    __tablename__ = "intelligence_provider_health"

    provider_id: Mapped[str] = mapped_column(String(100), ForeignKey("intelligence_provider_metadata.provider_id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(50), default="healthy") # healthy | degraded | unhealthy
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    last_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(String(2000))

    provider: Mapped["ProviderMetadata"] = relationship()

class IntelligenceCacheEntry(BaseModel):
    """
    The primary cache for normalized intelligence data.
    Stores enriched results for specific vulnerability/package IDs.
    """
    __tablename__ = "intelligence_cache"

    # Unified key (e.g., 'CVE-2024-1234' or 'purl:pkg:npm/express@4.18.2')
    intel_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # The normalized data stored as JSON for flexibility across different intel types
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Source tracking
    providers: Mapped[list] = mapped_column(JSON, default=list) # List of providers that contributed to this entry

    # Cache Lifecycle
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)

class SyncHistory(BaseModel):
    """
    Audit log of synchronization attempts between providers and the cache.
    """
    __tablename__ = "intelligence_sync_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(100), ForeignKey("intelligence_provider_metadata.provider_id"), index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(50)) # success | failed | partial
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[str]] = mapped_column(JSON)

    provider: Mapped["ProviderMetadata"] = relationship()

class IntelligenceVersion(BaseModel):
    """
    Tracks snapshots of intelligence data to allow for historical analysis
    and rollback of "poisoned" or incorrect intel.
    """
    __tablename__ = "intelligence_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    intel_id: Mapped[str] = mapped_column(String(255), ForeignKey("intelligence_cache.intel_id"), index=True)

    data_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    version_tag: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(100)) # e.g. 'system-sync', 'manual-update'

    entry: Mapped["IntelligenceCacheEntry"] = relationship()
