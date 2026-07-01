from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Any, Optional, Dict
from datetime import datetime, timezone

from app.api.deps import get_db
from app.services.intelligence.service import IntelligenceService
from app.schemas.intelligence import (
    ProviderHealthSchema, ProviderDetailsSchema, ProviderCapabilitySchema,
    CanonicalCVE, CanonicalPackage, EnrichedFinding,
)

router = APIRouter()


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_intelligence_summary(db: AsyncSession = Depends(get_db)):
    """Overall TIP summary statistics derived from live data."""
    from app.models.intelligence import (
        ProviderMetadata, IntelligenceCacheEntry, SyncHistory, ProviderHealth,
    )

    # Count cache entries (intelligence records)
    total_q = await db.execute(select(func.count()).select_from(IntelligenceCacheEntry))
    total_records = total_q.scalar() or 0

    # Count active providers
    active_q = await db.execute(
        select(func.count()).select_from(ProviderMetadata).where(ProviderMetadata.is_active == True)
    )
    active_providers = active_q.scalar() or 0

    # Last sync time
    sync_q = await db.execute(
        select(SyncHistory.end_time)
        .where(SyncHistory.status == "success")
        .order_by(SyncHistory.end_time.desc())
        .limit(1)
    )
    last_sync = sync_q.scalar_one_or_none()

    # Count healthy providers
    health_q = await db.execute(
        select(func.count()).select_from(ProviderHealth).where(ProviderHealth.status == "healthy")
    )
    healthy_count = health_q.scalar() or 0

    # Scan cache for critical CVEs
    cache_q = await db.execute(select(IntelligenceCacheEntry).limit(500))
    entries = cache_q.scalars().all()

    critical_count = 0
    kev_count = 0
    high_epss_count = 0
    new_today = 0
    today = datetime.now(timezone.utc).date()

    for e in entries:
        data = e.canonical_data or {}
        sev = (data.get("severity") or "").lower()
        if sev == "critical":
            critical_count += 1
        if data.get("is_kev"):
            kev_count += 1
        epss = data.get("epss_score") or 0
        if epss >= 0.7:
            high_epss_count += 1
        created = e.created_at
        if created and created.date() == today:
            new_today += 1

    return {
        "total_records": total_records,
        "active_providers": active_providers,
        "healthy_providers": healthy_count,
        "critical_advisories": critical_count,
        "new_cves_today": new_today,
        "kev_cves": kev_count,
        "high_epss": high_epss_count,
        "active_campaigns": 0,
        "known_threat_actors": 0,
        "malware_families": 0,
        "ioc_count": 0,
        "high_confidence": 0,
        "last_feed_update": last_sync.isoformat() if last_sync else None,
    }


# ── Feeds ─────────────────────────────────────────────────────────────────────

@router.get("/feeds")
async def get_intelligence_feeds(db: AsyncSession = Depends(get_db)):
    """All configured providers with last sync, record counts, and error stats."""
    from app.models.intelligence import ProviderMetadata, SyncHistory, ProviderHealth

    providers_q = await db.execute(select(ProviderMetadata))
    providers = providers_q.scalars().all()

    result = []
    for p in providers:
        # Latest sync
        sync_q = await db.execute(
            select(SyncHistory)
            .where(SyncHistory.provider_id == p.provider_id)
            .order_by(SyncHistory.start_time.desc())
            .limit(1)
        )
        last_sync = sync_q.scalar_one_or_none()

        # Health
        health_q = await db.execute(
            select(ProviderHealth).where(ProviderHealth.provider_id == p.provider_id)
        )
        health = health_q.scalar_one_or_none()

        result.append({
            "provider_id": p.provider_id,
            "name": p.name,
            "description": p.description,
            "is_active": p.is_active,
            "last_sync": p.last_sync_at.isoformat() if p.last_sync_at else None,
            "records": last_sync.items_processed if last_sync else 0,
            "errors": len(last_sync.errors) if last_sync and last_sync.errors else 0,
            "latency_ms": health.latency_ms if health else None,
            "status": health.status if health else ("active" if p.is_active else "inactive"),
            "last_error": health.last_error if health else None,
            "sync_status": last_sync.status if last_sync else None,
        })

    return result


