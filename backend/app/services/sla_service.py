"""
SLA tracking for security findings (threats + vulnerabilities).
SLA windows: critical=24h, high=7d, medium=30d, low=90d.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding_sla import FindingSLA, sla_due_at, SLA_HOURS
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.utils.logger import logger


class SLAService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Upsert SLA for a single finding ──────────────────────────────────────

    async def ensure_sla(
        self,
        tenant_id:   str,
        entity_type: str,
        entity_id:   str,
        severity:    str,
        title:       str,
        detected_at: datetime,
        owner:       str | None = None,
        team:        str | None = None,
        department:  str | None = None,
    ) -> FindingSLA:
        existing = (await self.db.execute(
            select(FindingSLA).where(
                FindingSLA.tenant_id   == tenant_id,
                FindingSLA.entity_type == entity_type,
                FindingSLA.entity_id   == entity_id,
            )
        )).scalar_one_or_none()

        due = sla_due_at(severity, detected_at)
        now = datetime.now(timezone.utc)
        is_overdue = now > due

        if existing:
            existing.is_overdue  = is_overdue
            existing.is_breached = existing.is_breached or is_overdue
            if owner:      existing.owner      = owner
            if team:       existing.team        = team
            if department: existing.department  = department
            await self.db.commit()
            return existing

        sla = FindingSLA(
            tenant_id=   tenant_id,
            entity_type= entity_type,
            entity_id=   entity_id,
            severity=    severity.lower(),
            title=       title,
            detected_at= detected_at,
            sla_due_at=  due,
            sla_hours=   SLA_HOURS.get(severity.lower(), 30 * 24),
            is_overdue=  is_overdue,
            is_breached= is_overdue,
            owner=       owner,
            team=        team,
            department=  department,
            status=      "open",
        )
        self.db.add(sla)
        await self.db.commit()
        return sla

    # ── Bulk sync from threats + vulns tables ─────────────────────────────────

    async def sync_findings(self, tenant_id: str) -> dict:
        """
        Pull all open threats + vulns for tenant and upsert SLA records.
        Called by scheduler and on-demand.
        """
        now     = datetime.now(timezone.utc)
        created = 0
        updated = 0

        # Threats
        threats = (await self.db.execute(
            select(Threat).where(
                Threat.tenant_id == tenant_id,
                Threat.status.in_(["open", "active"]),
            )
        )).scalars().all()

        for t in threats:
            detected = t.detected_at or t.created_at or now
            sla = await self.ensure_sla(
                tenant_id=   tenant_id,
                entity_type= "threat",
                entity_id=   t.id,
                severity=    t.severity,
                title=       t.title,
                detected_at= detected,
                owner=       getattr(t, "owner", None),
                team=        getattr(t, "team",  None),
                department=  getattr(t, "department", None),
            )
            if sla.created_at and (now - sla.created_at).total_seconds() < 5:
                created += 1
            else:
                updated += 1

        # Vulnerabilities
        vulns = (await self.db.execute(
            select(Vulnerability).where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.status    == "open",
            )
        )).scalars().all()

        for v in vulns:
            detected = v.first_seen_at or v.created_at or now
            sla = await self.ensure_sla(
                tenant_id=   tenant_id,
                entity_type= "vulnerability",
                entity_id=   v.id,
                severity=    v.severity,
                title=       v.title,
                detected_at= detected,
                owner=       getattr(v, "owner", None),
                team=        getattr(v, "team",  None),
                department=  getattr(v, "department", None),
            )
            if sla.created_at and (now - sla.created_at).total_seconds() < 5:
                created += 1
            else:
                updated += 1

        # Mark resolved SLAs
        await self.db.execute(
            update(FindingSLA)
            .where(
                FindingSLA.tenant_id == tenant_id,
                FindingSLA.status    == "open",
                FindingSLA.entity_type == "threat",
                FindingSLA.entity_id.in_([t.id for t in threats]) == False if threats else True,
            )
            .values(status="resolved", resolved_at=now)
        )

        logger.info(f"[sla:sync] tenant={tenant_id[:8]} created={created} updated={updated}")
        return {"created": created, "updated": updated}

    # ── Refresh overdue flags ─────────────────────────────────────────────────

    async def refresh_overdue(self, tenant_id: str) -> int:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(FindingSLA)
            .where(
                FindingSLA.tenant_id   == tenant_id,
                FindingSLA.status      == "open",
                FindingSLA.sla_due_at  <= now,
                FindingSLA.is_overdue  == False,
            )
            .values(is_overdue=True, is_breached=True)
        )
        await self.db.commit()
        return result.rowcount

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def list_slas(
        self,
        tenant_id:    str,
        severity:     str | None = None,
        status:       str | None = None,
        overdue_only: bool       = False,
        entity_type:  str | None = None,
        limit:        int        = 100,
        offset:       int        = 0,
    ) -> list[dict]:
        q = select(FindingSLA).where(FindingSLA.tenant_id == tenant_id)
        if severity:     q = q.where(FindingSLA.severity    == severity.lower())
        if status:       q = q.where(FindingSLA.status      == status)
        if overdue_only: q = q.where(FindingSLA.is_overdue  == True)
        if entity_type:  q = q.where(FindingSLA.entity_type == entity_type)
        q = q.order_by(FindingSLA.sla_due_at.asc()).limit(limit).offset(offset)
        rows = (await self.db.execute(q)).scalars().all()
        now  = datetime.now(timezone.utc)
        return [_sla_dict(s, now) for s in rows]

    async def get_summary(self, tenant_id: str) -> dict:
        now = datetime.now(timezone.utc)

        total = (await self.db.execute(
            select(func.count(FindingSLA.id)).where(
                FindingSLA.tenant_id == tenant_id, FindingSLA.status == "open"
            )
        )).scalar() or 0

        overdue = (await self.db.execute(
            select(func.count(FindingSLA.id)).where(
                FindingSLA.tenant_id == tenant_id,
                FindingSLA.status    == "open",
                FindingSLA.is_overdue == True,
            )
        )).scalar() or 0

        by_severity: dict[str, dict] = {}
        for sev in ["critical", "high", "medium", "low"]:
            total_s = (await self.db.execute(
                select(func.count(FindingSLA.id)).where(
                    FindingSLA.tenant_id == tenant_id,
                    FindingSLA.severity  == sev,
                    FindingSLA.status    == "open",
                )
            )).scalar() or 0
            over_s = (await self.db.execute(
                select(func.count(FindingSLA.id)).where(
                    FindingSLA.tenant_id  == tenant_id,
                    FindingSLA.severity   == sev,
                    FindingSLA.status     == "open",
                    FindingSLA.is_overdue == True,
                )
            )).scalar() or 0
            by_severity[sev] = {
                "total": total_s, "overdue": over_s,
                "sla_hours": SLA_HOURS[sev],
            }

        # Due in next 24h
        due_soon = (await self.db.execute(
            select(func.count(FindingSLA.id)).where(
                FindingSLA.tenant_id  == tenant_id,
                FindingSLA.status     == "open",
                FindingSLA.is_overdue == False,
                FindingSLA.sla_due_at <= now + timedelta(hours=24),
            )
        )).scalar() or 0

        return {
            "total_open":  total,
            "overdue":     overdue,
            "due_soon_24h": due_soon,
            "by_severity": by_severity,
        }


def _sla_dict(s: FindingSLA, now: datetime) -> dict:
    remaining_h = (s.sla_due_at - now).total_seconds() / 3600 if not s.is_overdue else None
    overdue_h   = (now - s.sla_due_at).total_seconds() / 3600 if s.is_overdue else None
    return {
        "id":           s.id,
        "entity_type":  s.entity_type,
        "entity_id":    s.entity_id,
        "severity":     s.severity,
        "title":        s.title,
        "status":       s.status,
        "detected_at":  s.detected_at.isoformat(),
        "sla_due_at":   s.sla_due_at.isoformat(),
        "sla_hours":    s.sla_hours,
        "is_overdue":   s.is_overdue,
        "is_breached":  s.is_breached,
        "overdue_hours": round(overdue_h, 1) if overdue_h else None,
        "remaining_hours": round(remaining_h, 1) if remaining_h else None,
        "owner":        s.owner,
        "team":         s.team,
        "department":   s.department,
        "resolved_at":  s.resolved_at.isoformat() if s.resolved_at else None,
    }
