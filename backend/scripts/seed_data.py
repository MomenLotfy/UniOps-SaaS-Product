#!/usr/bin/env python3
"""Seed database with demo data for development and staging environments.

Usage:
    python scripts/seed_data.py [--tenant-id existing-tenant-id]
"""
import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def seed_data(tenant_id: str = None) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.integration import Integration
    from app.models.pipeline import Pipeline
    from app.models.pod import Pod
    from app.models.threat import Threat
    from app.models.vulnerability import Vulnerability
    from app.models.cost_metric import CostMetric
    from app.models.alert import Alert
    from app.core.security import hash_password
    from sqlalchemy import select
    import random

    async with AsyncSessionLocal() as db:
        # ── Idempotency guard — skip if already seeded ────────────────────────
        existing = await db.execute(
            select(User).where(User.email == "admin@demo.com")
        )
        if existing.scalar_one_or_none():
            print("⏭️  Demo data already exists — skipping seed")
            return

        if tenant_id:
            r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = r.scalar_one_or_none()
            if not tenant:
                print(f"ERROR: Tenant {tenant_id} not found")
                sys.exit(1)
        else:
            tenant = Tenant(name="Demo Organization", slug="demo", plan="professional", is_active=True)
            db.add(tenant)
            await db.flush()

            admin = User(
                tenant_id=tenant.id, email="admin@demo.com", username="demo_admin",
                full_name="Demo Admin", hashed_password=hash_password("demo123!"), role="admin",
                is_active=True, is_verified=True,
            )
            viewer = User(
                tenant_id=tenant.id, email="viewer@demo.com", username="demo_viewer",
                full_name="Demo Viewer", hashed_password=hash_password("demo123!"), role="viewer",
                is_active=True, is_verified=True,
            )
            db.add_all([admin, viewer])
            await db.flush()  # ensure admin.id is available later

        # Integrations
        for int_type, int_name in [("aws", "AWS Production"), ("github", "GitHub"), ("kubernetes", "K8s Cluster")]:
            db.add(Integration(tenant_id=tenant.id, name=int_name, type=int_type,
                               status="connected", is_active=True, credentials={}, config={}))
        await db.flush()

        # Pipelines
        statuses = ["success", "success", "success", "failed", "running"]
        for i in range(20):
            db.add(Pipeline(
                tenant_id=tenant.id,
                external_id=f"run-{1000+i}",
                name=f"Build {i+1}",
                repository=f"org/repo-{(i%3)+1}",
                branch="main",
                status=random.choice(statuses),
                duration=random.randint(60, 600),
                triggered_by="github_actions",
            ))

        # Pods
        pod_statuses = ["Running", "Running", "Running", "Pending", "Failed"]
        for i in range(15):
            db.add(Pod(
                tenant_id=tenant.id, name=f"app-pod-{i+1}", namespace="production",
                cluster="prod-cluster", status=random.choice(pod_statuses),
                cpu_limit=1.0, cpu_usage=random.uniform(0.1, 0.9),
                memory_limit=512 * 1024 * 1024, memory_usage=random.randint(100 * 1024 * 1024, 450 * 1024 * 1024),
                restart_count=random.randint(0, 8),
            ))

        # Cost metrics (last 6 months, multiple services — ensures breakdown & forecast work)
        services_by_provider = [
            ("aws", "EC2",         random.uniform(1200, 2800)),
            ("aws", "S3",          random.uniform(200,  600)),
            ("aws", "RDS",         random.uniform(400,  1200)),
            ("aws", "CloudFront",  random.uniform(100,  400)),
            ("aws", "Lambda",      random.uniform(50,   300)),
            ("gcp", "Compute",     random.uniform(300,  900)),
            ("kubernetes", "Pods", random.uniform(150,  500)),
        ]
        for i in range(6):
            # i=0 → current month, i=1 → last month, etc.
            from datetime import timedelta as _td
            ref = date.today().replace(day=1)
            if i == 0:
                month_start = ref
            else:
                # Step back i months safely
                year = ref.year
                month = ref.month - i
                while month <= 0:
                    month += 12
                    year -= 1
                month_start = date(year, month, 1)
            month_end = month_start.replace(day=28)
            for provider, service, base_amount in services_by_provider:
                # Add some variance per month
                amount = round(base_amount * random.uniform(0.85, 1.20), 2)
                db.add(CostMetric(
                    tenant_id=tenant.id, provider=provider, service=service,
                    amount=amount, currency="USD",
                    period_start=month_start,
                    period_end=month_end,
                ))

        # Threats
        severities = ["critical", "high", "medium", "low"]
        for i in range(10):
            db.add(Threat(
                tenant_id=tenant.id, title=f"Security Event {i+1}", severity=random.choice(severities),
                category="network", status="open", source="falco",
                description="Suspicious activity detected in production namespace",
            ))

        # Vulnerabilities
        for i in range(15):
            db.add(Vulnerability(
                tenant_id=tenant.id, cve_id=f"CVE-2024-{1000+i}",
                title=f"Vulnerability {i+1}", severity=random.choice(severities),
                status="open", package_name=f"pkg-{i%5}", package_version="1.0.0", fixed_version="1.0.1",
                cvss_score=round(random.uniform(4.0, 10.0), 1),
            ))

        # Alerts
        alert_sources = ["aws_security_hub", "falco", "datadog", "prometheus"]
        for i in range(8):
            db.add(Alert(
                tenant_id=tenant.id, title=f"Alert {i+1}", severity=random.choice(["critical", "high", "medium"]),
                category="security", source=random.choice(alert_sources), status="active", is_read=i > 3,
                fired_at=datetime.now(timezone.utc) - timedelta(hours=i * 2),
            ))


        # ML Patterns
        from app.models.ml_pattern import MLPattern
        from app.models.ml_recommendation import MLRecommendation
        from app.models.ml_correlation import MLCorrelation
        from app.models.cost_anomaly import CostAnomaly
        from app.models.savings import Savings

        pattern_types = ["periodic_spike", "resource_leak", "cost_drift", "traffic_anomaly"]
        for i in range(8):
            db.add(MLPattern(
                tenant_id=tenant.id,
                name=f"Pattern-{i+1}",
                pattern_type=random.choice(pattern_types),
                description=f"Anomalous behavior detected with {85+i}% confidence in production cluster",
                confidence=round(85 + random.randint(0, 14), 1),
                frequency=random.choice(["hourly", "daily", "weekly"]),
                data={"services": [f"service-{i%3+1}"], "impact": random.choice(["Performance", "Cost", "Security"])},
            ))

        for i in range(5):
            db.add(MLRecommendation(
                tenant_id=tenant.id,
                title=f"Optimization Opportunity {i+1}",
                description=f"Apply this recommendation to reduce costs by {10+i*5}% or improve performance",
                category=random.choice(["Cost", "Performance", "Security", "Reliability"]),
                priority=random.randint(1, 5),
                confidence=round(80 + random.randint(0, 19), 1),
                impact=random.choice(["high", "medium", "low"]),
                effort=random.choice(["low", "medium", "high"]),
                status="pending",
                action=f"Enable auto-scaling and right-size resources for service-{i+1}",
            ))

        for i in range(6):
            db.add(MLCorrelation(
                tenant_id=tenant.id,
                metric_a=random.choice(["cpu_usage", "memory_usage", "request_rate", "disk_io"]),
                metric_b=random.choice(["latency", "error_rate", "cost", "throughput"]),
                correlation_score=round(random.uniform(0.3, 0.98), 2),
                method="pearson",
                insight=f"Strong correlation detected — consider optimizing together",
                data_points={"n": random.randint(100, 10000)},
            ))

        # Cost Anomalies
        for i in range(4):
            exp = round(random.uniform(500, 3000), 2)
            act = round(exp * (1 + random.uniform(0.2, 0.8)), 2)
            db.add(CostAnomaly(
                tenant_id=tenant.id,
                service=random.choice(["EC2", "S3", "RDS", "CloudFront"]),
                description=f"Cost spike: {round((act-exp)/exp*100)}% above expected baseline",
                expected_cost=exp,
                actual_cost=act,
                deviation=round((act - exp) / exp * 100, 1),
                severity=random.choice(["high", "medium"]),
                status=random.choice(["open", "investigating", "resolved"]),
                detected_date=date.today(),
            ))

        for i in range(5):
            db.add(Savings(
                tenant_id=tenant.id,
                title=f"Savings Opportunity {i+1}",
                description=f"Optimize cloud resource usage to reduce monthly costs",
                category=random.choice(["Compute", "Storage", "Network", "Database"]),
                provider=random.choice(["aws", "gcp", "azure"]),
                potential_savings=round(random.uniform(200, 2000), 2),
                effort=random.choice(["low", "medium"]),
                status="open",
                recommendation="Review and apply optimization to reduce spend",
            ))

        # ── Repositories (needed for Security Center scan UI) ─────────────────
        from app.models.scan import Repository, Scan

        demo_repos = [
            {"name": "backend-api",      "full_name": "demo-org/backend-api",      "provider": "github", "language": "python",     "has_dockerfile": True,  "has_cicd": True},
            {"name": "frontend-app",     "full_name": "demo-org/frontend-app",     "provider": "github", "language": "typescript", "has_dockerfile": True,  "has_cicd": True},
            {"name": "infra-terraform",  "full_name": "demo-org/infra-terraform",  "provider": "github", "language": "unknown",    "has_dockerfile": False, "has_cicd": False},
        ]

        # Get the GitHub integration id
        gh_int_res = await db.execute(
            select(Integration).where(Integration.tenant_id == tenant.id, Integration.type == "github")
        )
        gh_int = gh_int_res.scalar_one_or_none()

        repos_created = []
        for rd in demo_repos:
            repo = Repository(
                tenant_id=tenant.id,
                integration_id=gh_int.id if gh_int else None,
                provider=rd["provider"],
                external_id=rd["full_name"],
                full_name=rd["full_name"],
                name=rd["name"],
                clone_url=f"https://github.com/{rd['full_name']}.git",
                default_branch="main",
                is_private=True,
                language=rd["language"],
                has_dockerfile=rd["has_dockerfile"],
                has_cicd=rd["has_cicd"],
                last_scan_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48)),
                last_scan_score=round(random.uniform(55, 92), 1),
            )
            db.add(repo)
            repos_created.append(repo)
        await db.flush()

        # ── Completed Scans with realistic finding counts ─────────────────────
        severity_sets = [
            {"critical": 2, "high": 5, "medium": 8, "low": 4, "secrets": 3, "misconfigs": 2, "score": 62.0},
            {"critical": 0, "high": 3, "medium": 6, "low": 7, "secrets": 1, "misconfigs": 3, "score": 78.5},
            {"critical": 1, "high": 2, "medium": 4, "low": 3, "secrets": 0, "misconfigs": 1, "score": 84.0},
        ]

        admin_res = await db.execute(select(User).where(User.email == "admin@demo.com"))
        admin_user = admin_res.scalar_one_or_none()
        admin_id = admin_user.id if admin_user else tenant.id  # fallback to tenant id

        for i, (repo, sev) in enumerate(zip(repos_created, severity_sets)):
            scan_time = datetime.now(timezone.utc) - timedelta(hours=i * 6 + 2)
            scan = Scan(
                tenant_id=tenant.id,
                repo_id=repo.id,
                triggered_by=admin_id,
                branch="main",
                status="completed",
                started_at=scan_time,
                completed_at=scan_time + timedelta(minutes=random.randint(3, 12)),
                duration_secs=random.randint(180, 720),
                scanners_run={"sast": "completed", "secrets": "completed", "deps": "completed", "container": "completed", "cicd": "completed"},
                critical_count=sev["critical"],
                high_count=sev["high"],
                medium_count=sev["medium"],
                low_count=sev["low"],
                secret_count=sev["secrets"],
                misconfig_count=sev["misconfigs"],
                security_score=sev["score"],
                ai_summary=(
                    f"Scan of {repo.full_name} found {sev['critical']} critical and {sev['high']} high severity issues. "
                    f"Primary concerns include exposed secrets and outdated dependencies. "
                    f"Overall security posture requires attention in dependency management and secrets handling."
                ),
                ai_suggestions=[
                    "Rotate any exposed credentials immediately and add them to a secrets manager",
                    "Enable Dependabot alerts and auto-merge for patch-level dependency updates",
                    "Add pre-commit hooks to prevent secrets from being committed",
                    "Pin Docker base images to specific digests for reproducible builds",
                    "Require code review approvals on the main branch",
                ],
            )
            db.add(scan)

        # ── ML Predictions (needed for ML Insights page) ──────────────────────
        from app.models.ml_prediction import MLPrediction

        prediction_scenarios = [
            {
                "model_name": "cost_predictor",
                "prediction_type": "cost_forecast",
                "input_data": {"historical_costs": [3200, 3450, 3600, 3800, 4100, 3950], "months_ahead": 3},
                "output_data": {
                    "predicted_cost": 4320.0, "confidence": 0.87,
                    "lower_bound": 3950.0, "upper_bound": 4690.0,
                    "trend": "increasing", "change_pct": 9.4,
                    "breakdown": {"EC2": 1850.0, "S3": 620.0, "RDS": 940.0, "CloudFront": 380.0, "Other": 530.0},
                },
                "confidence": 0.87,
            },
            {
                "model_name": "anomaly_detector",
                "prediction_type": "anomaly_detection",
                "input_data": {"data_points": 90, "method": "isolation_forest"},
                "output_data": {
                    "anomalies_detected": 3, "confidence": 0.79,
                    "anomaly_dates": ["2025-04-12", "2025-04-28", "2025-05-08"],
                    "severity": "medium",
                    "description": "3 cost anomalies detected in the past 90 days — EC2 usage spikes on weekends",
                },
                "confidence": 0.79,
            },
            {
                "model_name": "resource_optimizer",
                "prediction_type": "resource_optimization",
                "input_data": {"services": ["EC2", "RDS", "ECS"], "lookback_days": 30},
                "output_data": {
                    "savings_opportunity": 847.0, "confidence": 0.82,
                    "recommendations": [
                        {"service": "EC2", "action": "rightsizing", "saving": 420.0},
                        {"service": "RDS", "action": "reserved_instance", "saving": 310.0},
                        {"service": "ECS", "action": "spot_instances", "saving": 117.0},
                    ],
                },
                "confidence": 0.82,
            },
        ]

        for i, pred_data in enumerate(prediction_scenarios):
            db.add(MLPrediction(
                tenant_id=tenant.id,
                model_name=pred_data["model_name"],
                prediction_type=pred_data["prediction_type"],
                input_data=pred_data["input_data"],
                output_data=pred_data["output_data"],
                confidence=pred_data["confidence"],
                predicted_at=datetime.now(timezone.utc) - timedelta(hours=i * 3),
            ))

        await db.commit()
        print(f"\n✓ Seed data created for tenant: {tenant.name} (ID: {tenant.id})")
        print("  Admin: admin@demo.com / demo123!")
        print("  Viewer: viewer@demo.com / demo123!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed UniOps demo data")
    parser.add_argument("--tenant-id", default=None, help="Existing tenant ID to seed into")
    args = parser.parse_args()
    asyncio.run(seed_data(args.tenant_id))
