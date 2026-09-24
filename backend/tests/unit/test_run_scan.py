"""Regression coverage for repository scan result persistence."""

import tempfile
from copy import deepcopy

import pytest
from sqlalchemy import select

from app.models.scan import Repository, Scan
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