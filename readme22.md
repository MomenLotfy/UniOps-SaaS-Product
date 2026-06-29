# 📐 UniOps — Master Architecture & Product Roadmap Review

> **Audit period**: as of current repository state (commit lineage through `546f8762`).
> **Reviewer perspective**: Chief Software Architect / Enterprise TPM.
> **Scope**: This is **NOT** a code review or production-readiness review. It is a top-down reconstruction of the platform as it actually exists today, an honesty-based accounting of what is complete vs. partial vs. obsolete, and a reissued roadmap for the next phase.
> **Method**: Static code archaeology of `backend/app`, `artifacts/uniops/src`, `infra/k8s`, `docs/`, `alembic/versions`, and the most recent commits.

---

## 1. Executive Summary

UniOps was originally a Security Dashboard. Through multiple sprints it grew—deliberately and sometimes organically—into a far larger system that today presents **three coexisting personalities**:

1. A **CloudOps / DevOps Control Tower** (Command Center, Cost Center, ML Insights, DevOps Center, Cluster Observability, Catalogs, Pipelines, Pods, GitOps, ArgoCD-driven deployments).
2. A **Security Platform** (Threats, Vulnerabilities, Policies, Exceptions, Reports, Posture, K8s Security, SBOM, Repository Risk, Ownership, SLA, Tickets, Remediation, Knowledge Graph, Security Copilot, Scan Engine, Asset Discovery).
3. A **Decision-Automation Subsystem** that the engineering team calls "EPIC 10 / Module 0" — Decision Engine → Decision Strategy → Decision Approval → Execution Orchestration, with read-only APIs and a Sprint 3 observation layer, but **no actual remediation or Git side effects yet**.

The platform also ships production-grade infrastructure: Helm-free raw Kubernetes manifests (api / celery-worker / celery-beat / backup CronJob / overlay per env), Prometheus rules + adapter, OpenTelemetry + Sentry + structlog observability, rate limiting, 16 Alembic migrations, a `docs/` runbook / RPO / DR set, and an end-to-end Docker Compose.

**The backbone is solid and getting stronger.** The product surface is far wider than the original roadmap; the codebase has more partial modules than it has mature ones, and the consumer-facing depth (remediation that actually patches code, a real-time intel pipeline, an enterprise-class workflow engine) is still missing. Most of the platform's value is concentrated in a small number of deeply-built subsystems and a much larger number of wide-but-thin ones.

**Overall Architecture Score: 64 / 100** — *Production-Mature Foundations, Beta-Grade Product.*
**Product Maturity Level: Beta, transitioning toward Production** for the security-data plane; **Prototype → Alpha** for autonomous remediation.

---

## 2. Current Architecture (Reconstructed from Code)

### 2.1 Architecture Map (verbal)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            Frontend (React + Vite)                         │
│            artifacts/uniops → CommandCenter / DevOpsCenter /                │
│            SecurityCenter / CostCenter / MLInsights + Settings/             │
│            Company/Admin/Auth.                                              │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application Layer                           │
│   app/api/v1 → ~40 routers (auth, users, integrations, security.*,         │
│   intelligence, decisions, strategies, approvals, executions, ...)          │
│   app/api/webhooks  (GitHub / GitLab / Slack / Stripe)                      │
│   app/api/v1/websocket (manager + handlers)                                │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
   ┌────────────────────────────────┼─────────────────────────────────────┐
   │                                │                                     │
   ▼                                ▼                                     ▼
┌──────────────────────┐  ┌────────────────────────┐  ┌──────────────────────────┐
│  Domain Modules      │  │  Cross-Cutting          │  │ Infrastructure           │
│  (app/modules,       │  │  (app/core, app/        │  │ (app/integrations,       │
│   app/services)      │  │   platform,             │  │  Celery, Redis, K8s)     │
│                      │  │   app/observability)    │  │                          │
│ • Decision Engine    │  │ • Database/Async        │  │ • Git/GitLab/ArgoCD      │
│   (Module 0 / P3)    │  │ • Exceptions            │  │ • K8s (sync, watcher)    │
│ • Decision Strategy  │  │ • Scheduler             │  │ • AWS (Cost Explorer,    │
│   (Module 0 / P4)    │  │ • Cache / Redis         │  │   Security Hub)          │
│ • Decision Approval  │  │ • Event Bus (in-proc)   │  │ • Semgrep / Trivy        │
│   (Module 0 / P5)    │  │ • Security core         │  │ • Prometheus / Loki      │
│ • Execution          │  │ • Pagination            │  │ • Slack / Email          │
│   Orchestration      │  │ • Transaction Manager   │  │ • Stripe                 │
│   (Module 0 / P6)    │  │ • Base classes          │  │                          │
│ • Security Intel     │  │ • Observability stack   │  │                          │
│ • Investigation      │  │ • Logging               │  │                          │
│ • Knowledge Graph    │  │ • Tracing               │  │                          │
│ • Impact / Risk      │  │ • Metrics (Prom)        │  │                          │
│ • Scanning / SBOM    │  │ • Sentry                │  │                          │
│ • Deployment Engine  │  │ • Middleware (logging,  │  │                          │
│ • ML service         │  │   audit, rate-limit,    │  │                          │
│ • Security Copilot   │  │   tenant)               │  │                          │
└──────────────────────┘  └────────────────────────┘  └──────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     Persistence (PostgreSQL 16)                             │
│   16 Alembic migrations, 60+ ORM models, Multi-tenant (tenant_id)          │
│   Strategy / Approval / Execution decoupled into their own models          │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                  Async Runtime (Celery + APScheduler + Beat)               │
│   redis:// broker + result. Scan / sync / insight jobs.                   │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                  K8s + Helm-less Manifests (infra/k8s)                     │
│   api (HPA 3-20), celery-worker, celery-beat (singleton),                 │
│   backup (CronJob), 3 overlays (dev/staging/production),                   │
│   Prometheus rules + adapter, NetworkPolicies, PDB, ServiceAccount.        │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Identified Major Subsystems

