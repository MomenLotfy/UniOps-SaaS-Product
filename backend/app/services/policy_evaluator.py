"""
Policy Evaluation Engine
========================
Evaluates active security policies against scan findings.
Built-in rules:
  - no_secrets            : any secret/credential finding → violation
  - block_critical_cves   : any critical CVE → violation (enforce = block)
  - require_signed_images : unsigned container image → violation
  - require_mfa           : missing MFA finding → violation
  - require_private_repos : public repository → violation
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_policy import SecurityPolicy
from app.models.security_exception import SecurityException
from app.models.policy_violation import PolicyViolation
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.scan import Repository, Scan
from app.models.repository_risk import RepositoryRiskScore
from app.models.security_posture import SecurityPostureScore
from app.utils.logger import logger


# ─── Built-in policy templates ───────────────────────────────────────────────

BUILTIN_POLICIES: list[dict] = [
    {
        "name":        "No Secrets Allowed",
        "policy_type": "no_secrets",
        "category":    "secrets",
        "severity":    "critical",
        "enforcement": "enforce",
        "description": "Block any scan that surfaces secrets, credentials, API keys, or tokens in source code or configuration.",
        "rules":       [{"key": "no_secrets", "description": "Detect secrets / credentials in findings"}],
        "frameworks":  ["SOC2", "PCI-DSS", "NIST"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Block Critical CVEs",
        "policy_type": "block_critical_cves",
        "category":    "dependencies",
        "severity":    "critical",
        "enforcement": "enforce",
        "description": "Block scans when any critical-severity CVE is discovered with a known exploit or CVSS ≥ 9.0.",
        "rules":       [{"key": "block_critical_cves", "description": "Any vulnerability with severity=critical is a violation"}],
        "frameworks":  ["NIST", "ISO27001"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Require Signed Images",
        "policy_type": "require_signed_images",
        "category":    "container",
        "severity":    "high",
        "enforcement": "audit",
        "description": "Flag container images that are not cryptographically signed (Cosign / Notary).",
        "rules":       [{"key": "require_signed_images", "description": "Container image must be signed"}],
        "frameworks":  ["NIST", "CIS"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Require MFA",
        "policy_type": "require_mfa",
        "category":    "iam",
        "severity":    "high",
        "enforcement": "enforce",
        "description": "Enforce multi-factor authentication for all privileged IAM users and service accounts.",
        "rules":       [{"key": "require_mfa", "description": "Detect MFA-disabled accounts in findings"}],
        "frameworks":  ["SOC2", "ISO27001", "PCI-DSS"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Require Private Repositories",
        "policy_type": "require_private_repos",
        "category":    "code_quality",
        "severity":    "critical",
        "enforcement": "enforce",
        "description": "All source code repositories must be private. Public repos containing source code are a violation.",
        "rules":       [{"key": "require_private_repos", "description": "Repository must not be public"}],
        "frameworks":  ["SOC2", "ISO27001"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Minimum Security Score",
        "policy_type": "min_security_score",
        "category":    "posture",
        "severity":    "high",
        "enforcement": "audit",
        "description": "Ensure repositories maintain a minimum security score threshold.",
        "rules":       [{"key": "min_security_score", "threshold": 70, "description": "Security score must be >= 70"}],
        "frameworks":  ["NIST", "ISO27001"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Block High Risk Repositories",
        "policy_type": "block_high_risk_repos",
        "category":    "risk",
        "severity":    "critical",
        "enforcement": "enforce",
        "description": "Prevent deployment of repositories with 'Critical' or 'High' risk levels.",
        "rules":       [{"key": "block_high_risk_repos", "levels": ["critical", "high"], "description": "Risk level must not be critical or high"}],
        "frameworks":  ["SOC2", "NIST"],
        "tags":        {"builtin": True},
    },
    {
        "name":        "Require Passing Compliance Score",
        "policy_type": "require_passing_compliance",
        "category":    "compliance",
        "severity":    "high",
        "enforcement": "enforce",
        "description": "Require a minimum compliance score for all active repositories.",
        "rules":       [{"key": "require_passing_compliance", "threshold": 80, "description": "Compliance score must be >= 80"}],
        "frameworks":  ["HIPAA", "GDPR", "SOC2"],
        "tags":        {"builtin": True},
    },
]


# ─── Rule matcher functions ──────────────────────────────────────────────────

_SECRET_KEYWORDS = {
    "secret", "credential", "api_key", "apikey", "token", "password",
    "private_key", "access_key", "aws_secret", "auth_key", "passphrase",
}
_UNSIGNED_KEYWORDS = {"unsigned", "not signed", "signature missing", "cosign", "notary"}
_MFA_KEYWORDS = {"mfa", "multi-factor", "2fa", "two-factor", "totp", "authenticator", "mfa disabled", "no mfa"}


def _matches_no_secrets(finding: Any, ftype: str) -> tuple[bool, str]:
    """True if the finding indicates a secret / credential exposure."""
    title       = (getattr(finding, "title", "") or "").lower()
    category    = (getattr(finding, "category", "") or "").lower()
    source      = (getattr(finding, "source", "") or "").lower()
    description = (getattr(finding, "description", "") or "").lower()
    text        = f"{title} {category} {source} {description}"
    if any(kw in text for kw in _SECRET_KEYWORDS):
        return True, f"Secret/credential detected: '{finding.title[:80]}'"
    return False, ""


def _matches_block_critical_cves(finding: Any, ftype: str) -> tuple[bool, str]:
    if ftype != "vulnerability":
        return False, ""
    severity = (getattr(finding, "severity", "") or "").lower()
    if severity == "critical":
        cve = getattr(finding, "cve_id", "") or "CVE-unknown"
        return True, f"Critical CVE: {cve} — {finding.title[:80]}"
    return False, ""


def _matches_require_signed_images(finding: Any, ftype: str) -> tuple[bool, str]:
    title    = (getattr(finding, "title", "") or "").lower()
    category = (getattr(finding, "category", "") or "").lower()
    if any(kw in title or kw in category for kw in _UNSIGNED_KEYWORDS):
        return True, f"Unsigned image detected: '{finding.title[:80]}'"
    # Also flag container-category threats without signature
    if ftype == "threat" and "container" in category:
        image = getattr(finding, "resource", "") or ""
        if image and not any(kw in title for kw in ("signed", "verified")):
            return True, f"Unverified container image: {image[:80]}"
    return False, ""


def _matches_require_mfa(finding: Any, ftype: str) -> tuple[bool, str]:
    title    = (getattr(finding, "title", "") or "").lower()
    category = (getattr(finding, "category", "") or "").lower()
    description = (getattr(finding, "description", "") or "").lower()
    text = f"{title} {category} {description}"
    if any(kw in text for kw in _MFA_KEYWORDS):
        return True, f"MFA not enforced: '{finding.title[:80]}'"
    return False, ""


RULE_MATCHERS = {
    "no_secrets":            _matches_no_secrets,
    "block_critical_cves":   _matches_block_critical_cves,
    "require_signed_images":  _matches_require_signed_images,
    "require_mfa":           _matches_require_mfa,
}


class PolicyEvaluator:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Seed built-in policies for a tenant ───────────────────────────────────

    async def seed_builtin_policies(self, tenant_id: str, created_by: str) -> list[dict]:
        """Idempotently create built-in policies for a tenant."""
        created = []
        for tmpl in BUILTIN_POLICIES:
            # Check if already exists by policy_type + tenant
            existing = (await self.db.execute(
                select(SecurityPolicy).where(
                    SecurityPolicy.tenant_id  == tenant_id,
                    SecurityPolicy.policy_type == tmpl["policy_type"],
                )
            )).scalar_one_or_none()

            if existing:
                # Update enforcement mode if it changed
                continue

            policy = SecurityPolicy(
                tenant_id=  tenant_id,
                created_by= created_by,
                updated_by= created_by,
                status=     "active",
                is_builtin= True,
                **{k: v for k, v in tmpl.items()},
            )
            self.db.add(policy)
            created.append({"name": tmpl["name"], "policy_type": tmpl["policy_type"]})

        await self.db.commit()
        logger.info(f"[policy:seed] tenant={tenant_id[:8]} created={len(created)}")
        return created

    # ── Evaluate a completed scan ─────────────────────────────────────────────

    async def evaluate_scan(self, tenant_id: str, scan_id: str) -> dict:
        """
        Run all active policies against the scan's threats and vulnerabilities.

        ``violations`` counts new violation lifecycle rows created by this
        scan. A finding that remains present on a later scan updates its
        existing open row and increments that row's ``occurrence_count``; it
        does not inflate this count or the policy's active ``violations_count``.
        ``blocked`` and ``audit_flags`` still reflect every matching finding
        in the current scan.
        """
        # Load active policies
        policies = (await self.db.execute(
            select(SecurityPolicy).where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.status    == "active",
            )
        )).scalars().all()

        if not policies:
            await self._resolve_unobserved_finding_violations(
                tenant_id=tenant_id,
                scan_id=scan_id,
                observed_keys=set(),
            )
            await self.db.commit()
            return {"violations": 0, "blocked": False, "audit_flags": 0}

        # Load active exceptions (to suppress matching violations)
        now = datetime.now(timezone.utc)
        exceptions = (await self.db.execute(
            select(SecurityException).where(
                SecurityException.tenant_id == tenant_id,
                SecurityException.status    == "approved",
            )
        )).scalars().all()
        excepted_findings = set()
        for exception in exceptions:
            if not exception.finding_id:
                continue

            expires_at = exception.expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                # Some databases (including SQLite in tests) return timezone-
                # aware columns as naive datetimes. Treat those as UTC, matching
                # the timestamps written by the application.
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at is None or expires_at > now:
                excepted_findings.add(exception.finding_id)


        # Load threats and vulnerabilities for this scan
        threats = (await self.db.execute(
            select(Threat).where(Threat.scan_id == scan_id)
        )).scalars().all()
        vulns = (await self.db.execute(
            select(Vulnerability).where(Vulnerability.scan_id == scan_id)
        )).scalars().all()

        findings = [(t, "threat") for t in threats] + [(v, "vulnerability") for v in vulns]

        violations_created = 0
        blocked            = False
        audit_flags        = 0
        observed_keys: set[tuple[str, str, str, str]] = set()

        for finding, ftype in findings:
            if finding.id in excepted_findings:
                continue

            for policy in policies:
                for rule in (policy.rules or []):
                    rule_key    = rule.get("key", "")
                    matcher     = RULE_MATCHERS.get(rule_key)
                    if not matcher:
                        continue

                    matched, reason = matcher(finding, ftype)
                    if not matched:
                        continue

                    observed_keys.add((policy.id, ftype, finding.id, rule_key))
                    violation = await self._record_violation(
                        tenant_id=       tenant_id,
                        policy_id=       policy.id,
                        scan_id=         scan_id,
                        entity_type=     ftype,
                        entity_id=       finding.id,
                        entity_title=    finding.title,
                        rule_key=        rule_key,
                        rule_description=reason,
                        severity=        policy.severity,
                        enforcement_mode=policy.enforcement,
                        was_blocked=     policy.enforcement == "enforce",
                        context={
                            "policy_name":  policy.name,
                            "finding_type": ftype,
                            "severity":     getattr(finding, "severity", None),
                        },
                    )
                    if violation:
                        violations_created += 1

                    if policy.enforcement == "enforce":
                        blocked = True
                    else:
                        audit_flags += 1

        await self._resolve_unobserved_finding_violations(
            tenant_id=tenant_id,
            scan_id=scan_id,
            observed_keys=observed_keys,
        )
        await self.db.commit()

        # Check repository and posture policies
        await self._check_entity_policies(tenant_id, scan_id, policies)


        logger.info(
            f"[policy:evaluate] scan={scan_id[:8]} violations={violations_created} "
            f"blocked={blocked} audit={audit_flags}"
        )
        return {
            "violations": violations_created,
            "blocked":    blocked,
            "audit_flags": audit_flags,
            "scan_id":    scan_id,
        }

    async def _resolve_unobserved_finding_violations(
        self,
        *,
        tenant_id: str,
        scan_id: str,
        observed_keys: set[tuple[str, str, str, str]],
    ) -> None:
        """Close finding violations absent from a completed repository scan.

        Repository and posture violations are intentionally excluded: these
        are evaluated independently from scanner findings.
        """
        scan = (
            await self.db.execute(
                select(Scan).where(
                    Scan.id == scan_id,
                    Scan.tenant_id == tenant_id,
                    Scan.status == "completed",
                )
            )
        ).scalar_one_or_none()
        if not scan or not scan.repo_id:
            return

        violations = (
            await self.db.execute(
                select(PolicyViolation)
                .join(Scan, PolicyViolation.scan_id == Scan.id)
                .where(
                    PolicyViolation.tenant_id == tenant_id,
                    PolicyViolation.status == "open",
                    PolicyViolation.entity_type.in_(("threat", "vulnerability")),
                    Scan.tenant_id == tenant_id,
                    Scan.repo_id == scan.repo_id,
                )
            )
        ).scalars().all()

        now = datetime.now(timezone.utc)
        resolved_policy_ids = set()
        for violation in violations:
            key = (
                violation.policy_id,
                violation.entity_type,
                violation.entity_id,
                violation.rule_key,
            )
            if key not in observed_keys:
                violation.status = "resolved"
                violation.resolved_at = now
                resolved_policy_ids.add(violation.policy_id)

        # The policy counter is used as an active-violation total. Recompute it
        # for affected policies so it stays correct while resolved rows remain
        # available as lifecycle history.
        for policy_id in resolved_policy_ids:
            open_count = (
                await self.db.execute(
                    select(func.count(PolicyViolation.id)).where(
                        PolicyViolation.tenant_id == tenant_id,
                        PolicyViolation.policy_id == policy_id,
                        PolicyViolation.status == "open",
                    )
                )
            ).scalar_one()
            await self.db.execute(
                update(SecurityPolicy)
                .where(
                    SecurityPolicy.tenant_id == tenant_id,
                    SecurityPolicy.id == policy_id,
                )
                .values(violations_count=open_count)
            )

    async def _record_violation(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        scan_id: str,
        entity_type: str,
        entity_id: str,
        entity_title: str | None,
        rule_key: str,
        rule_description: str,
        severity: str,
        enforcement_mode: str,
        was_blocked: bool,
        context: dict,
    ) -> PolicyViolation | None:
        """Create or update one policy violation lifecycle.

        An open violation is identified by the policy, rule, and finding/entity
        within a tenant. Keeping the row open preserves a stable active
        violation for operators while ``scan_id`` and ``last_seen_at`` point
        to the latest observation. Closed lifecycles are intentionally not
        reused so their history remains visible.

        Returns the newly-created row, or ``None`` when an existing open row
        was updated.
        """
        existing = (
            await self.db.execute(
                select(PolicyViolation)
                .where(
                    PolicyViolation.tenant_id == tenant_id,
                    PolicyViolation.policy_id == policy_id,
                    PolicyViolation.entity_type == entity_type,
                    PolicyViolation.entity_id == entity_id,
                    PolicyViolation.rule_key == rule_key,
                    PolicyViolation.status == "open",
                )
                .order_by(PolicyViolation.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if existing:
            is_new_scan_observation = existing.scan_id != scan_id
            existing.scan_id = scan_id
            existing.entity_title = entity_title
            existing.rule_description = rule_description
            existing.severity = severity
            existing.enforcement_mode = enforcement_mode
            existing.was_blocked = was_blocked
            existing.context = context
            if is_new_scan_observation:
                existing.occurrence_count = (existing.occurrence_count or 1) + 1
            existing.last_seen_at = now
            return None

        violation = PolicyViolation(
            tenant_id=tenant_id,
            policy_id=policy_id,
            scan_id=scan_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_title=entity_title,
            rule_key=rule_key,
            rule_description=rule_description,
            severity=severity,
            enforcement_mode=enforcement_mode,
            was_blocked=was_blocked,
            status="open",
            context=context,
            first_seen_at=now,
            last_seen_at=now,
        )
        self.db.add(violation)
        await self.db.execute(
            update(SecurityPolicy)
            .where(SecurityPolicy.id == policy_id)
            .values(violations_count=SecurityPolicy.violations_count + 1)
        )
        return violation

    async def _check_entity_policies(
        self, tenant_id: str, scan_id: str, policies: list[SecurityPolicy]
    ) -> None:
        """Check repository, risk, and compliance policies for the scan entity."""
        # Find policies targeting entities (repos, posture, risk)
        entity_policies = [p for p in policies if
                           any(r.get("key") in ["require_private_repos", "min_security_score",
                                              "block_high_risk_repos", "require_passing_compliance"]
                               for r in (p.rules or []))]
        if not entity_policies:
            return

        from app.models.scan import Scan
        scan = (await self.db.execute(
            select(Scan).where(Scan.id == scan_id)
        )).scalar_one_or_none()
        if not scan:
            return

        # 1. Repository Privacy Check
        if scan.repo_id:
            repo = (await self.db.execute(
                select(Repository).where(Repository.id == scan.repo_id)
            )).scalar_one_or_none()
            if repo and not repo.is_private:
                for p in entity_policies:
                    if any(r.get("key") == "require_private_repos" for r in (p.rules or [])):
                        await self._record_violation(
                            tenant_id=tenant_id,
                            policy_id=p.id,
                            scan_id=scan_id,
                            entity_type="repository",
                            entity_id=repo.id,
                            entity_title=repo.full_name,
                            rule_key="require_private_repos",
                            rule_description=f"Repository '{repo.full_name}' is public",
                            severity=p.severity,
                            enforcement_mode=p.enforcement,
                            was_blocked=(p.enforcement == "enforce"),
                            context={"repo_full_name": repo.full_name, "is_private": False},
                        )

        # 2. Risk & Score Checks
        if scan.repo_id:
            risk = (await self.db.execute(
                select(RepositoryRiskScore).where(RepositoryRiskScore.repo_id == scan.repo_id)
            )).scalar_one_or_none()

            if risk:
                for p in entity_policies:
                    for rule in (p.rules or []):
                        key = rule.get("key")
                        if key == "min_security_score":
                            threshold = rule.get("threshold", 0)
                            score = risk.security_score or 0.0
                            if score < threshold:
                                await self._record_violation(
                                    tenant_id=tenant_id,
                                    policy_id=p.id,
                                    scan_id=scan_id,
                                    entity_type="repository",
                                    entity_id=scan.repo_id,
                                    entity_title=f"Score: {score}",
                                    rule_key=key,
                                    rule_description=f"Security score {score} is below threshold {threshold}",
                                    severity=p.severity,
                                    enforcement_mode=p.enforcement,
                                    was_blocked=(p.enforcement == "enforce"),
                                    context={"score": score, "threshold": threshold},
                                )

                        elif key == "block_high_risk_repos":
                            levels = rule.get("levels", ["critical", "high"])
                            if risk.risk_level.lower() in [l.lower() for l in levels]:
                                await self._record_violation(
                                    tenant_id=tenant_id,
                                    policy_id=p.id,
                                    scan_id=scan_id,
                                    entity_type="repository",
                                    entity_id=scan.repo_id,
                                    entity_title=f"Risk: {risk.risk_level}",
                                    rule_key=key,
                                    rule_description=f"Repository risk level '{risk.risk_level}' is blocked",
                                    severity=p.severity,
                                    enforcement_mode=p.enforcement,
                                    was_blocked=(p.enforcement == "enforce"),
                                    context={"risk_level": risk.risk_level, "blocked_levels": levels},
                                )

        # 3. Compliance Check (Tenant level)
        posture = (await self.db.execute(
            select(SecurityPostureScore).where(SecurityPostureScore.tenant_id == tenant_id)
            .order_by(SecurityPostureScore.recorded_at.desc())
        )).scalar_one_or_none()

        if posture:
            for p in entity_policies:
                for rule in (p.rules or []):
                    if rule.get("key") == "require_passing_compliance":
                        threshold = rule.get("threshold", 0)
                        score = posture.compliance_score
                        if score < threshold:
                            await self._record_violation(
                                tenant_id=tenant_id,
                                policy_id=p.id,
                                scan_id=scan_id,
                                entity_type="tenant",
                                entity_id=tenant_id,
                                entity_title="Compliance Posture",
                                rule_key="require_passing_compliance",
                                rule_description=f"Compliance score {score} is below threshold {threshold}",
                                severity=p.severity,
                                enforcement_mode=p.enforcement,
                                was_blocked=(p.enforcement == "enforce"),
                                context={"score": score, "threshold": threshold},
                            )

        await self.db.commit()

    # ── List violations ───────────────────────────────────────────────────────

    async def list_violations(
        self,
        tenant_id:   str,
        policy_id:   str | None = None,
        entity_type: str | None = None,
        status:      str | None = None,
        enforcement: str | None = None,
        limit:       int = 100,
        offset:      int = 0,
    ) -> list[dict]:
        q = select(PolicyViolation).where(PolicyViolation.tenant_id == tenant_id)
        if policy_id:   q = q.where(PolicyViolation.policy_id       == policy_id)
        if entity_type: q = q.where(PolicyViolation.entity_type      == entity_type)
        if status:      q = q.where(PolicyViolation.status           == status)
        if enforcement: q = q.where(PolicyViolation.enforcement_mode == enforcement)
        q = q.order_by(PolicyViolation.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.db.execute(q)).scalars().all()
        return [_viol_dict(v) for v in rows]

    async def get_violation_summary(self, tenant_id: str) -> dict:
        total = (await self.db.execute(
            select(func.count(PolicyViolation.id)).where(PolicyViolation.tenant_id == tenant_id)
        )).scalar() or 0
        open_count = (await self.db.execute(
            select(func.count(PolicyViolation.id)).where(
                PolicyViolation.tenant_id == tenant_id,
                PolicyViolation.status    == "open",
            )
        )).scalar() or 0
        blocked = (await self.db.execute(
            select(func.count(PolicyViolation.id)).where(
                PolicyViolation.tenant_id  == tenant_id,
                PolicyViolation.was_blocked == True,
            )
        )).scalar() or 0
        # By rule
        rule_rows = (await self.db.execute(
            select(PolicyViolation.rule_key, func.count(PolicyViolation.id))
            .where(PolicyViolation.tenant_id == tenant_id, PolicyViolation.status == "open")
            .group_by(PolicyViolation.rule_key)
        )).all()
        by_rule = {r[0]: r[1] for r in rule_rows}
        return {
            "total": total, "open": open_count, "blocked": blocked,
            "by_rule": by_rule,
        }


def _viol_dict(v: PolicyViolation) -> dict:
    return {
        "id":              v.id,
        "policy_id":       v.policy_id,
        "scan_id":         v.scan_id,
        "entity_type":     v.entity_type,
        "entity_id":       v.entity_id,
        "entity_title":    v.entity_title,
        "rule_key":        v.rule_key,
        "rule_description":v.rule_description,
        "severity":        v.severity,
        "enforcement_mode":v.enforcement_mode,
        "was_blocked":     v.was_blocked,
        "is_suppressed":   v.is_suppressed,
        "status":          v.status,
        "context":         v.context,
        "occurrence_count":v.occurrence_count,
        "first_seen_at":   v.first_seen_at.isoformat() if v.first_seen_at else None,
        "last_seen_at":    v.last_seen_at.isoformat() if v.last_seen_at else None,
        "created_at":      v.created_at.isoformat() if v.created_at else None,
    }
