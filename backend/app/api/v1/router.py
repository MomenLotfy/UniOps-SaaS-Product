from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, companies, integrations, pipelines, pods,
    threats, vulnerabilities, compliance, costs, savings,
    ml, alerts, audit, webhooks, billing, health,
    security_scan,
)

api_router = APIRouter()

api_router.include_router(health.router,         prefix="/health",        tags=["Health"])
api_router.include_router(auth.router,           prefix="/auth",          tags=["Auth"])
api_router.include_router(users.router,          prefix="/users",         tags=["Users"])
api_router.include_router(companies.router,      prefix="/companies",     tags=["Companies"])
api_router.include_router(integrations.router,   prefix="/integrations",  tags=["Integrations"])
api_router.include_router(pipelines.router,      prefix="/pipelines",     tags=["Pipelines"])
api_router.include_router(pods.router,           prefix="/kubernetes/pods", tags=["Pods"])
api_router.include_router(threats.router,        prefix="/threats",       tags=["Security"])
api_router.include_router(vulnerabilities.router,prefix="/vulnerabilities",tags=["Security"])
api_router.include_router(compliance.router,     prefix="/compliance",    tags=["Security"])
api_router.include_router(security_scan.router,  prefix="/security",      tags=["DevSecOps"])
api_router.include_router(costs.router,          prefix="/costs",         tags=["Cost"])
api_router.include_router(savings.router,        prefix="/savings",       tags=["Cost"])
api_router.include_router(ml.router,             prefix="/ml",            tags=["ML"])
api_router.include_router(alerts.router,         prefix="/alerts",        tags=["Alerts"])
api_router.include_router(audit.router,          prefix="/audit-logs",    tags=["Audit"])
api_router.include_router(webhooks.router,       prefix="/webhooks",      tags=["Webhooks"])
api_router.include_router(billing.router,        prefix="/billing",       tags=["Billing"])