| # | Subsystem | Location | Notes |
|---|---|---|---|
| 1 | **Authentication & Identity** | `app/api/v1/endpoints/auth.py`, `services/auth_service.py` | JWT (HS256), refresh tokens, 2FA (TOTP), Redis-backed reset/invite, multi-tenant |
| 2 | **User / Company / Team / RBAC** | `models/user.py`, `tenant.py`, `role.py`, `permission.py`, `constants/permissions.py`, `lib/permissions.ts` | Roles, permissions constants; permission.ts mirrors frontend |
| 3 | **API Keys** | `endpoints/api_keys.py` | Scoped, tenant-bound |
| 4 | **Integrations Platform** | `services/integration_service.py`, `endpoints/integrations.py`, `app/integrations/{github,gitlab,aws,kubernetes,gitops,slack,stripe,email,observability,scanners}` | Single source-of-truth service for credentials, sync dispatch |
| 5 | **Asset Discovery & Inventory** | `services/asset_discovery_service.py`, `models/asset.py`, `endpoints/assets.py` | Pulls repos from Git/GitLab, AWS resources, K8s clusters/pods/namespaces, derived Docker images |
| 6 | **Scan Engine (Repo/SCA/K8s)** | `services/scan_engine.py`, `scan_service.py`, `integration_service.sync_repos_for_tenant`, `integrations/scanners/{semgrep,trivy}` + `k8s_security_service.py` | Trivy + Semgrep integration; K8s native + optional Kubescape, kube-bench, kube-hunter |
| 7 | **Vulnerability / Threat Core** | `models/threat.py`, `vulnerability.py`, endpoints `threats.py`, `vulnerabilities.py` | Severity, status, CVSS, CWE, exploit refs |
| 8 | **SBOM** | `services/sbom_service.py`, `models/sbom.py`, `endpoints/sbom.py` | Syft binary with manifest-parser fallback (CycloneDX + SPDX) |
| 9 | **Risk (Repository + Tenant)** | `services/risk_service.py`, `repository_risk.py`, `risk/` (subcomponents), `models/risk.py`, `repository_risk*.py` | Weighted penalty scoring, history, tier-level thresholds |
| 10 | **Knowledge / Asset Graph** | `services/graph/`, `services/impact/`, `services/investigation/`, `models/graph.py`, `models/impact.py`, `models/investigation.py`, endpoints `graph.py`, `impact.py`, `investigation.py` | Full graph → traversal, investigation sessions, correlation, impact blast radius |
| 11 | **Policies / Exceptions / Compliance / Posture** | `services/security_policy_service.py`, `security_exception_service.py`, `policy_evaluator.py`, `security_posture_service.py`, `models/security_*.py`, `models/compliance.py`, endpoints `security_policies.py`, `security_exceptions.py`, `compliance.py`, `security_posture.py` | Built-in policies (no_secrets, block_critical_cves, require_signed_images, require_mfa, require_private_repos) |
| 12 | **Reports** | `services/security_report_service.py`, `models/security_report.py`, endpoints `security_reports.py` | Report types: exec summary, threat assessment, vuln report, compliance, posture, exception mgmt, full audit |
| 13 | **SLA / Tickets / Ownership / Remediation** | `services/sla_service.py`, `ticket_service.py`, `ownership_service.py`, `remediation_endpoint_remediation.py` (endpoints/remediation.py), `models/finding_sla.py` etc. | Tied to severity tiers; Slack/email/Jira/AzureDevOps/Linear ticket clients |
| 14 | **Catalog & Deployment Engine** | `services/catalog_service.py`, `cluster_service.py`, `core/deployment_engine/{service,worker,argocd,generators,git_provider}` | Resume in-flight deployments, ArgoCD bridging, GitProvider abstraction |
| 15 | **Pipelines / Pods / GitOps / Cluster** | `endpoints/{pipelines,pods,gitops,clusters}.py`, `services/kubernetes_service.py`, `integrations/kubernetes/{client,watcher}.py` | K8s API + watcher + ArgoCD client |
| 16 | **Cost / FinOps** | `services/cost_service.py`, `billing_service.py`, `savings.py`, `models/cost_*.py`, `integrations/aws/cost_explorer.py`, endpoints `costs.py`, `savings.py`, `billing.py` | Cost anomaly + recommendations + Stripe billing |
| 17 | **Observability** | `services/observability_service.py`, `endpoints/observability.py`, `integrations/observability/{prometheus,loki}.py`, `models/deployment_log.py`, `devops_alert.py` | Prometheus + Loki piping + in-house observability dashboard |
| 18 | **AI / ML** | `services/ml_service.py`, `ml_endpoints.py` endpoints, `tasks/train_ml_models.py`, `tasks/sync_ml_insights.py`, `models/ml_*.py`, `endpoints/ml.py`, `models/copilot.py` (+ `services/copilot_*.py`) | Predictions, recommendations, patterns, correlations; Security Copilot (conversations + context builder) |
| 19 | **Security Intelligence Platform** | `services/intelligence/{service,cache,providers,normalization,enrichment,sync}`, `models/intelligence.py`, endpoints `intelligence.py` | Provider registry, normalization with provenance, enrichment pipeline, merge engine, version resolver |
| 20 | **Investigation Engine** | `services/investigation/{engine,service,session,query,search,timeline,correlation,filter}` | Sessions, query planner, search, timeline, correlation |
| 21 | **Decision Engine** (Module 0 / P3) | `app/modules/security/decision_engine/{api,models,pipeline,services}` | Rule engine + policy engine + decision manager + statistics |
| 22 | **Decision Strategy Engine** (Module 0 / P4) | `app/modules/security/decision_strategy/{api,models,services}` | Strategy registry, 10-dimension scoring, comparator, 7-stage pipeline, 13 models, 18 services |
| 23 | **Decision Approval Engine** (Module 0 / P5) | `app/modules/security/decision_approval/{api,models,services}` | 7-dimension scoring, 9-state lifecycle, 15 models, 17 services, 7 default evaluators |
| 24 | **Execution Orchestration** (Module 0 / P6) | `app/modules/security/execution_orchestration/{api,models,services}` | 12 readiness checks, 10-state lifecycle, 12 models, 16 services; produces immutable `ExecutionPackage` — does NOT execute |
| 25 | **Observability Stack (Sprint 3)** | `app/observability/{logging,tracing,metrics,sentry,context,formatters,instrumentation,startup_validator}` | structlog→loguru fallback, Prometheus registry, OTEL, Sentry, ContextVars |
| 26 | **Shared Platform (Sprint 3 R35)** | `app/platform/{base_cache,base_pipeline,base_lifecycle,base_audit_service,base_statistics_service,thread_safe_registry}` | Reusable abstractions over engines |
| 27 | **Notifications** | `services/notification_service.py`, `integrations/{email,slack}` | Email (SendGrid), Slack (webhook + bot), WebSocket |
| 28 | **Webhooks (Inbound)** | `app/api/webhooks/{github,gitlab,stripe,slack}.py` | Receives from external systems |
| 29 | **Webhooks (Outbound)** | `services/webhook_service.py`, `models/webhook.py` | Used by integrations |
| 30 | **Audit / Rate-limit / Tenant Middleware** | `app/middleware/{audit,rate_limit,tenant,logging,cors}.py` | Per-tenant + per-endpoint Redis-backed limiter, fail-open on Redis down |
| 31 | **Caching** | `app/core/{cache,intelligence_cache,redis_client}` | Generic TTL cache + IntelligenceCache |
| 32 | **Scheduling** | `app/core/scheduler.py`, `app/tasks/*`, Celery `app/tasks/worker.py`, `app/core/celery_app.py` | APScheduler for dev, Celery beat for prod |
| 33 | **Deployment Engine Worker** | `core/deployment_engine/worker.py`, started from `main.lifespan` | Recover stuck in-flight deployments |
| 34 | **Audit Log / Compliance** | `models/audit_log.py`, `middleware/audit.py`, `services/audit_service.py` | Request-level audit table |
| 35 | **Alerts / DevOps Alerts** | `services/alert_service.py`, `models/alert.py`, `devops_alert.py`, `endpoints/{alerts,devops_alerts}.py` | Operational alerting |
| 36 | **API Documentation** | `app/api/v1/router.py`, README files inside modules | All routers + auto-generated Swagger |
| 37 | **Docs-as-Code** | `docs/{RUNBOOK,RPO_RTO,DISASTER_RECOVERY,README}.md`, `infra/k8s/README.md`, per-module `README.md` | Production-grade docs exist |
| 38 | **Analytics / Logs / Metrics (query)** | `endpoints/{logs,metrics,catalog}.py` | High-cardinality safe log/metric querying |

### 2.3 Public REST Surface (declared in `app/api/v1/router.py`)

```
/auth, /users, /companies, /integrations, /pipelines, /kubernetes/pods
/threats, /vulnerabilities, /compliance, /security (scan)
/security-policies, /security-exceptions, /security-reports, /security-posture
/costs, /savings, /ml, /copilot
/alerts, /audit-logs, /webhooks, /billing, /api-keys, /clusters, /observability,
/devops-alerts, /gitops, /catalog, /metrics, /logs, /assets
/k8s, /sbom, /repos/risk, /ownership, /sla, /tickets, /remediation, /intelligence
/security/decisions, /security/decision-strategies/*, /security/decision-approvals/*, /security/execution-packages/*
+ inbound webhooks: /webhooks/{github,gitlab,stripe,slack}
+ WS: /ws/{tenant_id}
+ /metrics (Prometheus), /api/v1/health/{live,ready,startup}
```

