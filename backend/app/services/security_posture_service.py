from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func, text
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

    async def get_dashboard(self, tenant_id: str, days: int = 30) -> dict:
        """
        Full Security Posture Dashboard payload.
        All scores and trends from real DB aggregations — no synthetic data.
        """
        from app.models.scan import Scan as ScanModel, Repository
        from app.models.k8s_security import K8sScan
        from app.models.asset import Asset
        from app.models.repository_risk import RepositoryRiskScore
        from app.models.repository_risk_history import RepositoryRiskHistory

        now      = datetime.now(timezone.utc)
        cutoff   = now - timedelta(days=days)

        # ── Base scores ────────────────────────────────────────────────────
        scores = await self._compute_scores(tenant_id)

        # Git Security: avg security_score across all completed git scans
        git_score_raw = (await self.db.execute(
            select(func.avg(ScanModel.security_score))
            .join(Repository, ScanModel.repo_id == Repository.id)
            .where(
                ScanModel.tenant_id == tenant_id,
                ScanModel.status == "completed",
                ScanModel.security_score.isnot(None),
                Repository.provider.in_(["github", "gitlab"]),
            )
        )).scalar()
        git_security = round(float(git_score_raw), 1) if git_score_raw is not None else None

        # K8s Security: 100 - avg_risk across completed k8s scans
        k8s_risk_raw = (await self.db.execute(
            select(func.avg(K8sScan.risk_score))
            .where(K8sScan.tenant_id == tenant_id, K8sScan.status == "completed")
        )).scalar()
        k8s_security = round(_clamp(100.0 - float(k8s_risk_raw)), 1) if k8s_risk_raw is not None else None

        # AWS Security: from assets where source='aws'
        aws_total = (await self.db.execute(
            select(func.count(Asset.id))
            .where(Asset.tenant_id == tenant_id, Asset.source == "aws")
        )).scalar() or 0
        if aws_total > 0:
            aws_critical = (await self.db.execute(
                select(func.count(Asset.id))
                .where(
                    Asset.tenant_id == tenant_id,
                    Asset.source == "aws",
                    Asset.risk_level.in_(["critical", "high"]),
                )
            )).scalar() or 0
            aws_security = round(_clamp(100.0 - (aws_critical / aws_total) * 80), 1)
        else:
            aws_security = None

        # Overall Risk: avg risk_score from repository_risk_scores (higher = worse)
        avg_risk_raw = (await self.db.execute(
            select(func.avg(RepositoryRiskScore.risk_score))
            .where(RepositoryRiskScore.tenant_id == tenant_id)
        )).scalar()
        overall_risk = round(float(avg_risk_raw), 1) if avg_risk_raw is not None else 0.0

        # Vuln counts
        open_vulns = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "open")
        )).scalar() or 0
        crit_vulns = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == "critical",
                Vulnerability.status == "open",
            )
        )).scalar() or 0
        resolved_vulns = (await self.db.execute(
            select(func.count(Vulnerability.id))
            .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "resolved")
        )).scalar() or 0

        # ── Trend deltas (7d / 30d / 90d) ────────────────────────────────
        trend_deltas: dict[str, dict] = {}
        for d in [7, 30, 90]:
            window_start = now - timedelta(days=d) - timedelta(hours=12)
            window_end   = now - timedelta(days=d) + timedelta(hours=12)

            past_snap = (await self.db.execute(
                select(SecurityPostureScore)
                .where(
                    SecurityPostureScore.tenant_id   == tenant_id,
                    SecurityPostureScore.recorded_at >= window_start,
                    SecurityPostureScore.recorded_at <= window_end,
                )
                .order_by(SecurityPostureScore.recorded_at.desc())
                .limit(1)
            )).scalar_one_or_none()

            past_risk_raw = (await self.db.execute(
                select(func.avg(RepositoryRiskHistory.risk_score))
                .where(
                    RepositoryRiskHistory.tenant_id   == tenant_id,
                    RepositoryRiskHistory.recorded_at >= window_start,
                    RepositoryRiskHistory.recorded_at <= window_end,
                )
            )).scalar()

            trend_deltas[f"{d}d"] = {
                "overall_security": round(
                    scores["overall"] - (past_snap.overall_score if past_snap else scores["overall"]), 1
                ),
                "compliance": round(
                    scores["compliance"] - (past_snap.compliance_score if past_snap else scores["compliance"]), 1
                ),
                "risk_score": round(
                    overall_risk - (float(past_risk_raw) if past_risk_raw is not None else overall_risk), 1
                ),
                "has_baseline": past_snap is not None or past_risk_raw is not None,
            }

        # ── Risk Trend Chart ──────────────────────────────────────────────
        risk_trend_rows = (await self.db.execute(
            select(
                func.date_trunc("day", RepositoryRiskHistory.recorded_at).label("day"),
                func.avg(RepositoryRiskHistory.risk_score).label("avg_risk"),
                func.max(RepositoryRiskHistory.risk_score).label("max_risk"),
                func.min(RepositoryRiskHistory.risk_score).label("min_risk"),
                func.count(RepositoryRiskHistory.id).label("sample_count"),
            )
            .where(
                RepositoryRiskHistory.tenant_id   == tenant_id,
                RepositoryRiskHistory.recorded_at >= cutoff,
            )
            .group_by(text("1"))
            .order_by(text("1"))
        )).all()
        risk_trend = [
            {
                "date":     row.day.strftime("%Y-%m-%d"),
                "avg_risk": round(float(row.avg_risk), 1),
                "max_risk": round(float(row.max_risk), 1),
                "min_risk": round(float(row.min_risk), 1),
            }
            for row in risk_trend_rows
        ]

        # ── Security Trend Chart ──────────────────────────────────────────
        sec_trend_rows = (await self.db.execute(
            select(SecurityPostureScore)
            .where(
                SecurityPostureScore.tenant_id   == tenant_id,
                SecurityPostureScore.recorded_at >= cutoff,
            )
            .order_by(SecurityPostureScore.recorded_at.asc())
        )).scalars().all()
        security_trend = [
            {
                "date":       s.recorded_at.strftime("%Y-%m-%d"),
                "overall":    s.overall_score,
                "threat":     s.threat_score,
                "vuln":       s.vulnerability_score,
                "compliance": s.compliance_score,
                "asset":      s.asset_score,
            }
            for s in sec_trend_rows
        ]

        # ── Remediation Trend Chart ───────────────────────────────────────
        # Daily snapshot of open critical+high vs medium+low from completed scans
        scan_trend_rows = (await self.db.execute(
            select(
                func.date_trunc("day", ScanModel.completed_at).label("day"),
                func.sum(ScanModel.critical_count + ScanModel.high_count).label("open_crit_high"),
                func.sum(ScanModel.medium_count + ScanModel.low_count).label("open_med_low"),
                func.count(ScanModel.id).label("scans"),
            )
            .where(
                ScanModel.tenant_id   == tenant_id,
                ScanModel.status      == "completed",
                ScanModel.completed_at >= cutoff,
                ScanModel.completed_at.isnot(None),
            )
            .group_by(text("1"))
            .order_by(text("1"))
        )).all()
        remediation_trend = [
            {
                "date":            row.day.strftime("%Y-%m-%d"),
                "open_crit_high":  int(row.open_crit_high or 0),
                "open_med_low":    int(row.open_med_low or 0),
                "scans":           int(row.scans),
            }
            for row in scan_trend_rows
        ]

        return {
            "scores": {
                "overall_risk":      overall_risk,
                "overall_security":  round(float(scores["overall"]), 1),
                "git_security":      git_security,
                "aws_security":      aws_security,
                "k8s_security":      k8s_security,
                "compliance":        round(float(scores["compliance"]), 1),
                "threat":            round(float(scores["threat"]), 1),
                "vuln_score":        round(float(scores["vulnerability"]), 1),
                "open_vulns":        open_vulns,
                "critical_vulns":    crit_vulns,
                "resolved_vulns":    resolved_vulns,
            },
            "trends":           trend_deltas,
            "risk_trend":       risk_trend,
            "security_trend":   security_trend,
            "remediation_trend": remediation_trend,
        }

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
