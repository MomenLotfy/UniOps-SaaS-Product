from __future__ import annotations
"""
Repository Risk Rating Engine
==============================
Computes a risk score and risk level for each repository after a scan.

Risk Score (0–100, higher = more risky):
  Each factor contributes a weighted penalty capped at a per-factor ceiling.

Factor weights:
  Critical Findings     each +18  (cap 54)
  High Findings         each +7   (cap 35)
  Secrets Detected      each +12  (cap 36)
  Container Issues      each +5   (cap 25)
  Compliance Violations each +6   (cap 24)
  Exposure Risk         0–15 (public repo, stale scan, no auth)

Risk Level thresholds:
  critical  ≥ 75
  high      ≥ 50
  medium    ≥ 25
  low        < 25

Trend: compare current risk_score to the stored previous_risk_score.
  worsening  — score went up   by >5
  improving  — score went down by >5
  stable     — otherwise
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository_risk import RepositoryRiskScore
from app.models.scan import Repository, Scan
from app.models.vulnerability import Vulnerability
from app.utils.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Weights & thresholds
# ─────────────────────────────────────────────────────────────────────────────

_WEIGHTS = {
    "critical":   {"per": 18, "cap": 54},
    "high":       {"per": 7,  "cap": 35},
    "secrets":    {"per": 12, "cap": 36},
    "container":  {"per": 5,  "cap": 25},
    "compliance": {"per": 6,  "cap": 24},
}

_LEVEL_THRESHOLDS = [
    (75, "critical"),
    (50, "high"),
    (25, "medium"),
    (0,  "low"),
]


def _compute_risk_score(
    critical_count:  int,
    high_count:      int,
    secret_count:    int,
    container_count: int,
    compliance_violations: int,
    is_public:       bool,
    days_since_scan: Optional[float],
) -> tuple[float, float, dict]:
    """
    Returns (risk_score, exposure_risk, factor_breakdown).
    """
    factors: dict[str, dict] = {}

    def _penalty(key: str, count: int) -> float:
        w = _WEIGHTS[key]
        return min(count * w["per"], w["cap"])

    p_critical   = _penalty("critical",   critical_count)
    p_high       = _penalty("high",       high_count)
    p_secrets    = _penalty("secrets",    secret_count)
    p_container  = _penalty("container",  container_count)
    p_compliance = _penalty("compliance", compliance_violations)

    # Exposure risk: combination of public visibility + scan staleness
    exposure_risk = 0.0
    if is_public:
        exposure_risk += 5.0
    if days_since_scan is None:
        exposure_risk += 15.0   # never scanned
    elif days_since_scan > 30:
        exposure_risk += 10.0
    elif days_since_scan > 7:
        exposure_risk += 3.0

    raw = p_critical + p_high + p_secrets + p_container + p_compliance + exposure_risk
    risk_score = min(100.0, raw)

    factors = {
        "critical_findings":   {"count": critical_count,        "penalty": p_critical,   "cap": _WEIGHTS["critical"]["cap"]},
        "high_findings":       {"count": high_count,            "penalty": p_high,       "cap": _WEIGHTS["high"]["cap"]},
        "secrets_detected":    {"count": secret_count,          "penalty": p_secrets,    "cap": _WEIGHTS["secrets"]["cap"]},
        "container_issues":    {"count": container_count,       "penalty": p_container,  "cap": _WEIGHTS["container"]["cap"]},
        "compliance_violations":{"count": compliance_violations,"penalty": p_compliance, "cap": _WEIGHTS["compliance"]["cap"]},
        "exposure_risk":       {"is_public": is_public, "days_since_scan": days_since_scan, "penalty": exposure_risk},
    }

    return round(risk_score, 1), round(exposure_risk, 1), factors


def _risk_level(score: float) -> str:
    for threshold, level in _LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return "low"


def _trend(current: float, previous: Optional[float]) -> str:
    if previous is None:
        return "stable"
    delta = current - previous
    if delta > 5:
        return "worsening"
    if delta < -5:
        return "improving"
    return "stable"


# ─────────────────────────────────────────────────────────────────────────────
# RiskService
# ─────────────────────────────────────────────────────────────────────────────

class RiskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_and_store(
        self,
        tenant_id:       str,
        repo_id:         str,
        scan_id:         str,
        scan:            Scan,
        repo:            Repository,
        compliance_violations: int = 0,
    ) -> RepositoryRiskScore:
        """
        Compute and upsert the risk rating for a repository after a scan.
        Pulls open findings count from the vulnerabilities table.
        """
        now = datetime.now(timezone.utc)

        # ── Open findings count ───────────────────────────────────────────────
        from sqlalchemy import func as _func
        open_res = await self.db.execute(
            select(_func.count()).select_from(Vulnerability).where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.repo_id   == repo_id,
                Vulnerability.status    == "open",
            )
        )
        open_findings = open_res.scalar() or 0

        # ── Days since last scan ──────────────────────────────────────────────
        days_since: Optional[float] = None
        if repo.last_scan_at:
            days_since = (now - repo.last_scan_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400

        # ── Compute score ─────────────────────────────────────────────────────
        risk_score, exposure_risk, factors = _compute_risk_score(
            critical_count=       scan.critical_count or 0,
            high_count=           scan.high_count     or 0,
            secret_count=         scan.secret_count   or 0,
            container_count=      scan.misconfig_count or 0,
            compliance_violations=compliance_violations,
            is_public=            not (repo.is_private or True),  # treat as private until we have public flag
            days_since_scan=      days_since,
        )
        level = _risk_level(risk_score)

        # ── Extract owner from repo full_name (org/repo → org) ───────────────
        owner: Optional[str] = None
        if repo.full_name and "/" in repo.full_name:
            owner = repo.full_name.split("/")[0]

        # ── Load existing record for trend + previous values ─────────────────
        existing_res = await self.db.execute(
            select(RepositoryRiskScore).where(
                RepositoryRiskScore.tenant_id == tenant_id,
                RepositoryRiskScore.repo_id   == repo_id,
            )
        )
        existing = existing_res.scalar_one_or_none()

        prev_score = existing.risk_score if existing else None
        prev_level = existing.risk_level if existing else None
        trend      = _trend(risk_score, prev_score)

        if existing:
            await self.db.execute(
                update(RepositoryRiskScore)
                .where(RepositoryRiskScore.repo_id == repo_id)
                .values(
                    scan_id=             scan_id,
                    risk_level=          level,
                    risk_score=          risk_score,
                    trend=               trend,
                    previous_risk_level= prev_level,
                    previous_risk_score= prev_score,
                    critical_count=      scan.critical_count or 0,
                    high_count=          scan.high_count     or 0,
                    secret_count=        scan.secret_count   or 0,
                    container_count=     scan.misconfig_count or 0,
                    compliance_violations=compliance_violations,
                    open_findings=       open_findings,
                    exposure_risk=       exposure_risk,
                    security_score=      scan.security_score,
                    owner=               owner,
                    factors=             factors,
                )
            )
            logger.info(
                f"[risk] Updated risk for repo={repo.full_name} "
                f"score={risk_score} level={level} trend={trend}"
            )
        else:
            record = RepositoryRiskScore(
                tenant_id=            tenant_id,
                repo_id=              repo_id,
                scan_id=              scan_id,
                risk_level=           level,
                risk_score=           risk_score,
                trend=                trend,
                previous_risk_level=  None,
                previous_risk_score=  None,
                critical_count=       scan.critical_count or 0,
                high_count=           scan.high_count     or 0,
                secret_count=         scan.secret_count   or 0,
                container_count=      scan.misconfig_count or 0,
                compliance_violations=compliance_violations,
                open_findings=        open_findings,
                exposure_risk=        exposure_risk,
                security_score=       scan.security_score,
                owner=                owner,
                factors=              factors,
            )
            self.db.add(record)
            logger.info(
                f"[risk] Created risk for repo={repo.full_name} "
                f"score={risk_score} level={level}"
            )

        await self.db.commit()

        # Return refreshed record
        result = await self.db.execute(
            select(RepositoryRiskScore).where(
                RepositoryRiskScore.tenant_id == tenant_id,
                RepositoryRiskScore.repo_id   == repo_id,
            )
        )
        return result.scalar_one()

    async def list_risk_ratings(self, tenant_id: str) -> list[dict]:
        """
        Return all risk ratings for a tenant, joined with repo metadata,
        sorted by risk_score descending (most critical first).
        """
        result = await self.db.execute(
            select(RepositoryRiskScore, Repository)
            .join(Repository, RepositoryRiskScore.repo_id == Repository.id)
            .where(RepositoryRiskScore.tenant_id == tenant_id)
            .order_by(RepositoryRiskScore.risk_score.desc())
        )
        rows = result.all()
        return [_to_risk_dict(rr, repo) for rr, repo in rows]

    async def get_risk_rating(self, tenant_id: str, repo_id: str) -> Optional[dict]:
        result = await self.db.execute(
            select(RepositoryRiskScore, Repository)
            .join(Repository, RepositoryRiskScore.repo_id == Repository.id)
            .where(
                RepositoryRiskScore.tenant_id == tenant_id,
                RepositoryRiskScore.repo_id   == repo_id,
            )
        )
        row = result.first()
        if not row:
            return None
        rr, repo = row
        return _to_risk_dict(rr, repo)


def _to_risk_dict(rr: RepositoryRiskScore, repo: Repository) -> dict:
    return {
        "id":                  rr.id,
        "repo_id":             rr.repo_id,
        "repo_name":           repo.full_name,
        "repo_provider":       repo.provider,
        "repo_language":       repo.language,
        "repo_is_private":     repo.is_private,
        "repo_default_branch": repo.default_branch,
        "scan_id":             rr.scan_id,
        "risk_level":          rr.risk_level,
        "risk_score":          rr.risk_score,
        "trend":               rr.trend,
        "previous_risk_level": rr.previous_risk_level,
        "previous_risk_score": rr.previous_risk_score,
        "critical_count":      rr.critical_count,
        "high_count":          rr.high_count,
        "secret_count":        rr.secret_count,
        "container_count":     rr.container_count,
        "compliance_violations": rr.compliance_violations,
        "open_findings":       rr.open_findings,
        "exposure_risk":       rr.exposure_risk,
        "security_score":      rr.security_score,
        "owner":               rr.owner,
        "factors":             rr.factors or {},
        "last_scan_at":        repo.last_scan_at.isoformat() if repo.last_scan_at else None,
        "last_scan_score":     repo.last_scan_score,
        "updated_at":          rr.updated_at.isoformat(),
    }