---

## 3. Architecture Diagram

```
                        ┌──────────────────────────┐
                        │   External Producers     │
                        │ (GitHub, GitLab, Stripe, │
                        │  Slack, K8s API, AWS)    │
                        └────────────┬─────────────┘
                                     │ webhooks / SDKs
                                     ▼
       ┌──────────────────────────────────────────────────────────────┐
       │                FastAPI App (Uvicorn, asyncio)               │
       │                                                              │
       │  ┌──────────────────────┐    ┌─────────────────────────┐    │
       │  │ Webhooks (inbound)   │    │  WebSocket Bridge       │    │
       │  └──────────┬───────────┘    │  (event_bus → ws)       │    │
       │             │                └─────────────────────────┘    │
       │             ▼                                                │
       │  ┌──────────────────────────────────────────────────────┐   │
       │  │            Middleware Stack                          │   │
       │  │  • Sentry / Tracing / Structlog                      │   │
       │  │  • RateLimit (per-tenant, per-endpoint)              │   │
       │  │  • CORS / Logging / Audit / Tenant-Routing           │   │
       │  └──────────────────────────────────────────────────────┘   │
       │                                                              │
       │  ┌──────────────────────────────────────────────────────┐   │
       │  │           Domain Modules (verticals)                 │   │
       │  │                                                      │   │
       │  │   Auth/Identity ──┐                                  │   │
       │  │                    ├──► Company / RBAC              │   │
       │  │   Integrations ───┤                                  │   │
       │  │                    ├──► Asset Discovery             │   │
       │  │   Billing (Stripe)─┤                                  │   │
       │  │                    ├──► Scan / K8s / SBOM           │   │
       │  │   Clusters/K8s ───┤                                  │   │
       │  │                    ├──► Threats / Vulns / SLA       │   │
       │  │   Pipelines/Pods ──┤                                  │   │
       │  │                    ├──► Risk / Impact / Graph        │   │
       │  │   Git/GitOps ──────┤                                  │   │
       │  │                    ├──► Policies / Exceptions       │   │
       │  │   Observability ───┤                                  │   │
       │  │                    ├──► Reports / Posture            │   │
       │  │   ML/Copilot ──────┤                                  │   │
       │  │                    ├──► Investigations              │   │
       │  │                    ├──► Security Intelligence        │   │
       │  │                    └──► Tickets / Remediation        │   │
       │  │                                                      │   │
       │  │   EPIC 10 Module 0 — Decision Automation            │   │
       │  │     Decision Engine ─► Strategy ─► Approval ─►      │   │
       │  │     Execution Orchestration  (no execution yet)      │   │
       │  └──────────────────────────────────────────────────────┘   │
       │                                                              │
       │  ┌──────────────────────────────────────────────────────┐   │
       │  │              Shared Platform Layer                   │   │
       │  │   BaseCache · BasePipeline · BaseLifecycle ·         │   │
       │  │   BaseAuditService · BaseStatisticsService ·         │   │
       │  │   ThreadSafeRegistry · TransactionManager            │   │
       │  └──────────────────────────────────────────────────────┘   │
       │                                                              │
       │  ┌──────────────────────────────────────────────────────┐   │
       │  │                Cross-Cutting                         │   │
       │  │  Config · Exceptions · Logging · Metrics · Tracing ·  │   │
       │  │  Sentry · Pagination · Security · Redis · Scheduler  │   │
       │  └──────────────────────────────────────────────────────┘   │
       └──────────────┬───────────────────────────┬───────────────────┘
                      │                           │
                      ▼                           ▼
        ┌────────────────────────┐    ┌─────────────────────────────┐
        │    PostgreSQL 16       │    │        Redis 7              │
        │  (16 Alembic revisions │    │  Broker + Result Cache +     │
        │   60+ models)          │    │  Rate-Limit + Session +      │
        └────────────────────────┘    │  Idempotency                 │
                                      └─────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────────────────────────────────┐
        │           Async Runtime                                   │
        │  • Celery Worker (concurrency=2 default)                  │
        │  • Celery Beat (singleton, persistent schedule)           │
        │  • APScheduler (dev / fallback)                           │
        │  • Deployment Engine Worker (recover stuck services)      │
        │  • EventBus wildcard WebSocket bridge                     │
        └──────────────────────────────────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────────────────────────────────┐
        │       Kubernetes                                          │
        │  api Deployment (3-20, HPA, PDB, NetworkPolicy)           │
        │  celery-worker Deployment, celery-beat (singleton)       │
        │  backup CronJob (PVC + S3)                               │
        │  overlays dev / staging / production                     │
        └──────────────────────────────────────────────────────────┘
```

---

## 4. Implemented Modules (Complete / Mostly Complete)