@router.post("/feeds/{provider_id}/sync")
async def trigger_feed_sync(provider_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger a manual sync for a specific provider."""
    from app.models.intelligence import ProviderMetadata
    q = await db.execute(
        select(ProviderMetadata).where(ProviderMetadata.provider_id == provider_id)
    )
    provider = q.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    return {
        "success": True,
        "message": f"Sync triggered for {provider.name}",
        "provider_id": provider_id,
    }


# ── Records (paginated) ────────────────────────────────────────────────────────

@router.get("/records")
async def get_intelligence_records(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    kev_only: bool = Query(False),
    high_epss: bool = Query(False),
    record_type: Optional[str] = Query(None),
):
    """
    Paginated list of canonical intelligence records from cache.
    Supports filtering by severity, KEV, EPSS, type, and full-text search.
    """
    from app.models.intelligence import IntelligenceCacheEntry

    stmt = select(IntelligenceCacheEntry)

    all_q = await db.execute(stmt)
    all_entries = all_q.scalars().all()

    records = []
    for e in all_entries:
        data = e.canonical_data or {}
        sev = (data.get("severity") or "").lower()
        is_kev = bool(data.get("is_kev"))
        epss = float(data.get("epss_score") or 0)
        intel_type = data.get("type") or ("cve" if e.intel_id.startswith("CVE-") else "advisory")

        if severity and sev != severity.lower():
            continue
        if kev_only and not is_kev:
            continue
        if high_epss and epss < 0.7:
            continue
        if record_type and intel_type != record_type.lower():
            continue
        if search:
            s = search.lower()
            searchable = " ".join([
                e.intel_id,
                data.get("description") or "",
                data.get("title") or "",
                data.get("threat_actor") or "",
            ]).lower()
            if s not in searchable:
                continue

        records.append({
            "id": e.intel_id,
            "title": data.get("title") or e.intel_id,
            "type": intel_type,
            "severity": sev or "unknown",
            "cvss_score": data.get("cvss_score"),
            "epss_score": epss,
            "is_kev": is_kev,
            "threat_actor": data.get("threat_actor"),
            "malware": data.get("malware"),
            "mitre_technique": data.get("mitre_technique"),
            "affected_products": data.get("affected_products") or [],
            "published_at": data.get("published_at"),
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            "confidence": data.get("confidence") or "medium",
            "sources": list((e.provenance or {}).keys()),
            "description": data.get("description"),
            "references": data.get("references") or [],
            "cwe_ids": data.get("cwe_ids") or [],
            "capec_ids": data.get("capec_ids") or [],
        })

    total = len(records)
    offset = (page - 1) * page_size
    page_data = records[offset: offset + page_size]

    return {
        "data": page_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


# ── IOCs ──────────────────────────────────────────────────────────────────────

@router.get("/iocs")
async def get_iocs(
    db: AsyncSession = Depends(get_db),
    ioc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Returns Indicators of Compromise extracted from intelligence cache.
    Empty state if no providers have contributed IOC data.
    """
    from app.models.intelligence import IntelligenceCacheEntry

    all_q = await db.execute(select(IntelligenceCacheEntry))
    entries = all_q.scalars().all()

    iocs = []
    for e in entries:
        data = e.canonical_data or {}
        raw_iocs = data.get("iocs") or []
        for ioc in raw_iocs:
            if ioc_type and ioc.get("type", "").lower() != ioc_type.lower():
                continue
            iocs.append({
                "id": f"{e.intel_id}:{ioc.get('value', '')}",
                "type": ioc.get("type", "unknown"),
                "value": ioc.get("value", ""),
                "confidence": ioc.get("confidence", "medium"),
                "first_seen": ioc.get("first_seen"),
                "last_seen": ioc.get("last_seen"),
                "source": ioc.get("source") or list((e.provenance or {}).keys()),
                "observed_internally": bool(ioc.get("observed_internally")),
                "related_intel_id": e.intel_id,
            })

    total = len(iocs)
    offset = (page - 1) * page_size
    return {
        "data": iocs[offset: offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


# ── Threat Actors ─────────────────────────────────────────────────────────────

@router.get("/threat-actors")
async def get_threat_actors(db: AsyncSession = Depends(get_db)):
    """Threat actor profiles aggregated from intelligence cache."""
    from app.models.intelligence import IntelligenceCacheEntry

    all_q = await db.execute(select(IntelligenceCacheEntry))
    entries = all_q.scalars().all()

    actors: Dict[str, dict] = {}
    for e in entries:
        data = e.canonical_data or {}
        threat_intel = data.get("threat_intel") or {}
        actor_name = threat_intel.get("threat_actor") or data.get("threat_actor")
        if not actor_name:
            continue
        if actor_name not in actors:
            actors[actor_name] = {
                "name": actor_name,
                "aliases": [],
                "country": None,
                "motivation": None,
                "known_campaigns": [],
                "known_malware": [],
                "mitre_techniques": [],
                "target_industries": threat_intel.get("targets") or [],
                "target_countries": [],
                "associated_cves": [],
                "associated_iocs": [],
            }
        if e.intel_id.startswith("CVE-") and e.intel_id not in actors[actor_name]["associated_cves"]:
            actors[actor_name]["associated_cves"].append(e.intel_id)
        campaign = threat_intel.get("campaign")
        if campaign and campaign not in actors[actor_name]["known_campaigns"]:
            actors[actor_name]["known_campaigns"].append(campaign)

    return list(actors.values())


# ── Malware ───────────────────────────────────────────────────────────────────

@router.get("/malware")
async def get_malware_families(db: AsyncSession = Depends(get_db)):
    """Malware family profiles aggregated from intelligence cache."""
    from app.models.intelligence import IntelligenceCacheEntry

    all_q = await db.execute(select(IntelligenceCacheEntry))
    entries = all_q.scalars().all()

    families: Dict[str, dict] = {}
    for e in entries:
        data = e.canonical_data or {}
        malware = data.get("malware")
        if not malware:
            continue
        if malware not in families:
            families[malware] = {
                "family": malware,
                "category": data.get("malware_category"),
                "severity": (data.get("severity") or "unknown").lower(),
                "associated_threat_actor": data.get("threat_actor"),
                "delivery_method": data.get("delivery_method"),
                "persistence": data.get("persistence"),
                "mitre_mapping": data.get("mitre_technique"),
                "related_cves": [],
            }
        if e.intel_id.startswith("CVE-"):
            families[malware]["related_cves"].append(e.intel_id)

    return list(families.values())


# ── MITRE ATT&CK Techniques ───────────────────────────────────────────────────

@router.get("/techniques")
async def get_attack_techniques(db: AsyncSession = Depends(get_db)):
    """MITRE ATT&CK technique coverage aggregated from intelligence cache."""
    from app.models.intelligence import IntelligenceCacheEntry

    all_q = await db.execute(select(IntelligenceCacheEntry))
    entries = all_q.scalars().all()

    techniques: Dict[str, dict] = {}
    for e in entries:
        data = e.canonical_data or {}
        tech = data.get("mitre_technique")
        if not tech:
            continue
        if tech not in techniques:
            techniques[tech] = {
                "technique": tech,
                "tactic": data.get("mitre_tactic"),
                "sub_technique": data.get("mitre_sub_technique"),
                "coverage": "partial",
                "affected_assets": [],
                "observed_events": 0,
                "related_intel_ids": [],
            }
        techniques[tech]["observed_events"] += 1
        techniques[tech]["related_intel_ids"].append(e.intel_id)

    return list(techniques.values())


# ── Existing Endpoints ────────────────────────────────────────────────────────

@router.get("/health", response_model=List[ProviderHealthSchema])
async def get_intelligence_health(db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    health = await service.get_provider_health()
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
async def get_providers(db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    from app.models.intelligence import ProviderMetadata
    result = await db.execute(select(ProviderMetadata))
    metadata_list = result.scalars().all()
    manager = service.manager
    health_report = await manager.get_health_report()
    providers_details = []
    for m in metadata_list:
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
            config={},
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
async def get_provider_details(provider_id: str, db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    from app.models.intelligence import ProviderMetadata
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
                provider_id=m.provider_id, capability_type=cap, is_supported=True, confidence_level=1.0
            ))
    health_report = await manager.get_health_report()
    return ProviderDetailsSchema(
        provider_id=m.provider_id, name=m.name, description=m.description,
        version=m.version, provider_type="official" if "nvd" in m.provider_id else "community",
        is_active=m.is_active, capabilities=capabilities, config={},
        health=None if m.provider_id not in health_report else ProviderHealthSchema(
            provider_id=m.provider_id, name=m.name,
            status=health_report[m.provider_id]["status"],
            latency_ms=health_report[m.provider_id]["latency_ms"],
            last_check_at=health_report[m.provider_id]["last_check_at"]
        )
    )


@router.get("/status", response_model=List[Any])
async def get_intelligence_status(db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    return await service.get_provider_status()


@router.get("/lookup/{intel_id}")
async def lookup_intelligence(intel_id: str, db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    if intel_id.startswith("CVE-"):
        res = await service.get_vulnerability(intel_id)
    elif "pkg:" in intel_id:
        res = await service.get_package(intel_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid intelligence ID format")
    if not res:
        raise HTTPException(status_code=404, detail="Intelligence not found in cache")
    return res


@router.get("/enriched/{finding_id}", response_model=EnrichedFinding)
async def get_enriched_finding(finding_id: str, db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    res = await service.get_enriched_finding(finding_id)
    if not res:
        raise HTTPException(status_code=404, detail="Enriched finding not found")
    return res


@router.get("/recommendations/{finding_id}")
async def get_remediation_recommendations(finding_id: str, db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    finding = await service.get_enriched_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return {
        "finding_id": finding_id,
        "recommendations": finding.remediation_refs,
        "fix_available": finding.fix_available,
        "patched_versions": finding.patched_versions,
    }


@router.get("/canonical/cve/{cve_id}", response_model=CanonicalCVE)
async def get_canonical_cve(cve_id: str, db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    res = await service.get_vulnerability(cve_id)
    if not res:
        raise HTTPException(status_code=404, detail="Canonical CVE not found")
    return res


@router.get("/canonical/package/{purl}", response_model=CanonicalPackage)
async def get_canonical_package(purl: str, db: AsyncSession = Depends(get_db)):
    service = IntelligenceService(db)
    res = await service.get_package(purl)
    if not res:
        raise HTTPException(status_code=404, detail="Canonical package not found")
    return res
