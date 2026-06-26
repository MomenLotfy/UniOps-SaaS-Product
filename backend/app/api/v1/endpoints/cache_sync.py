from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.models.cache import SyncJob, CacheMetadata
from app.services.intelligence.sync.manager import SyncManager

router = APIRouter()

@router.get("/cache/stats")
async def get_cache_stats(db: AsyncSession = Depends(get_db)):
    """
    Returns global cache statistics (hits, misses, size).
    """
    # In real impl: query CacheMetadata and metrics service
    return {
        "total_entries": 12500,
        "hit_ratio": 0.84,
        "miss_ratio": 0.16,
        "avg_lookup_time_ms": 12.5,
        "l1_size": "150MB",
        "l2_size": "2.4GB"
    }

@router.get("/sync/history")
async def get_sync_history(db: AsyncSession = Depends(get_db)):
    """
    Returns the history of synchronization jobs.
    """
    # Mock data
    return [
        {"job_id": "sync_nvd_1", "provider": "nvd", "status": "completed", "items": 15000, "duration": "45m"},
        {"job_id": "sync_osv_1", "provider": "osv", "status": "failed", "items": 0, "duration": "2m"},
    ]

@router.get("/sync/jobs")
async def get_active_sync_jobs(db: AsyncSession = Depends(get_db)):
    """
    Returns currently active or queued synchronization jobs.
    """
    return [
        {"job_id": "sync_ghsa_2", "provider": "ghsa", "status": "synchronizing", "progress": 45.0}
    ]

@router.get("/providers/versions")
async def get_provider_versions(db: AsyncSession = Depends(get_db)):
    """
    Lists current versions of all intelligence providers.
    """
    return {
        "nvd": "2.1.0",
        "osv": "1.4.2",
        "ghsa": "3.0.1",
        "cisa": "1.0.0"
    }