| # | Module | Status | Confidence | Evidence |
|---|---|---|---|---|
| 1 | Authentication / 2FA / JWT refresh | **Implemented (95%)** | High | `services/auth_service.py`, reset+invite tokens, 2FA endpoint, Redis-backed |
| 2 | Multi-tenant isolation (tenant_id everywhere) | **Implemented (90%)** | High | Models all carry `tenant_id`, middleware `tenant.py`, migrations 002/008/014 |
| 3 | API Keys | **Implemented (90%)** | High | `endpoints/api_keys.py` + model |
| 4 | Integrations Platform (CRUD + sync dispatch) | **Implemented (85%)** | High | `integration_service.py` is single source of truth, encrypts creds, tests, sync dispatch |
| 5 | GitHub / GitLab / K8s / AWS / Slack / Stripe / Stripe-Webhook / SendGrid integrations | **Implemented (75-90%)** | High-Historical | Clients present in `app/integrations/`; github app uses GitHub App or PAT |
| 6 | GitOps (ArgoCD client) | **Mostly implemented (75%)** | Medium | `argocd_client.py` + `DeploymentEngine` + reconciler worker |
| 7 | Scan Engine (Repository/Trivy/Semgrep) | **Implemented (80%)** | High | `scan_engine.py`, `scan_service.py`, `remediation_endpoint_remediation`; runs against actual binary + manifest-parser fallback |
| 8 | Vulnerability / Threat ingestion + listing | **Implemented (85%)** | High | Endpoints + service path |
| 9 | SBOM (CycloneDX + SPDX) | **Implemented (80%)** | High | Syft + manifest-parser fallback |
| 10 | Security Policies (CRUD, built-in templates, evaluator) | **Implemented (80%)** | High | `services/policy_evaluator.py`, `services/security_policy_service.py` with 5 built-ins |
| 11 | Security Exceptions (waivers) | **Implemented (80%)** | High | Endpoint, model, service |
| 12 | Compliance Reports + framework scoring | **Implemented (75%)** | Medium | `compliance.py` endpoint + report service |
| 13 | Security Posture (overall scoring, breakdown) | **Implemented (75%)** | Medium | `security_posture_service.py` |
| 14 | Security Reports (exec/threat/vuln/compliance/posture/exception/audit) | **Implemented (80%)** | High | 7 report types |
| 15 | Risk (Repository + sub-components) | **Implemented (80%)** | High | Weighted penalty scoring, history, trend detection |
| 16 | Impact Analysis (blast radius, reachability, dependency) | **Implemented (75%)** | Medium | `services/impact/*` + endpoint |
| 17 | Knowledge Graph | **Implemented (75%)** | Medium | `services/graph/*` |
| 18 | Investigation (query/search/timeline/correlation/sessions/saved queries/bookmarks) | **Implemented (75%)** | Medium | Models + engine |
| 19 | SLA Tracking | **Implemented (80%)** | High | Critical 24h / High 7d / Medium 30d / Low 90d |
| 20 | Tickets (Slack + Email + Jira/AzureDevOps/Linear clients) | **Implemented (75%)** | High | `ticket_service.py` + ticket_clients |
| 21 | Ownership | **Implemented (75%)** | Medium | `ownership_service.py` |
| 22 | Remediation (read-mostly) | **Mostly implemented (60%)** | Medium | Endpoint exists; heavy lifting is still the unfinished EPIC 10 pipeline (see §6) |
| 23 | Asset Discovery + Inventory | **Implemented (80%)** | High | Provider-agnostic upserts from Git/GitLab/AWS/K8s |
| 24 | Cost / FinOps | **Implemented (80%)** | High | AWS Cost Explorer, anomalies, recommendations, savings, Stripe billing |
| 25 | Pipelines + Pods + Cluster + GitOps | **Implemented (75%)** | High | Real Kubernetes API + ArgoCD + watcher |
| 26 | Observability ingestion (Prom + Loki) + dashboards | **Implemented (80%)** | High | In-house observability service |
| 27 | ML Service (patterns, predictions, correlations, recommendations) | **Implemented (75%)** | Medium | With debounce + per-tenant training, drift over Celery |
| 28 | Security Copilot (conversations + context builder) | **Mostly implemented (60%)** | Medium | Conversation persistence + context, but the LLM call site is a thin proxy |
| 29 | Notifications (email/Slack/WS) | **Implemented (85%)** | High | `notification_service.py` + integrations |
| 30 | Outbound / Inbound Webhooks | **Implemented (85%)** | High | Bi-directional webhook system |
| 31 | Audit Logs (request-level + entity-level) | **Implemented (90%)** | High | Middleware + service |
| 32 | Rate Limit (per-tenant + per-endpoint + burst + sustained) | **Implemented (90%)** | High | Redis-backed w/ fail-open |
| 33 | Health (live/ready/startup, /metrics) | **Implemented (95%)** | High | Used in K8s probes |
| 34 | Alembic Migrations (16 revisions) | **Implemented (90%)** | High | 001..015 + copilot migration |
| 35 | Docker Compose (db/redis/backend/celery_worker/celery_beat/frontend) | **Implemented (95%)** | High | Production-ready compose |
| 36 | Kubernetes Manifests (api/worker/beat/backup/observability, dev/staging/prod overlays) | **Implemented (90%)** | High | `infra/k8s/` |
| 37 | Helm-less Observability (PrometheusRule + prometheus-adapter) | **Implemented (85%)** | High | `infra/k8s/observability/` |
| 38 | Runbook / RPO RTO / Disaster Recovery | **Implemented (90%)** | High | `docs/` |
| 39 | Decision Engine (Module 0 / P3) | **Implemented (90%)** | High | 7-stage pipeline, transaction manager, statistics, 13 models; tested in `tests/integration/test_decision_pipeline.py` |
| 40 | Decision Strategy (Module 0 / P4) | **Implemented (88%)** | High | 13 models, 18 services, registry, 10-dim scoring; route + integration test |
| 41 | Decision Approval (Module 0 / P5) | **Implemented (85%)** | High | 15 models, 17 services, 7 default evaluators, idempotency; notifications stub |
| 42 | Execution Orchestration (Module 0 / P6) | **Implemented (85%)** | High | 12 models, 16 services, 12 readiness checks, builds immutable packages |
| 43 | Shared Platform Components (R35) | **Implemented (80%)** | High | `BaseCache`, `BaseLifecycleManager`, `BaseAuditService`, `BaseStatisticsService`, `BasePipeline`, `ThreadSafeRegistry`, `TransactionManager` |

---

## 5. Partially Implemented Modules

| Module | Status | Confidence | What's missing |
|---|---|---|---|
| **Real-time Intelligence Providers** | Partial — Architecture-only (35%) | High | Only NVD + OSV mappers are wired (see `service.py`); 8 providers (`cisa`, `capec`, `cwe`, `epss`, `ghsa`, `owasp`, `vendor`) are stubs returning `None`. Provider manager's loader exists but the real HTTP/SOAP/etc adapters are not done. |
| **Investigation `session/` folder** | Stub (40%) | Medium | `services/investigation/session/` is empty; `session.py` duplicates the same functions in `session/`. |
| **Investigation `optimizer`** | Stub (40%) | Medium | Single 12-line `optimizer.py` no-op |
| **ML Drift / Model Retraining Loop** | Partial (50%) | Medium | `train_ml_models.py` exists but is not wired to periodic retrain; no model-versioning |
| **Copilot LLM connection** | Partial (60%) | Medium | Conversation + context builder exist; no clear LLM provider plug-in (which model, which key) |
| **Remediation execution** | Stub (45%) | Medium | Endpoint exists but real patch / git / PR creation is missing |
| **Deployment Engine worker git-provider** | Partial | Medium | `git_provider.py` + `generators.py` exist but commit/push workflow is incomplete |
| **Caching** | Partial (70%) | Medium | Generic `cache.py` + `intelligence_cache.py` exist; no real cluster cache (`intelligence_cache.py` looks like a placeholder) |
| **Cluster Service** | Mostly implemented (75%) | Medium | Reads clusters but watcher bootstrap intentionally disabled |
| **Workspace Multi-tenancy (SSO/SCIM)** | Missing (15%) | Low | No SAML, OIDC, SCIM endpoints |
| **License Management / Billing Dunning** | Partial — Stripe present, no license enforcement (40%) | Medium | Stripe integration is functional, no entitlement engine |
| **DevOps Alerts (PrometheusRule→AlertManager bridge)** | Partial (50%) | Medium | Stored as data; routing to Slack not end-to-end |
| **Email Templates** | Partial (65%) | Medium | Plain HTML only, no i18n, no in-app digest |
| **Audit log retention** | Stub — no auto-purge (40%) | Medium | `cleanup_old_data.py` exists but retention is configurable, not enforced |
| **Alembic CI gating** | Partial | Medium | Migration revision injection but no schema-diff CI |
| **Frontend Tests / Playwright** | Missing (5%) | High | Frontend has no test suite |

---

## 6. Missing Modules (Tier-1)

These exist only as words in this report and README files, not as code:

1. **Real patch generation / Patch Generator** — no PR-creator, no diff engine, no PR-approval flow
2. **Validation Engine** — no automated test runner to "validate the patch actually fixes the CVE without breaking the build"
3. **Auto Remediation (closed-loop)** — beyond `ExecutionPackage`, the system never actually applies the change
4. **Workflow Engine** — runtime-configurable state machines; current state machines are hard-coded per module
5. **Plugin / Extension System** — strategy, readiness check, intelligence provider all have registry patterns, but there is no formal extension API or sandboxed loading
6. **Distributed Tasks / External Message Queue (NATS/Kafka)** — the "queue" today is Celery + Redis; no Kafka layer, no multi-consumer fan-out
7. **Outbound Plugin SDK** (webhooks have one shape; not extensible)
8. **Policy Engine** (declarative OPA-like layer; today rules are Python)
9. **Secrets Rotation** (only encrypt-on-store; no rotate, no Vault binding)
10. **SSO / SAML / OIDC** — only password + 2FA
11. **SCIM** for orgs
12. **OPA** for fine-grained authz on decisions
13. **OpenTelemetry Collector deployment** (the SDK is initialized, but no collector)
14. **License / Plan Management + Dunning**
15. **Feature Flags** (runbook mentions patching via configmap, no actual flag framework in code)
16. **Investigation `session/` empty dir, `optimizer.py` stub, `correlation/` has only an engine file (no real correlation store)**
17. **Real Copilot LLM provider** (no model plug-point in code)
18. **Auto-remediation loop** with rollback and continuous validation
19. **Attack Graph** — knowledge graph exists but is not algorithmic attack-path material
20. **Risk Correlation / Posture trend predictions** as first-class endpoints (intel layer is too thin)
21. **Executive Reporting / Quarterly Reports** (data is there, narrative template is not)
22. **Compliance Framework Plugins** (SOC2/ISO/PCI/GDPR/ISO27001 stubs only)
23. **DR Drill** (docs exist, no automated drill script)

