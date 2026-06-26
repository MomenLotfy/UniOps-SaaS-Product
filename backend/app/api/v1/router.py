from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, companies, integrations, pipelines, pods,
    threats, vulnerabilities, compliance, costs, savings,
    ml, alerts, audit, webhooks, billing, health,
    security_scan, api_keys, clusters, observability, devops_alerts, gitops,
    catalog, metrics, logs, assets,
    security_policies, security_exceptions, security_reports, security_posture,
    k8s_security, sbom, repository_risk,
    ownership, sla, tickets,
    copilot, remediation,
)

api_router = APIRouter()

api_router.include_router(health.router,             prefix="/health",            tags=["Health"])
api_router.include_router(auth.router,               prefix="/auth",              tags=["Auth"])
api_router.include_router(users.router,              prefix="/users",             tags=["Users"])
api_router.include_router(companies.router,          prefix="/companies",         tags=["Companies"])
api_router.include_router(integrations.router,       prefix="/integrations",      tags=["Integrations"])
api_router.include_router(pipelines.router,          prefix="/pipelines",         tags=["Pipelines"])
api_router.include_router(pods.router,               prefix="/kubernetes/pods",   tags=["Pods"])

# ── Security — Core Findings ─────────────────────────────────────────────────
api_router.include_router(threats.router,            prefix="/threats",           tags=["Security - Threats"])
api_router.include_router(vulnerabilities.router,    prefix="/vulnerabilities",   tags=["Security - Vulnerabilities"])
api_router.include_router(compliance.router,         prefix="/compliance",        tags=["Security - Compliance"])
api_router.include_router(security_scan.router,      prefix="/security",          tags=["Security - Scanner"])

# ── Security — Governance & Posture ─────────────────────────────────────────
api_router.include_router(security_policies.router,  prefix="/security-policies", tags=["Security - Policies"])
api_router.include_router(security_exceptions.router,prefix="/security-exceptions",tags=["Security - Exceptions"])
api_router.include_router(security_reports.router,   prefix="/security-reports",  tags=["Security - Reports"])
api_router.include_router(security_posture.router,   prefix="/security-posture",  tags=["Security - Posture"])

# ── Cost & FinOps ────────────────────────────────────────────────────────────
api_router.include_router(costs.router,              prefix="/costs",             tags=["Cost"])
api_router.include_router(savings.router,            prefix="/savings",           tags=["Cost"])

# ── AI & ML ──────────────────────────────────────────────────────────────────
api_router.include_router(ml.router,                 prefix="/ml",                tags=["ML"])
api_router.include_router(copilot.router,            prefix="/copilot",           tags=["Security Copilot"])


# ── Operations ───────────────────────────────────────────────────────────────
api_router.include_router(alerts.router,             prefix="/alerts",            tags=["Alerts"])
api_router.include_router(audit.router,              prefix="/audit-logs",        tags=["Audit"])
api_router.include_router(webhooks.router,           prefix="/webhooks",          tags=["Webhooks"])
api_router.include_router(billing.router,            prefix="/billing",           tags=["Billing"])
api_router.include_router(api_keys.router,           prefix="/api-keys",          tags=["API Keys"])
api_router.include_router(clusters.router,           prefix="/clusters",          tags=["Clusters"])
api_router.include_router(observability.router,      prefix="/observability",     tags=["Observability"])
api_router.include_router(devops_alerts.router,      prefix="/devops-alerts",     tags=["DevOps Alerts"])
api_router.include_router(gitops.router,             prefix="/gitops",            tags=["GitOps"])
api_router.include_router(catalog.router,            prefix="/catalog",           tags=["Catalog"])
api_router.include_router(metrics.router,            prefix="/metrics",           tags=["Metrics"])
api_router.include_router(logs.router,               prefix="/logs",              tags=["Logs"])
api_router.include_router(assets.router,             prefix="/assets",            tags=["Assets"])
api_router.include_router(k8s_security.router,       prefix="/k8s",               tags=["Kubernetes Security"])
api_router.include_router(sbom.router,               prefix="/sbom",              tags=["Security - SBOM"])
api_router.include_router(repository_risk.router,    prefix="/repos/risk",        tags=["Security - Risk Ratings"])
api_router.include_router(ownership.router,          prefix="/ownership",          tags=["Security - Ownership"])
api_router.include_router(sla.router,                prefix="/sla",                tags=["Security - SLA"])
api_router.include_router(tickets.router,            prefix="/tickets",            tags=["Security - Tickets"])
api_router.include_router(remediation.router,         prefix="/remediation",       tags=["Security - Remediation"])
