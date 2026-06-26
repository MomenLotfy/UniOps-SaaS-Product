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
from app.models.scan import Repository
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
        Returns {violations, blocked, audit_flags}.
        """
        # Load active policies
        policies = (await self.db.execute(
            select(SecurityPolicy).where(
                SecurityPolicy.tenant_id == tenant_id,
                SecurityPolicy.status    == "active",
            )
        )).scalars().all()

        if not policies:
            return {"violations": 0, "blocked": False, "audit_flags": 0}

        # Load active exceptions (to suppress matching violations)
        now = datetime.now(timezone.utc)
        exceptions = (await self.db.execute(
            select(SecurityException).where(
                SecurityException.tenant_id == tenant_id,
                SecurityException.status    == "approved",
            )
        )).scalars().all()
        excepted_findings = {e.finding_id for e in exceptions if e.finding_id}

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

                    # Create violation record
                    violation = PolicyViolation(
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
                        status=          "open",
                        context={
                            "policy_name":  policy.name,
                            "finding_type": ftype,
                            "severity":     getattr(finding, "severity", None),
                        },
                    )
                    self.db.add(violation)
                    violations_created += 1

                    if policy.enforcement == "enforce":
                        blocked = True
                    else:
                        audit_flags += 1

                    # Update policy violation count
                    await self.db.execute(
                        update(SecurityPolicy)
                        .where(SecurityPolicy.id == policy.id)
                        .values(violations_count=SecurityPolicy.violations_count + 1)
                    )

        await self.db.commit()

        # Check private repos separately (not scan-level, but repo-level)
        await self._check_private_repo_policies(tenant_id, scan_id, policies)

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

    async def _check_private_repo_policies(
        self, tenant_id: str, scan_id: str, policies: list[SecurityPolicy]
    ) -> None:
        """Check if any repo linked to this scan is public."""
        priv_policies = [p for p in policies if
                         any(r.get("key") == "require_private_repos" for r in (p.rules or []))]
        if not priv_policies:
            return

        # Find repo for scan
        from app.models.scan import Scan
        scan = (await self.db.execute(
            select(Scan).where(Scan.id == scan_id)
        )).scalar_one_or_none()
        if not scan or not scan.repo_id:
            return

        repo = (await self.db.execute(
            select(Repository).where(Repository.id == scan.repo_id)
        )).scalar_one_or_none()
        if not repo:
            return

        if not repo.is_private:
            for policy in priv_policies:
                violation = PolicyViolation(
                    tenant_id=       tenant_id,
                    policy_id=       policy.id,
                    scan_id=         scan_id,
                    entity_type=     "repository",
                    entity_id=       repo.id,
                    entity_title=    repo.full_name,
                    rule_key=        "require_private_repos",
                    rule_description=f"Repository '{repo.full_name}' is public",
                    severity=        policy.severity,
                    enforcement_mode=policy.enforcement,
                    was_blocked=     policy.enforcement == "enforce",
                    status=          "open",
                    context={"repo_full_name": repo.full_name, "is_private": False},
                )
                self.db.add(violation)
                await self.db.execute(
                    update(SecurityPolicy)
                    .where(SecurityPolicy.id == policy.id)
                    .values(violations_count=SecurityPolicy.violations_count + 1)
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
        "created_at":      v.created_at.isoformat() if v.created_at else None,
    }