---

## 7. Foundation Quality

| Foundation Component | Verdict | Notes |
|---|---|---|
| **Async Database layer** | Solid | Async SQLAlchemy 2.0 with dedicated sessionmaker; `AsyncSessionLocal` and `CelerySessionLocal` split; `Base` proper declarative; migrations are sole source of truth in prod. |
| **Transaction Manager** | Solid | `app/modules/security/_shared/transaction_manager.py` codifies commit/rollback + post-commit side-effects; reused by Strategy/Approval/Execution. |
| **Base abstractions** | Solid | `BaseCache`, `BaseLifecycleManager`, `BaseAuditService`, `BaseStatisticsService`, `BasePipeline`, `ThreadSafeRegistry` are new but tested. |
| **Exception layer** | Solid | `app/core/exceptions.py` is typed (`UniOpsException`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `DecisionInvariantError`); global handler strips sensitive details in prod. |
| **Config / Settings** | Solid | Pydantic Settings; production-mode validators on `SECRET_KEY`, `DEBUG`, `CORS_ORIGINS`. |
| **Cache / Redis** | Mostly Solid | Real Redis client + memory fallback; some legacy `cache.py` over `cache_set`; `intelligence_cache.py` is placeholder. |
| **Metrics** | Solid | Dedicated Prometheus registry with bounded-cardinality helpers; pipeline duration histograms; tolerant emit. |
| **Logging** | Solid | structlog w/ loguru fallback; context vars (trace_id, correlation_id, tenant_id, user_id, request_id). |
| **Tracing** | Solid (prod) / Partial (dev) | OTel SDK init; no collector in cluster yet; tolerant degradation. |
| **Sentry** | Solid (best-effort) | Errors captured; on-by-default with `SENTRY_DSN`. |
| **Rate Limit** | Solid | Burst + sustained + per-tenant; fail-open. |
| **Auth / Multi-tenant** | Solid | tenant_id on every model; `tenant.py` middleware; isolation migration `008`. |
| **Migrations / Alembic** | Solid | 16 revisions covering initial → security → strategy → approval → execution → copilot → schema-alignment |
| **Event Bus** | Lightweight but Solid | In-process pub/sub + WS bridge; not distributed. |
| **Scheduler / Queue** | Solid | Celery + APScheduler fallback; queues `default` and `scans`. |
| **Audit Log** | Solid | Middleware-level + entity-level services. |
| **Shared Security Semantics** | Solid | Transaction Manager + BasePipeline + BaseLifecycle + read-only API prefix |
| **Frontend Hook Layer** | Mostly Solid | `useApi` with envelope-stripping, error-toast, retry, debounce |

**Verdict on foundations:** **Sufficient for the next 12-18 months of development**, with two corrections:

- The foundation has *zero formal extension points* — every registry is module-private. Before opening the platform to plugins/SDKs, the `app/platform/thread_safe_registry.py` should graduate to `app/core/` and a public protocol surface.
- The Foundations are *production-hardened* but *not security-hardened* under adversarial conditions: no JWT key rotation, no audit-table append-only guarantee, no per-tenant encryption key isolation, no Vault binding.

---

## 8. Technical Debt — Documented Findings

| ID | Category | Finding | Severity | Note |
|---|---|---|---|---|
| TD-01 | **Mixed Model Styles** | `app/models/*.py` mixes `mapped_column`/`Mapped` (SQLAlchemy 2.0 style) with legacy `Column(String, ForeignKey)` (Declarative 1.x style). Half of legacy files lack `tenant_id` indexes even after migration 014. | **High** | Normalize to 2.0 style across the board. Add `tenant_id` index to every tenant-bound table in one migration. |
| TD-02 | **Duplicate Stubs** | `services/intelligence/providers/impls/{capec,cisa,cwe,epss,ghsa,owasp,vendor}.py` and `{nvd,osv}` are all placeholders/architecture stubs. | **High** | Eight out of ten intel providers return `None`. |
| TD-03 | **Empty Slot** | `services/investigation/session/__init__.py` dir is created but empty; real code lives in `services/investigation/session.py`. | **Low** | Remove the empty folder. |
| TD-04 | **Optimizer Stub** | `services/investigation/query/optimizer.py` is 12 lines and effectively a no-op. | **Low** | Either implement or remove. |
| TD-05 | **Circular Risk** | `services/investigation/correlation/engine.py` and `services/impact/resolvers/ownership_resolver.py` import from each other implicitly via models. | **Medium** | Verify with `pydeps`. |
| TD-06 | **Layer Leak** | `app/modules/security/decision_*/**/models` reach into `app/models/**` for shared cross-module types; OK in some cases, but `cache.py` model imported by both security domain and `app/core/cache.py` is fragile. | **Medium** | Adopt a single model home for shared entities. |
| TD-07 | **Service Layer Bloat** | `services/scan_engine.py` is 49KB — one of the largest files. Split by provider. | **Medium** | Refactor to `services/scan_engine/{providers,score,risk}.py`. |
| TD-08 | **Service Layer Bloat** | `services/k8s_security_service.py` is 47KB; same recommendation. | **Medium** | |
| TD-09 | **Service Layer Bloat** | `services/asset_discovery_service.py` is 38KB. | **Medium** | |
| TD-10 | **Distribution Coupling** | `service.py` for Intelligence hard-codes NVD + OSV; not via registry. Register them like the others. | **Medium** | |
| TD-11 | **Magic / Hard-coded Values** | Policy thresholds and weights in `models/policy_evaluator.py` / `risk/components/*`; not exposed to config | **Low** | Pull to `app/config.py` |
| TD-12 | **Logging Anti-pattern** | Many modules call `logger.exception` even on expected outcomes; obscures real failures | **Low** | Audit and downgrade to `info` |
| TD-13 | **No Dead-Letter / Retry** | Celery tasks have no `autoretry_for`/`retry_backoff`. Failed scans permanently die | **High** | Add retries w/ exponential backoff for IO-bound tasks |
| TD-14 | **Doppelganger Models** | `DecisionBase` vs `BaseModel` (in `app/models/base.py`) co-exist | **Low** | Pick one |
| TD-15 | **Frontend Tab Bloat** | `pages/DevOpsCenter/components.tsx` is 49KB — single file holding ~200 components | **Medium** | Split into per-feature files |
| TD-16 | **No FE Test Suite** | Only tests/services tested | **High** | Add Vitest + Playwright |
| TD-17 | **Dev/Prod Divergence** | `app.config_dev.py` exists beside `config.py`; the dev override path risks prod bleed | **Low** | Funnel both through env-detection |
| TD-18 | **Migrations Bloat** | Migrations 004, 014 (`add_all_missing_tables.py`, `sprint2_schema_alignment.py`) are catch-alls | **Low** | Split future ones per-feature |
| TD-19 | **Type Drift** | `services/investigation/**/*.py` use plain dicts; no Pydantic schemas in `services/investigation` | **Medium** | Add at least `service.py` typed I/O |
| TD-20 | **No Custom Exception for Intel** | `services/intelligence/exceptions.py` is 1KB; reuse `core.exceptions.UniOpsException` | **Low** | |
| TD-21 | **Hard-coded Versioning** | `intelligence/providers/loader.py` constructs hardcoded providers; nothing dynamically discovers them | **High** | ProviderEntry should be loaded via entry-points or config |
| TD-22 | **Missing API Gateway** | No rate-limit on inbound webhooks; a misbehaving GitHub install could DoS | **High** | Add webhook-specific limiter / signature-failover |
| TD-23 | **No DB Query Budget** | Investigations `query/executor.py` doesn't bound recursion or query size | **High** | Cap query size, results, timeouts |
| TD-24 | **No Migration from Mono to Multi-arch** | Single Docker image; no ARM build | **Low** | Add multi-arch pipeline (Out of scope for now) |
| TD-25 | **Deprecated / Inconsistent Tenant Routing** | `app/middleware/tenant.py` is 1.5KB; tenant id comes from JWT but is also passed as route param on WS | **Low** | Clean up |
| TD-26 | **Under-engineered Audit Retention** | `audit_service.py` & `audit_log.py` model — no automated prune/retention | **Medium** | Add `cleanup_old_data.py` runner for audit |
| TD-27 | **Auto-Remediation Missing** | The Decision pipeline terminates in `ExecutionPackage`. The actual remedy (patch/PR/apply) never happens | **Critical** | This is not just debt — it's product-completeness gap. Track separately. |
| TD-28 | **Frontend "smoke" Pages** | `src/pages/status/*.tsx` exist as standalone 500/404/503 placeholders; not bad, but they are stubs the user-facing graph doesn't route to | **Low** | Drop until needed |
| TD-29 | **No SLO Bake-in** | RUNBOOK lists SLOs but `/metrics` doesn't expose them with the names referenced | **Low** | Add SLO summary metric |
| TD-30 | **No CVE Feed Ingest** | Threat model still doesn't pull NVD/OSV continuously; needs scheduling + idempotency | **High** | Add a real ingestion Celery task |

