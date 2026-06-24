from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_posture import SecurityPostureScore
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.compliance import Compliance
from app.models.asset import Asset
from app.models.security_policy import SecurityPolicy
from app.schemas.security_posture import SecurityPostureResponse, SecurityPostureSummary
from app.services.base import BaseService
from app.utils.logger import logger


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


class SecurityPostureService(BaseService):

    async def get_summary(self, tenant_id: str) -> SecurityPostureSummary:
        scores = await self._compute_scores(tenant_id)

        # Latest historical snapshot
        history_result = await self.db.execute(
            select(SecurityPostureScore)
            .where(SecurityPostureScore.tenant_id == tenant_id)
            .order_by(SecurityPostureScore.recorded_at.desc())
            .limit(30)
        )
        history = [
            {
                "date": s.recorded_at.isoformat(),
                "overall": s.overall_score,
                "threat": s.threat_score,
                "vulnerability": s.vulnerability_score,
                "compliance": s.compliance_score,
            }
            for s in reversed(history_result.scalars().all())
        ]

        trend = "stable"
        if len(history) >= 2:
            delta = history[-1]["overall"] - history[-2]["overall"]
            trend = "improving" if delta > 1 else ("degrading" if delta < -1 else "stable")

        open_threats = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id, Threat.status == "open")
        )).scalar() or 0
        open_vulns = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        )).scalar() or 0
        critical_assets = (await self.db.execute(
            select(func.count(Asset.id))
            .where(Asset.tenant_id == tenant_id, Asset.is_critical == True)
        )).scalar() or 0
        active_policies = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id, SecurityPolicy.status == "active")
        )).scalar() or 0

        from app.models.security_exception import SecurityException
        pending_exceptions = (await self.db.execute(
            select(func.count(SecurityException.id))
            .where(SecurityException.tenant_id == tenant_id, SecurityException.status == "pending")
        )).scalar() or 0

        return SecurityPostureSummary(
            current_score=scores["overall"],
            trend=trend,
            threat_score=scores["threat"],
            vulnerability_score=scores["vulnerability"],
            compliance_score=scores["compliance"],
            asset_score=scores["asset"],
            policy_score=scores["policy"],
            breakdown=scores["breakdown"],
            history=history,
            open_threats=open_threats,
            open_vulns=open_vulns,
            critical_assets=critical_assets,
            active_policies=active_policies,
            pending_exceptions=pending_exceptions,
        )

    async def get_history(self, tenant_id: str, days: int = 30) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(SecurityPostureScore)
            .where(
                SecurityPostureScore.tenant_id == tenant_id,
                SecurityPostureScore.recorded_at >= cutoff,
            )
            .order_by(SecurityPostureScore.recorded_at.asc())
        )
        return [
            {
                "date": s.recorded_at.isoformat(),
                "overall": s.overall_score,
                "threat": s.threat_score,
                "vulnerability": s.vulnerability_score,
                "compliance": s.compliance_score,
                "asset": s.asset_score,
                "policy": s.policy_score,
            }
            for s in result.scalars().all()
        ]

    async def record_snapshot(self, tenant_id: str) -> SecurityPostureResponse:
        scores = await self._compute_scores(tenant_id)
        snapshot = SecurityPostureScore(
            tenant_id=tenant_id,
            overall_score=scores["overall"],
            threat_score=scores["threat"],
            vulnerability_score=scores["vulnerability"],
            compliance_score=scores["compliance"],
            asset_score=scores["asset"],
            policy_score=scores["policy"],
            breakdown=scores["breakdown"],
            trend="stable",
            recorded_at=datetime.now(timezone.utc),
        )
        self.db.add(snapshot)
        await self.db.flush()
        logger.info(f"[posture:snapshot] tenant={tenant_id[:8]} overall={scores['overall']:.1f}")
        return SecurityPostureResponse.model_validate(snapshot)

    async def _compute_scores(self, tenant_id: str) -> dict:
        # ── Threat Score ─────────────────────────────────────────────────────
        t_total = (await self.db.execute(
            select(func.count(Threat.id)).where(Threat.tenant_id == tenant_id)
        )).scalar() or 0
        t_open = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id, Threat.status.in_(["open", "active"]))
        )).scalar() or 0
        t_crit = (await self.db.execute(
            select(func.count(Threat.id))
            .where(Threat.tenant_id == tenant_id, Threat.severity == "critical", Threat.status.in_(["open", "active"]))
        )).scalar() or 0
        threat_score = _clamp(100 - (t_open * 3) - (t_crit * 7)) if t_total > 0 else 100.0

        # ── Vulnerability Score ───────────────────────────────────────────────
        v_total = (await self.db.execute(
            select(func.count(Vulnerability.id)).where(Vulnerability.tenant_id == tenant_id)
        )).scalar() or 0
        v_open = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        )).scalar() or 0
        v_crit = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.severity == "critical", Vulnerability.status == "open")
        )).scalar() or 0
        vuln_score = _clamp(100 - (v_open * 1.5) - (v_crit * 5)) if v_total > 0 else 100.0

        # ── Compliance Score ──────────────────────────────────────────────────
        comp_result = await self.db.execute(
            select(Compliance.score).where(Compliance.tenant_id == tenant_id)
        )
        scores_list = [r[0] for r in comp_result.all()]
        compliance_score = (sum(scores_list) / len(scores_list)) if scores_list else 0.0

        # ── Asset Score ───────────────────────────────────────────────────────
        a_total = (await self.db.execute(
            select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
        )).scalar() or 0
        a_critical = (await self.db.execute(
            select(func.count(Asset.id))
            .where(Asset.tenant_id == tenant_id, Asset.risk_level == "critical")
        )).scalar() or 0
        asset_score = _clamp(100 - (a_critical / max(a_total, 1)) * 50) if a_total > 0 else 100.0

        # ── Policy Score ──────────────────────────────────────────────────────
        p_total = (await self.db.execute(
            select(func.count(SecurityPolicy.id)).where(SecurityPolicy.tenant_id == tenant_id)
        )).scalar() or 0
        p_active = (await self.db.execute(
            select(func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id, SecurityPolicy.status == "active")
        )).scalar() or 0
        policy_score = (p_active / max(p_total, 1)) * 100 if p_total > 0 else 0.0

        # ── Overall (weighted) ────────────────────────────────────────────────
        overall = _clamp(
            threat_score * 0.30 +
            vuln_score   * 0.25 +
            compliance_score * 0.25 +
            asset_score  * 0.10 +
            policy_score * 0.10
        )

        return {
            "overall": round(overall, 1),
            "threat": round(threat_score, 1),
            "vulnerability": round(vuln_score, 1),
            "compliance": round(compliance_score, 1),
            "asset": round(asset_score, 1),
            "policy": round(policy_score, 1),
            "breakdown": {
                "threats": {"open": t_open, "critical": t_crit, "total": t_total},
                "vulnerabilities": {"open": v_open, "critical": v_crit, "total": v_total},
                "assets": {"total": a_total, "critical_risk": a_critical},
                "policies": {"total": p_total, "active": p_active},
            },
        }
