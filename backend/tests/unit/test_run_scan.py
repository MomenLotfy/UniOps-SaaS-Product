"""Regression coverage for repository scan result persistence."""

import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.scan import Repository, Scan
from app.models.security_exception import SecurityException
from app.models.tenant import Tenant
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.models.policy_violation import PolicyViolation
from app.models.security_policy import SecurityPolicy
from app.services.scan_engine import RawFinding, ScanResult
from tests.conftest import TestSessionLocal


def _threat(*, file_path: str = "app.py", line: int = 10) -> RawFinding:
    return RawFinding(
        scanner="sast",
        severity="high",
        title="Unsafe code pattern",
        description="A regression-test threat",
        file_path=file_path,
        line=line,
        rule_id="python.security.test",
        raw={"engine": "fixture", "check": "unsafe"},
    )


def _vulnerability(*, cve_id: str = "CVE-2026-0001") -> RawFinding:
    return RawFinding(
        scanner="deps",
        severity="critical",
        title="Vulnerable dependency",
        description="A regression-test vulnerability",
        cve_id=cve_id,
        package="example-package",
        version="1.0.0",
        fixed_in="1.0.1",
    )


@pytest.fixture
def fake_scan_worker(monkeypatch):
    """Install a deterministic clone/scanner while retaining real persistence."""
    from app.core import database
    from app.services import scan_engine

    findings_by_repo: dict[str, list[RawFinding]] = {}

    class FakeOrchestrator:
        def __init__(self, **_kwargs):
            pass

        async def clone(self, *_args):
            return tempfile.mkdtemp(prefix="uniops-test-scan-")

        async def scan_repo(self, _work_dir, _scan_id, repo_name):
            findings = deepcopy(findings_by_repo.get(repo_name, []))
            return ScanResult(
                findings=findings,
                scanners_run={"fixture": "completed"},
                raw_by_scanner={"fixture": [vars(f) for f in findings]},
            )

        def _detect_repo_capabilities(self, _work_dir):
            return {"has_dockerfile": False, "has_cicd": False}

    class FakeAiAnalyzer:
        async def analyze(self, **_kwargs):
            return "fixture summary", ["fixture suggestion"]

    monkeypatch.setattr(scan_engine, "ScanOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(scan_engine, "AiAnalyzer", FakeAiAnalyzer)
    monkeypatch.setattr(database, "CelerySessionLocal", TestSessionLocal)

    return findings_by_repo


async def _create_scan(
    db_session, *, tenant_id: str, repo_name: str, repo_id: str | None = None
) -> Scan:
    if repo_id is None:
        repo = Repository(
            tenant_id=tenant_id,
            provider="github",
            external_id=repo_name,
            full_name=repo_name,
            name=repo_name.rsplit("/", 1)[-1],
            clone_url=f"https://example.test/{repo_name}.git",
            default_branch="main",
        )
        db_session.add(repo)
        await db_session.flush()
        repo_id = repo.id

    scan = Scan(tenant_id=tenant_id, repo_id=repo_id, branch="main", status="queued")
    db_session.add(scan)
    await db_session.commit()
    return scan


async def _run_scan(db_session, scan: Scan) -> None:
    from app.tasks.run_scan import _run_scan_async

    await _run_scan_async(scan.id)


@pytest.mark.asyncio
async def test_clean_scan_completes_without_findings(db_session, fake_scan_worker):
    tenant = Tenant(name="Clean tenant", slug="clean-tenant")
    db_session.add(tenant)
    await db_session.flush()
    scan = await _create_scan(db_session, tenant_id=tenant.id, repo_name="acme/clean")

    await _run_scan(db_session, scan)

    stored_scan = await db_session.get(Scan, scan.id, populate_existing=True)
    threats = (await db_session.execute(select(Threat))).scalars().all()
    vulnerabilities = (await db_session.execute(select(Vulnerability))).scalars().all()
    assert stored_scan.status == "completed"
    assert stored_scan.security_score == 100.0
    assert threats == []
    assert vulnerabilities == []


@pytest.mark.asyncio
async def test_threat_finding_is_persisted_with_raw_metadata(db_session, fake_scan_worker):
    tenant = Tenant(name="Threat tenant", slug="threat-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/threats"] = [_threat()]
    scan = await _create_scan(db_session, tenant_id=tenant.id, repo_name="acme/threats")

    await _run_scan(db_session, scan)

    threat = (await db_session.execute(select(Threat))).scalar_one()
    assert threat.title == "Unsafe code pattern"
    assert threat.repo_id == scan.repo_id
    assert threat.raw_data["engine"] == "fixture"
    assert threat.raw_data["rule_id"] == "python.security.test"


@pytest.mark.asyncio
async def test_vulnerability_finding_is_persisted(db_session, fake_scan_worker):
    tenant = Tenant(name="Vulnerability tenant", slug="vulnerability-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/vulnerabilities"] = [_vulnerability()]
    scan = await _create_scan(
        db_session, tenant_id=tenant.id, repo_name="acme/vulnerabilities"
    )

    await _run_scan(db_session, scan)

    vulnerability = (await db_session.execute(select(Vulnerability))).scalar_one()
    assert vulnerability.cve_id == "CVE-2026-0001"
    assert vulnerability.repo_id == scan.repo_id
    assert vulnerability.detected_by == ["deps"]


@pytest.mark.asyncio
async def test_scan_worker_persists_policy_violation_for_matching_finding(
    db_session, fake_scan_worker
):
    tenant = Tenant(name="Policy tenant", slug="policy-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/policy"] = [_vulnerability()]
    policy = SecurityPolicy(
        tenant_id=tenant.id,
        name="Block critical CVEs",
        category="dependencies",
        severity="critical",
        status="active",
        enforcement="enforce",
        rules=[{"key": "block_critical_cves"}],
    )
    db_session.add(policy)
    await db_session.commit()
    scan = await _create_scan(db_session, tenant_id=tenant.id, repo_name="acme/policy")

    await _run_scan(db_session, scan)

    violation = (
        await db_session.execute(
            select(PolicyViolation).where(PolicyViolation.scan_id == scan.id)
        )
    ).scalar_one()
    assert violation.tenant_id == tenant.id
    assert violation.policy_id == policy.id
    assert violation.entity_type == "vulnerability"
    assert violation.rule_key == "block_critical_cves"
    assert violation.was_blocked is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "should_suppress"),
    [
        ("approved_matching", True),
        ("expired", False),
        ("pending", False),
        ("other_tenant", False),
        ("other_finding", False),
    ],
)
async def test_scan_worker_only_suppresses_matching_active_approved_exceptions(
    db_session, fake_scan_worker, case, should_suppress
):
    tenant = Tenant(name=f"Exception tenant {case}", slug=f"exception-tenant-{case}")
    db_session.add(tenant)
    await db_session.flush()
    scan = await _create_scan(
        db_session, tenant_id=tenant.id, repo_name=f"acme/exception-{case}"
    )

    finding = Vulnerability(
        tenant_id=tenant.id,
        scan_id=scan.id,
        repo_id=scan.repo_id,
        cve_id="CVE-2026-0001",
        title="Vulnerable dependency",
        description="A regression-test vulnerability",
        severity="critical",
        package_name="example-package",
        package_version="1.0.0",
        status="open",
        detected_by=["deps"],
    )
    policy = SecurityPolicy(
        tenant_id=tenant.id,
        name="Block critical CVEs",
        category="dependencies",
        severity="critical",
        status="active",
        enforcement="enforce",
        rules=[{"key": "block_critical_cves"}],
    )
    db_session.add_all([finding, policy])
    await db_session.flush()

    exception_tenant_id = tenant.id
    if case == "other_tenant":
        other_tenant = Tenant(
            name="Exception from another tenant",
            slug="other-exception-tenant",
        )
        db_session.add(other_tenant)
        await db_session.flush()
        exception_tenant_id = other_tenant.id

    exception_finding_id = finding.id
    if case == "other_finding":
        exception_finding_id = "different-finding-id"

    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    if case == "expired":
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    exception = SecurityException(
        tenant_id=exception_tenant_id,
        finding_id=exception_finding_id,
        title="Accepted dependency risk",
        justification="Accepted for regression test",
        risk_acceptance="The risk is tracked",
        status="pending" if case == "pending" else "approved",
        requested_by="test-user",
        approved_by=None if case == "pending" else "test-reviewer",
        expires_at=expires_at,
    )
    db_session.add(exception)
    await db_session.commit()

    fake_scan_worker[f"acme/exception-{case}"] = [_vulnerability()]
    tenant_id = tenant.id
    scan_id = scan.id
    policy_id = policy.id
    finding_id = finding.id
    await _run_scan(db_session, scan)

    violations = (
        await db_session.execute(
            select(PolicyViolation)
            .where(PolicyViolation.scan_id == scan_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    if should_suppress:
        assert violations == []
    else:
        assert len(violations) == 1
        assert violations[0].tenant_id == tenant_id
        assert violations[0].policy_id == policy_id
        assert violations[0].entity_id == finding_id


@pytest.mark.asyncio
async def test_repeated_scan_keeps_one_policy_violation_and_tracks_occurrences(
    db_session, fake_scan_worker
):
    tenant = Tenant(name="Policy repeat tenant", slug="policy-repeat-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/policy-repeat"] = [_vulnerability()]
    policy = SecurityPolicy(
        tenant_id=tenant.id,
        name="Block critical CVEs",
        category="dependencies",
        severity="critical",
        status="active",
        enforcement="enforce",
        rules=[{"key": "block_critical_cves"}],
    )
    db_session.add(policy)
    await db_session.commit()

    first_scan = await _create_scan(
        db_session, tenant_id=tenant.id, repo_name="acme/policy-repeat"
    )
    await _run_scan(db_session, first_scan)
    second_scan = await _create_scan(
        db_session,
        tenant_id=tenant.id,
        repo_name="acme/policy-repeat",
        repo_id=first_scan.repo_id,
    )
    await _run_scan(db_session, second_scan)

    violations = (
        await db_session.execute(
            select(PolicyViolation).where(PolicyViolation.policy_id == policy.id)
        )
    ).scalars().all()
    assert len(violations) == 1
    assert violations[0].status == "open"
    assert violations[0].scan_id == second_scan.id
    assert violations[0].occurrence_count == 2

    stored_policy = await db_session.get(
        SecurityPolicy, policy.id, populate_existing=True
    )
    assert stored_policy.violations_count == 1


@pytest.mark.asyncio
async def test_missing_finding_resolves_violation_and_recurrence_starts_new_lifecycle(
    db_session, fake_scan_worker
):
    tenant = Tenant(name="Policy lifecycle tenant", slug="policy-lifecycle-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/policy-lifecycle"] = [_vulnerability()]
    policy = SecurityPolicy(
        tenant_id=tenant.id,
        name="Block critical CVEs",
        category="dependencies",
        severity="critical",
        status="active",
        enforcement="enforce",
        rules=[{"key": "block_critical_cves"}],
    )
    db_session.add(policy)
    await db_session.commit()
    tenant_id, policy_id = tenant.id, policy.id

    first_scan = await _create_scan(
        db_session, tenant_id=tenant_id, repo_name="acme/policy-lifecycle"
    )
    first_scan_id, repo_id = first_scan.id, first_scan.repo_id
    await _run_scan(db_session, first_scan)

    fake_scan_worker["acme/policy-lifecycle"] = []
    disappearance_scan = await _create_scan(
        db_session,
        tenant_id=tenant_id,
        repo_name="acme/policy-lifecycle",
        repo_id=repo_id,
    )
    await _run_scan(db_session, disappearance_scan)

    resolved = (
        await db_session.execute(
            select(PolicyViolation)
            .where(PolicyViolation.policy_id == policy_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert len(resolved) == 1
    assert resolved[0].status == "resolved"
    assert resolved[0].resolved_at is not None
    assert resolved[0].scan_id == first_scan_id
    stored_policy = await db_session.get(
        SecurityPolicy, policy_id, populate_existing=True
    )
    assert stored_policy.violations_count == 0

    fake_scan_worker["acme/policy-lifecycle"] = [_vulnerability()]
    recurrence_scan = await _create_scan(
        db_session,
        tenant_id=tenant_id,
        repo_name="acme/policy-lifecycle",
        repo_id=repo_id,
    )
    recurrence_scan_id = recurrence_scan.id
    await _run_scan(db_session, recurrence_scan)

    lifecycles = (
        await db_session.execute(
            select(PolicyViolation)
            .where(PolicyViolation.policy_id == policy_id)
            .order_by(PolicyViolation.created_at)
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert len(lifecycles) == 2
    assert lifecycles[0].status == "resolved"
    assert lifecycles[0].scan_id == first_scan_id
    assert lifecycles[1].status == "open"
    assert lifecycles[1].scan_id == recurrence_scan_id
    assert lifecycles[1].occurrence_count == 1
    stored_policy = await db_session.get(
        SecurityPolicy, policy_id, populate_existing=True
    )
    assert stored_policy.violations_count == 1


@pytest.mark.asyncio
async def test_finding_reconciliation_leaves_repository_and_posture_violations_open(
    db_session, fake_scan_worker
):
    tenant = Tenant(name="Entity policy tenant", slug="entity-policy-tenant")
    db_session.add(tenant)
    await db_session.flush()
    policy = SecurityPolicy(
        tenant_id=tenant.id,
        name="Block critical CVEs",
        category="dependencies",
        severity="critical",
        status="active",
        enforcement="enforce",
        rules=[{"key": "block_critical_cves"}],
    )
    db_session.add(policy)
    await db_session.commit()
    tenant_id, policy_id = tenant.id, policy.id

    first_scan = await _create_scan(
        db_session, tenant_id=tenant_id, repo_name="acme/entity-policy"
    )
    first_scan_id, repo_id = first_scan.id, first_scan.repo_id
    db_session.add_all(
        [
            PolicyViolation(
                tenant_id=tenant_id,
                policy_id=policy_id,
                scan_id=first_scan_id,
                entity_type="repository",
                entity_id=repo_id,
                rule_key="repository_rule",
                status="open",
            ),
            PolicyViolation(
                tenant_id=tenant_id,
                policy_id=policy_id,
                scan_id=first_scan_id,
                entity_type="tenant",
                entity_id=tenant_id,
                rule_key="posture_rule",
                status="open",
            ),
        ]
    )
    await db_session.commit()

    fake_scan_worker["acme/entity-policy"] = []
    next_scan = await _create_scan(
        db_session,
        tenant_id=tenant_id,
        repo_name="acme/entity-policy",
        repo_id=repo_id,
    )
    await _run_scan(db_session, next_scan)

    violations = (
        await db_session.execute(
            select(PolicyViolation)
            .where(PolicyViolation.policy_id == policy_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert {violation.entity_type for violation in violations} == {"repository", "tenant"}
    assert all(violation.status == "open" for violation in violations)
    assert all(violation.scan_id == first_scan_id for violation in violations)


@pytest.mark.asyncio
async def test_repeated_scan_deduplicates_findings_and_updates_occurrence(
    db_session, fake_scan_worker
):
    tenant = Tenant(name="Repeated tenant", slug="repeated-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/repeated"] = [_threat(), _vulnerability()]

    first_scan = await _create_scan(db_session, tenant_id=tenant.id, repo_name="acme/repeated")
    await _run_scan(db_session, first_scan)
    second_scan = await _create_scan(
        db_session,
        tenant_id=tenant.id,
        repo_name="acme/repeated",
        repo_id=first_scan.repo_id,
    )
    await _run_scan(db_session, second_scan)

    threats = (await db_session.execute(select(Threat))).scalars().all()
    vulnerabilities = (await db_session.execute(select(Vulnerability))).scalars().all()
    assert len(threats) == 1
    assert threats[0].occurrence_count == 2
    assert threats[0].scan_id == second_scan.id
    assert len(vulnerabilities) == 1
    assert vulnerabilities[0].scan_id == second_scan.id


@pytest.mark.asyncio
async def test_same_finding_in_multiple_repositories_is_stored_per_repository(
    db_session, fake_scan_worker
):
    tenant = Tenant(name="Multi-repository tenant", slug="multi-repository-tenant")
    db_session.add(tenant)
    await db_session.flush()
    fake_scan_worker["acme/repo-one"] = [_threat()]
    fake_scan_worker["acme/repo-two"] = [_threat()]

    first_scan = await _create_scan(db_session, tenant_id=tenant.id, repo_name="acme/repo-one")
    second_scan = await _create_scan(db_session, tenant_id=tenant.id, repo_name="acme/repo-two")
    await _run_scan(db_session, first_scan)
    await _run_scan(db_session, second_scan)

    threats = (await db_session.execute(select(Threat).order_by(Threat.repo_id))).scalars().all()
    assert len(threats) == 2
    assert {threat.repo_id for threat in threats} == {first_scan.repo_id, second_scan.repo_id}