---

## 9. Enterprise Readiness (gap analysis)

| Capability | Status | Comment |
|---|---|---|
| Workflow Engine | ❌ Missing | Hard-coded pipelines; no DSL |
| Plugin System | ⚠️ Internal-only registries | No public surface |
| Event Bus — distributed | ❌ Missing | Today in-process |
| Message Queue (NATS/Kafka) | ❌ Missing | Celery/Redis only |
| Webhooks — outbound | ✅ Present | Per-tenant |
| Webhooks — inbound | ✅ Present | GitHub/GitLab/Slack/Stripe |
| Policy Engine (declarative) | ⚠️ Mixed | Programmatic built-ins + 1 evaluator |
| Secrets Rotation | ❌ Missing | No rotation, no Vault binding |
| License Management | ⚠️ Stripe-only | No plan/dunning engine |
| Billing Integration | ✅ Present | Stripe webhook + service |
| Feature Flags | ⚠️ Runbook-only | No code path |
| Tenant Isolation | ✅ Strong | tenant_id everywhere |
| AI Governance | ❌ Missing | No Copilot prompt policy, rate, or audit |
| API Gateway | ❌ Missing | No throttling-by-route beyond limiter |
| Enterprise Search | ⚠️ Limited | Investigation `search/engine.py` exists |
| Asset Inventory | ✅ Present | Asset model + service |
| Investigation Timeline | ✅ Present | Timeline engine + endpoints |
| Executive Reporting | ⚠️ Partial | Data ready, narrative generator missing |
| Risk Correlation | ⚠️ Partial | Knowledge graph + repositories_risk |
| Attack Graph | ❌ Missing | Not implemented |
| Security Copilot | ⚠️ Partial | Conversation persistence, no real LLM |
| Auto Remediation | ❌ Missing | Stops at `ExecutionPackage` |
| Human Approval Chains | ⚠️ Designed | Module 0 / P5 builds chain; UI not wired |
| Disaster Recovery | ✅ Documented | docs/DISASTER_RECOVERY.md |
| Business Continuity | ⚠️ Documented | No automated drill |
| Data Retention | ❌ Missing | Default-only `cleanup_old_data` |
| Data Lifecycle | ⚠️ Partial | Soft-delete conventions absent |
| Compliance Framework | ⚠️ Partial | Numeric scoring only |
| SOAR Integration | ❌ Missing | No SOAR webhook target |
| SIEM Integration | ⚠️ Partial | Loki/Prom exist, no forward |
| Identity Providers (SAML) | ❌ Missing | |
| OIDC | ⚠️ Schema only | JWT validation is local |
| SCIM | ❌ Missing | |
| OPA | ❌ Missing | |
| OpenTelemetry | ✅ SDK | No collector deploy |
| Distributed Tracing | ✅ Span emission | Backend span stitching via W3C |
| Multi-region | ❌ Missing | Single-region design |
| Disaster Recovery Drill | ❌ Missing | |
| Data Loss Prevention | ❌ Missing | |
| License Enforcement in Calls | ⚠️ Stripe webhook only | No entitlement gate |
| Multi-Cloud Cost Mgmt | ⚠️ AWS-only | AWS Cost Explorer wired |

---

## 10. Updated Product Roadmap

> **Reconstructed based on the code, not the original plan.**

The original roadmap assumed a linear: Intel → Decision → Approval → Remediation → Patch → Validation → Git → Security Center flow. Today, the first five are mostly there; the last three are **completely missing**. Add to that the breadth the team actually shipped (Cost, ML, Copilot, Asset Graph, Investigation) and the roadmap requires substantial reshaping.

### EPIC 0 — Foundation Hardening & Hygiene (1 sprint, ~2-3 weeks)
**Modules**:
- M0.1 — Alembic parity sweep: every model must have `tenant_id` indexed; one final consolidation migration
- M0.2 — Migrate all `app/models/*.py` to SQLAlchemy 2.0 `mapped_column`/`Mapped`
- M0.3 — Split `services/scan_engine.py`, `services/k8s_security_service.py`, `services/asset_discovery_service.py`, and `frontend DevOpsCenter/components.tsx` into per-feature files
- M0.4 — Add Celery `autoretry_for` + `retry_backoff` to IO-bound tasks
- M0.5 — Webhook signer + per-webhook rate-limit
- M0.6 — Frontend Vitest + Playwright scaffold
- M0.7 — Hard-coded constants in policies/scoring → config
- M0.8 — Add code-generated API reference (`/docs` already exists; auto-publish)
- M0.9 — Audit log retention job

### EPIC 1 — Real Intelligence Providers (Sprint-style, 3-4 weeks)
**Modules**:
- M1.1 — Real NVD client (https://services.nvd.nist.gov/rest/json/cves/2.0) with rate-limit awareness
- M1.2 — Real OSV client (https://api.osv.dev/)
- M1.3 — GHSA client (GraphQL)
- M1.4 — EPSS client
- M1.5 — CISA KEV client
- M1.6 — CWE/CAPEC reference resolvers
- M1.7 — OWASP Top 10 reference resolver
- M1.8 — Per-tenant Intel Cache pruning schedule
- M1.9 — Federated intel pipeline (provider priority, weighted merge, conflict resolver hardening)
- M1.10 — Vendor advisory adapter (configurable per-tenant)

### EPIC 2 — Remediation Engine + Patch Generator (the missing E2E loop)
**Modules**:
- M2.1 — Patch generator (diff engine): generates a textual diff from a Decision + Strategy + Finding context
- M2.2 — Validation Engine: runs build/test/lint/lockfile-resolve against a patch in a sandbox
- M2.3 — Git Provider layer: pluggable (GitHub / GitLab / Bitbucket)
- M2.4 — PR/RM creator with auto-merge rules
- M2.5 — Rollback orchestrator
- M2.6 — Approval integration (consume Module 0 / P5 chain)
- M2.7 — Post-merge deployment hook (consume Module 0 / P6 / ArgoCD)
- M2.8 — Patch-result feedback into the Decision Stats Service

### EPIC 3 — Auto Remediation Loop (closed-loop security)
**Modules**:
- M3.1 — Hook from executed patch back to detection (close the loop)
- M3.2 — Auto-validate-then-merge rollout strategy
- M3.3 — Manual-override chain enforcement
- M3.4 — Canary + Shadow deployment for security patches
- M3.5 — Time-to-patch SLO capturing

### EPIC 4 — Workflow Engine (next-gen foundation)
**Modules**:
- M4.1 — Declarative state-machine DSL (YAML/JSON)
- M4.2 — Step executor (python, shell, http, k8s)
- M4.3 — Saga + compensation pattern
- M4.4 — Approve/Timeout/Retry policies
- M4.5 — Reuse engine in the existing 4 pipelines (Decision / Strategy / Approval / Execution)

### EPIC 5 — Plugin / Extension SDK
**Modules**:
- M5.1 — Entry-point discovery (`uniops.intel.provider`, `uniops.decision.strategy`, `uniops.scan.engine`, `uniops.readiness.check`, `uniops.policy.rule`)
- M5.2 — Sandboxed executor (WASM/Docker sidecar)
- M5.3 — Per-tenant plugin enable/disable + quota
- M5.4 — Plugin marketplace (internal)

### EPIC 6 — Policy-as-Code & OPA Integration
**Modules**:
- M6.1 — Convert built-in policies to Rego
- M6.2 — Bundle shipping + signing
- M6.3 — Per-tenant policy compile + hot-reload
- M6.4 — Policy violation forensics

### EPIC 7 — Distributed Runtime (Enterprise-grade)
**Modules**:
- M7.1 — Replace in-process EventBus with NATS / Kafka
- M7.2 — Multi-tenant queues
- M7.3 — Backpressure + dead-letter
- M7.4 — Cross-region replication
- M7.5 — Saga pattern for cross-service workflows

### EPIC 8 — Identity & Access (SSO/SCIM/OIDC)
**Modules**:
- M8.1 — SAML SSO
- M8.2 — OIDC SSO (Auth0/Okta/Keycloak/Cognito adapters)
- M8.3 — SCIM 2.0 user/group provisioning
- M8.4 — Just-in-Time provisioning
- M8.5 — Domain claim / verified domain
- M8.6 — OPA-based ABAC for decisions

### EPIC 9 — Cost Intelligence + FinOps+
**Modules**:
- M9.1 — GCP + Azure cost ingest
- M9.2 — Recommendation engine v2 with ROI projection
- M9.3 — Reserved-instance planning
- M9.4 — Show-back / Charge-back engine
- M9.5 — Forecast drift detection

### EPIC 10 — Investigation & Threat Intelligence Surface
**Modules**:
- M10.1 — Investigation session is wired into WebSockets
- M10.2 — Investigation `optimizer.py` real cost-based optimizer
- M10.3 — True correlation engine (not single-file stub)
- M10.4 — In-app notes + timeline sharing
- M10.5 — Hunting queries

### EPIC 11 — Observability, Reliability, Audit++
**Modules**:
- M11.1 — OpenTelemetry Collector deployment
- M11.2 — Tail-based sampling
- M11.3 — Datadog/Chronosphere/Grafana Cloud exporters
- M11.4 — PII redaction in logs (auto)
- M11.5 — Audit log streaming to SIEM/Cloud Object Storage
- M11.6 — DB connection pool telemetry per tenant
- M11.7 — Feature-flag rollout (Unleash-style)

### EPIC 12 — Licensing, Billing, Plans
**Modules**:
- M12.1 — Plan/entitlement engine
- M12.2 — Usage-based metering
- M12.3 — Dunning + grace period
- M12.4 — Self-serve plan upgrade/downgrade
- M12.5 — Quota enforcement at API edge

### EPIC 13 — AI Governance & Copilot 2.0
**Modules**:
- M13.1 — Provider plug-point (Claude, OpenAI, Bedrock, Vertex, Mistral, locally-hosted)
- M13.2 — System-prompt versioning + audit
- M13.3 — Token-budget per tenant
- M13.4 — Model card display
- M13.5 — A/B and guardrails
- M13.6 — Retrieval grounding against the Knowledge Graph + Investigation store

### EPIC 14 — Compliance + Reporting 2.0
**Modules**:
- M14.1 — Native SOC2 / ISO27001 / PCI / HIPAA evidence library
- M14.2 — Mapping controls → evidence collectors (auto)
- M14.3 — Custom frameworks (per-tenant)
- M14.4 — Quarterly executive narrative generator (LLM-bound but governed)
- M14.5 — Audit-ready export (signed PDFs + JSON)

### EPIC 15 — Hardening / Multi-region
**Modules**:
- M15.1 — Multi-region Postgres (read replicas)
- M15.2 — Redis Sentinel / Cluster
- M15.3 — GeoDNS
- M15.4 — Cross-region failover runbook automation
- M15.5 — DR drill script + game-day

---

## 11. Recommended Module Order (immediate next phase)

The next phase should not restart work. It should:

1. **Stabilize what works**: Foundation Hardening (Epic 0).
2. **Make the existing Decision chain safe to *not* execute**: Audit + runbook hardening on the EPIC 10 chain.
3. **Land real Intel providers**: Without them, decisions are starved of input.
4. **Build Remediation Engine + Patch Generator (Epic 2)**: this is the missing right-hand-side of the platform.
5. **Auto Remediation Loop (Epic 3)**: closes the loop.
6. **Parallel tracks (in same program)**: Epic 4 (Workflow) + Epic 8 (Identity).

**Priority order — must-ship first**:

```
EPIC 0  Foundation Hardening
EPIC 1  Real Intelligence Providers
EPIC 2  Remediation Engine + Patch Generator + Validation
EPIC 3  Auto Remediation Loop
EPIC 4  Workflow Engine
EPIC 8  Identity & Access (SSO/SCIM/OIDC)
EPIC 11 Observability Hardening
EPIC 5  Plugin SDK
EPIC 6  Policy-as-Code
EPIC 7  Distributed Runtime
EPIC 13 AI Governance
EPIC 9  Cost Intelligence
EPIC 10 Investigation Surface
EPIC 12 Licensing
EPIC 14 Compliance 2.0
EPIC 15 Multi-region
```

---

## 12. Current Development Phase

**UniOps is at the boundary of Beta → Production for the data plane, and at Alpha for the remediation plane.**

What is uniquely strong:
- Production-grade infrastructure (manifests, runbook, RPO/RTO, DR doc).
- Mature Module 0 / Decision chain (read-only, fully tested pipeline).
- A wide, fairly coherent vertical slice per subsystem.

What is uniquely weak:
- The original roadmap's "loop" — Intel → Decision → Strategy → Approval → Execution → **Patch → Validation → Git → Security Center** — has no Patch, no Validation, no Git side effects. So the platform currently *thinks deeply* about remediation but never *applies* one.
- The Security Intelligence subsystem is architecturally complete (registry, normalization, merge, conflict-resolver, provenance) but only NVD + OSV stubs are wired.
- Frontend is wide but under-tested.

---

## 13. What Should Be Built Next (Top 5 Imperatives)

1. **Patch Generator + Validation Engine + Git Provider** (the last three legs of the decision chain). This single deliverable converts the platform from "analyzer + advisor" to "autonomous security remediator."
2. **Real Intelligence Providers** (NVD, OSV, GHSA, EPSS, CISA KEV). Without fresh intel the engine can't even decide.
3. **Foundation Hardening** (Alembic parity, model style, task retries, webhook limiter, FE tests). Pays for itself within one quarter.
4. **Identity layer (SSO/OIDC/SCIM)**. Required before enterprise sales.
5. **Workflow Engine + Plugin SDK**. Required before the platform scales beyond one team.

---

## 14. Long-Term Vision

A "world-class Enterprise DevSecOps & Security Automation Platform" should land in five distinguishable planes:

1. **Observe** — already strong (assets, scans, findings, posture, intel).
2. **Decide** — strong (rules, policies, strategies, approvals).
3. **Act** — currently the missing plane (remediation, patch, deploy, rollback).
4. **Govern** — weak (SSO, SCIM, OPA, audit retention, compliance frameworks, AI governance).
5. **Extend** — missing (plugin SDK, marketplace, declarative policy/code, multi-tenant extensibility).

The first three reach from "reactive" to "autonomous"; the last two reach from "platform" to "ecosystem."

In the long term, UniOps should provide:

- Closed-loop detection-to-deployment security remediation, with verifiable validation and audit-grade rollback.
- A federated intelligence plane (proprietary + NVD/OSV + vendor advisories) with deterministic provenance.
- A policy-as-code authoring surface, with OPA bundles distributed to tenants.
- A first-class workflow engine where the customer can model their own "approved + auto-merged if low risk, manual if high risk" pipelines.
- A plug-in surface where third parties (security vendors) ship first-class scanners and readouts.
- A multi-region, multi-cloud control plane for global enterprises.
- An AI Governance plane where every Copilot call is auditable, policy-bound, and cost-bounded.

---

## 15. Scorecards

### 15.1 Architecture Quality (/100)

| Dimension | Score | Notes |
|---|---|---|
| Layer separation | 75 | Service→Model→API are clean, but some monolith service files and the FE component file hinder readability |
| Async correctness | 80 | Solid async pattern; scheduler still uses blocking calls in places |
| Multi-tenant discipline | 85 | Tenant ID everywhere; small leak risk on joint tables |
| Cache strategy | 65 | Cache module thin, intelligence cache placeholder |
| AuthN/AuthZ | 75 | JWT + 2FA + RBAC constants; SSO missing |
| Observability | 85 | Traces, metrics, logs; no collector deploy |
| Test coverage (security domain) | 80 | Module 0 has unit + integration tests; legacy modules thin |
| Frontend quality | 65 | Wide feature surface; no tests; some bloat |
| Documentation | 90 | Runbook, RPO, DR, READMEs everywhere |
| Kubernetes readiness | 90 | Manifests + overlays + probes + prometheus-rules |
| Schema discipline | 70 | Half files 1.x style |
| API Gateway / Webhook safety | 55 | No API Gateway, no webhook-rate-limit |
| **Weighted total** | **76** | |
| Adjusted for product gap (Action plane missing) | **64** | |
| **Overall Architecture Score** | **64 / 100** | |

### 15.2 Product Maturity Level (per axis)

| Axis | Level |
|---|---|
| Observe | **Production** |
| Decide | **Beta** (read-only chain) |
| Act (Autonomous Remediation) | **Alpha → Prototype** (ExecutionPackage only) |
| Govern (SSO/SCIM/Compliance) | **Beta** |
| Extend (Plugins) | **Prototype** |
| **Aggregate maturity** | **Beta**, trending to **Production** |

### 15.3 Operational Readiness Score
- Health probes 95
- Migrations 90
- Backups documented 90
- Runbook 90
- DR doc 90
- Metric coverage 80
- DLQ/Retry 50
- Alerting routing 60
- Webhook safety 55
- **Average: 78**

---

## 16. Final Recommendation

### 16.1 Where is UniOps today?

UniOps today is a **wide, well-architected, foundationally-sound Enterprise DevSecOps platform** whose **Observe and Decide planes are production-grade**, but whose **Act (remediation) plane is the missing final leg**, and whose **Govern plane is partial**. The codebase shows the work of many thoughtful sprints (Module 0 chain, observability stack, production docs) and a culture of discipline (typed exceptions, transactions, idempotency, audit). What it lacks is *closure* — closing the loop from finding to applied patch, with validation and rollback — and *governance breadth* — SSO, OPA, AI governance, distributed eventing.

### 16.2 What has truly been completed?

- A **production-grade FastAPI + Celery + K8s + observability** substrate.
- A **decision chain** (Decision → Strategy → Approval → Execution Orchestration) that is end-to-end internally consistent, fully tested, and tenant-aware.
- A **10+ subsystem wide product surface** (Auth, Integrations, Assets, Scans, Findings, Policies, Exceptions, Reports, Risk, Graph, Investigation, Copilot, ML, Cost).
- A **mature Kubernetes/Helm-less production layout** with probes, HPA, NetworkPolicies, prometheus-rules.
- A **production-grade documentation suite** (RUNBOOK, RPO, DR, README, in-module READMEs).
- A **disciplined shared platform** (TransactionManager, BaseCache, BaseLifecycle, BasePipeline, ThreadSafeRegistry) introduced in R35.

### 16.3 What remains to achieve the vision of a world-class Enterprise DevSecOps & Security Automation Platform?

1. **Close the loop**: Patch Generator + Validation Engine + Git Provider + Rollback.
2. **Real-time Intelligence**: Real provider adapters (NVD, OSV, GHSA, EPSS, CISA KEV, vendor advisories).
3. **Auto-Remediation at Scale**: rollout strategies (canary/shadow), time-to-patch SLO, automatic re-validation.
4. **Workflow Engine**: declarative state machines; reuse the current chains as test cases.
5. **Identity Plane**: SSO (SAML + OIDC), SCIM, OPA.
6. **Distributed Runtime**: NATS/Kafka bus, multi-tenant queues, saga patterns.
7. **AI Governance**: provider plug-in, prompt versioning, quota, audit.
8. **Compliance & Reporting 2.0**: native framework evidence library, executive narrative.
9. **Frontend Hardening**: tests, storybook, type tightening.
10. **Operational Reliability**: DLQ + retries, webhook safety, SLO-baked metrics.

### 16.4 What should be the immediate next implementation phase, and why?

**Phase 1 (Sprint 4 / Sprint 5): Foundation Hardening + Real Intelligence Providers + Patch/Validation/Git trio.**

Reasoning:
- It does **not** re-do finished work.
- It **completes the value proposition**: today the platform reads, evaluates, decides — but does not write. Adding Patch/Validation/Git turns it into an *autonomous* remediation platform, which is the only defense against the ever-widening AI-assisted attack surface.
- It **unblocks revenue**: enterprise security buyers pay for *closed-loop* remediation, not for dashboards.
- It **scales linearly**: each Patch Provider (GitHub Actions, GitLab CI, custom) is a narrow adapter that the engine can ship behind an interface.
- It **binds the foundations to the roadmap**: foundation hardening is paid back by reliability and throughput as the platform grows.

The conclusion: **Ship the Action plane (Patch + Validation + Git) on top of a foundation-hardening patch, fed by real intelligence, with Frontend tests running in CI — in that order — and UniOps graduates from Beta to Enterprise.**
