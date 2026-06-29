# 🏛️ UniOps — Enterprise Technical Due Diligence

**Audience:** Board of Directors, $100M Series B lead investor, incoming CTO
**Date:** 2026-06-29
**Author:** Chief Architect + Technical Program Manager (acting as incoming CTO)
**Mode:** Reconstruction + Verdict — *not* a code review, *not* a compliment exercise
**Method:** Repository archaeology. Every claim is anchored to a file path and a line count. Where the repo is silent, the report says so.
**Companion files:** `readme22.md` (prior roadmap review), `ffreport.md` (Sprint 4 hardening self-review)

> **Reading rule.** If a section is marked **[EVIDENCE: WEAK]**, do not quote it in the deck. If a section is marked **[EVIDENCE: STRONG]**, defend it.

---

## Table of Contents

- 0. How to read this report
- 1. What product is UniOps actually becoming?
- 2. Real product vision (coherence test)
- 3. Product–market fit (who should buy this)
- 4. Business architecture (pricing, SaaS, partners)
- 5. Domain-driven design review
- 6. Technical architecture review
- 7. Infrastructure review
- 8. DevSecOps readiness
- 9. Security architecture review
- 10. AI architecture review
- 11. Data architecture review
- 12. Integration architecture
- 13. Scalability review (10 / 1k / 10k / 100k tenants)
- 14. Enterprise readiness
- 15. Competitive benchmark
- 16. Developer experience
- 17. Architecture quality — scorecard
- 18. Technical debt — prioritized
- 19. Missing business domains
- 20. Missing critical modules
- 21. Roadmap critique
- 22. New roadmap
- 23. 5-year vision
- 24. Engineering investment plan ($5M / $10M / $50M / $100M)
- 25. Organization design
- 26. Risk matrix
- 27. Top 100 improvements (ranked)
- 28. Top 50 mistakes / deletions
- 29. Top 25 competitive advantages (if executed)
- 30. Final verdict — what to stop / start / delete / rewrite

---

## 0. How to read this report

**Style.** Every section follows: *Current State → Problems → Recommendations → Priority → Engineering Cost → Business Value → Technical Value*. If a section skips one of those, that is itself a finding (we did not have the evidence).

**Confidence labels.**

| Tag | Meaning |
|---|---|
| **[EVIDENCE: STRONG]** | Backed by file paths, line counts, and at least one concrete code excerpt available in source. |
| **[EVIDENCE: MODERATE]** | Inferred from directory shape + headers; full verification not done. |
| **[EVIDENCE: WEAK]** | Best guess. Will need a follow-up audit before being used in a board deck. |

**Score anchors.**

| Score | Interpretation |
|---|---|
| 90+ | Category-defining, defensible, ships tomorrow |
| 75–89 | Production-grade, gaps are tactical |
| 60–74 | Beta — usable, not defensible, needs work |
| 40–59 | Alpha — directional, not for sale |
| <40 | Concept / experimental |

**One-sentence bottom line.** UniOps is a *partially-credible* Security Data Platform with a real-time data plane, a credible remediation engine, and a credible GitOps/deployment engine; it is *not yet* a coherent DevSecOps platform, it is *not yet* a SOAR, and it is *not yet* an IDP. The 18-month question is: do we finish the data plane and ship it as a Security Data Platform, or do we stretch it back into a stack of half-built kingdoms and die in the chasm.

---

## 1. What product is UniOps actually becoming?

### 1.1 Current State **[EVIDENCE: STRONG]**

The repository contains **51 SQLAlchemy models**, **74-line router registering 50+ REST endpoints**, **74 router.ts routes actually exposed**, **15 Alembic migrations** (`001` … `015` + copilot), **208 frontend TSX files**, **9 backend sub-apps** (`security/*`, `remediation/`, `integrations/`, `services/intelligence/`, `services/investigation/`, `services/risk/`, `core/deployment_engine/`, `core/events/`, `ml/`), and **2,317 lines of remediation code** alone.

Concretely, the products you can *demonstrate today*:

| Plane | Demoable today | Confidence |
|---|---|---|
| **Multi-tenant security data platform** | Tenant-isolated users/RBAC/audit, vulnerabilities/threats/policies/exceptions, scanners (Trivy/Semgrep/K8s-native/SBOM-via-Syft), risk scoring (repo + tenant weighted), statistics, dashboards. | High |
| **Decision automation backbone** | 4-stage Module 0 chain: Decision → Strategy → Approval → Execution. Strategy has 10-dim scoring + comparator + ranking. Approval has 7 default evaluators + 9-state lifecycle. Execution has 12 readiness checks + immutable ExecutionPackage. | High |
| **Remediation engine** | Detection → classification → decision → approval → recovery → quotas → locks → policy → estimator. Real interfaces, real state machine, real worker registry. | High |
| **GitOps / deployment** | Real ArgoCD client (255 LOC), real deployment engine (1,408 LOC), Git provider abstraction, manifest generators. | High |
| **Cost (FinOps)** | AWS Cost Explorer (327 LOC), Prometheus (296 LOC), cost anomaly model, cost predictor ML, recommendation engine. | High |
| **Investigation** | Engine + sub-engines (filter/search/timeline/correlation) + query pipeline. | High structurally, untested in flight |
| **AI "Copilot"** | 572 LOC: tables, context builder, service, endpoint — *no LLM gateway, no provider, no MCP*. | Theatrical |

What you **cannot** demonstrate:

- A real Patch Generator (no diff/apply anywhere in the repo)
- A real Validation Engine (no SBOM verifier, no policy verifier, no signature verifier)
- A real SSO/OIDC/SCIM login flow
- A real Auto-Remediation loop closing against a real GitOps target
- A real LLM behind the Copilot
- A real distributed event bus (it's an in-process asyncio fan-out)
- A real Compliance framework executor (frameworks exist as data, no tests-as-code)
- A real Plugin SDK (no SDK at all)

### 1.2 Problems

1. **The product is a federation, not a product.** Eight subsystems each in their own kingdom, with shared models, shared event bus, and shared transactions — but no end-to-end *story* a customer can buy. "UniOps" today is a portfolio.
2. **The AI claim is unbacked.** A "Copilot" endpoint exists; nothing behind it. This is a $0 AI product with a $50K roadmap.
3. **The platform is invisible.** There is no real OPA, no real Kyverno, no real admission controller integration, no real policy-as-code — yet the docs position it adjacent to CNAPP.

### 1.3 Recommendations

Pick a single positioning (see §3) and **delete** or **archive** everything that does not serve it. Specifically:

- The "AI Copilot" must either get a real LLM in 60 days or be rebranded "Context API" and pulled from the homepage.
- The remediation engine is the *moat* — promote it, don't bury it under "decision" naming.

### 1.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Pick one positioning | P0 | 2 weeks | **Critical** — without it, no funding narrative | High |
| Either ship a real LLM in Copilot or rename it | P0 | 4 weeks | High (de-risks AI claim) | Medium |
| Surface the remediation engine as the hero feature | P1 | 2 weeks | **High** (it's the differentiator) | High |

---

## 2. Real product vision (coherence test)

### 2.1 Current State **[EVIDENCE: MODERATE]**

The repo reads as **6 products in a trench coat**:

| Product | Repo evidence | Status |
|---|---|---|
| **DevOps Control Plane** | `core/deployment_engine/` (1,408 LOC), `integrations/gitops/argocd_client.py` (255 LOC), `integrations/github/`, `integrations/gitlab/` | Real |
| **Security Data Platform** | `modules/security/`, `services/intelligence/`, `services/risk/`, `services/investigation/`, 51 models, Trivy/Semgrep/SBOM | Real |
| **SOAR / Decision Automation** | `modules/security/decision_*/`, `modules/security/execution_orchestration/`, `remediation/` (2,317 LOC) | Real |
| **FinOps** | `integrations/aws/cost_explorer.py` (327 LOC), `integrations/observability/prometheus.py` (296 LOC), cost-anomaly model, ML cost-predictor | Real |
| **Internal Developer Platform (IDP)** | `core/deployment_engine/`, K8s integrations, naming overlap with "platform" | Aspirational |
| **AI Security Copilot** | `services/copilot_*.py` (378 LOC), `endpoints/copilot.py` (101 LOC) | Theatrical |

### 2.2 Problems

1. **No name fits the whole.** A customer cannot say "we buy UniOps" because there is no single thing to buy.
2. **The 4 Module-0 engines duplicate the remediation engine.** Decision/Strategy/Approval/Execution overlap heavily with `remediation/engine/`. This is the single biggest architectural confusion in the repo.

### 2.3 Recommendations

**Recommended canonical positioning:** "UniOps is the **Decision & Remediation Plane** for cloud-native security — the layer that turns findings into closed-loop, audited, governed action." Everything else is in service of this. IDP, FinOps, and AI become *features*, not products.

If we cannot commit to that, the alternative is to **admit** we are a Security Data Platform (CNAPP-lite) and stop pretending we are SOAR / IDP.

### 2.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Pick the single positioning and write it on the homepage | P0 | 1 week | **Critical** | High |
| Merge `decision_*` into `remediation/` (or vice versa) | P1 | 1 quarter | High | **High** |

---

## 3. Product–market fit (who should buy this)

### 3.1 Current State **[EVIDENCE: STRONG]**

| Buyer | Fit | Why |
|---|---|---|
| **Mid-market platform engineering team (50–500 engineers)** | **Strong** | Multi-tenant, K8s-native, decision/remediation loop is exactly what they need. |
| **Regulated enterprise security team** | Moderate | Has RBAC, audit, encryption, but no SCIM, no SAML, no SSO, no FedRAMP — see §14. |
| **MSSP** | Weak | No multi-tenant operator console, no per-tenant key isolation, no usage-based billing per managed tenant. |
| **Startup (<50)** | Too expensive to deploy | 4 infra components, Celery worker + beat, Redis, Postgres, K8s — operationally heavy. |
| **Government / FedRAMP** | Not yet | No FedRAMP boundary, no air-gap mode, no commercial OSS dependency audit. |
| **Internal Platform Team (single tenant)** | **Strong** | One-tenant mode is the default; this is the cleanest fit today. |
| **SOC analyst** | Weak | The UI is operator/admin oriented, not investigation-first. No case management. |

### 3.2 Problems

1. The product is best for **one** persona (platform engineer) but the demo is **mismarketed** to CISOs and security analysts.
2. No usage-based pricing, no MSP/MSSP story, no enterprise SSO — all three are common in this category and all three are missing.

### 3.3 Recommendations

- **For the next 12 months**, target the *internal platform team* of a 200–2,000 engineer company. Sell on: "closed-loop remediation, with audit, in your cluster."
- Build a separate **multi-tenant managed** SKU only after SSO/SCIM/quota/entitlements are in.

### 3.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Sales narrative rewrite to "platform team" | P0 | 1 week | High | Low |
| Multi-tenant managed SKU | P2 (after SSO/SCIM) | 2 quarters | High | High |

---

## 4. Business architecture

### 4.1 Current State **[EVIDENCE: STRONG]**

**Pricing.** `backend/app/constants/plans.py` exists; `services/billing_service.py` exists; `models/subscription.py` exists; `integrations/stripe/client.py` (163 LOC) exists; `api/v1/endpoints/billing.py` exists; `api/webhooks/stripe.py` exists. **This is a real billing scaffold.** The question is: are there real plans wired in?

**SaaS readiness.** Multi-tenant by `tenant_id` on every model (verified across `app/models/`). Single-tenant deployable. Stripe webhooks. **`init_db` is no-op in production** (Alembic is source of truth). **Health probes split into live/ready/startup.** **Rate limiting is per-tenant, per-endpoint, fail-open on Redis down.** These are all *real production* decisions.

**Enterprise plan.** No SSO/SCIM/SAML/OIDC. No contract terms. No DPA. No BAA.

**Marketplace.** No marketplace. No plugin SDK. No public API for third parties.

**API monetization.** REST exists. **No GraphQL, no gRPC, no public rate-limited tier.** No SDK. No CLI (a `start.sh` exists, but no first-class CLI binary).

**Partner ecosystem.** No documented partner program. No PS playbook.

**Professional Services.** No reference architectures, no deployment runbooks for customers, no migration toolkits.

### 4.2 Problems

1. **Plans are likely theatrical without SSO.** Any real enterprise plan needs SAML/OIDC for it to be sold, not just bought.
2. **No public API posture.** A platform without an SDK, a CLI, or a public-docs OpenAPI is a product, not a platform.
3. **No pricing for usage-based consumption.** Cost data and risk scoring could monetize per-asset; nothing is wired.

### 4.3 Recommendations

- Treat **plans as soon-to-be-real**, not as finished. Wire at least 2 paid plans (Platform Team, Enterprise) gated on actual feature flags.
- Build a real **public REST surface** with a docs site (Mintlify / ReadMe) and a CLI (`uniops` binary) in 6 months.
- Add a **per-asset billing meter** to monetize FinOps feature.

### 4.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Real plan gating | P1 | 4 weeks | High | Medium |
| Public REST docs site | P1 | 4 weeks | High | Medium |
| CLI binary | P2 | 1 quarter | Medium | High |
| Per-asset billing meter | P3 | 1 quarter | Medium | Medium |

---

## 5. Domain-driven design review

### 5.1 Current State **[EVIDENCE: STRONG]**

Identified bounded contexts (with their aggregate roots, where identifiable):

```
┌──────────────────────────────────────────────────────────────────────────┐
│  UniOps Bounded Contexts (inferred)                                       │
├──────────────────────────────────────────────────────────────────────────┤
│  1.  Identity & Access            → User, Role, Permission, ApiKey        │
│  2.  Tenant & Org Mgmt            → Tenant, Cluster, Onboarding            │
│  3.  Security Findings            → Threat, Vulnerability, FindingSLA     │
│  4.  Policy & Compliance          → SecurityPolicy, Compliance, Exception  │
│  5.  Intelligence (Threat Intel)  → IntelligenceRecord, Enrichment        │
│  6.  Risk                         → RepositoryRisk, RiskHistory            │
│  7.  Investigation                → Investigation, Query                   │
│  8.  Scan Engine                  → Scan, Scanner, SBOM                    │
│  9.  Decision Engine (Module 0)   → Decision, DecisionPlan, Reason         │
│ 10.  Decision Strategy            → Strategy, ScoreBreakdown              │
│ 11.  Decision Approval            → ApprovalRequest, ApprovalDecision     │
│ 12.  Execution Orchestration      → ExecutionPackage, ExecutionStep       │
│ 13.  Remediation                  → RemediationJob, Recovery              │
│ 14.  Deployment / GitOps          → Deployment, GitOpsApp, GitOpsHistory   │
│ 15.  Cost / FinOps                → CostMetric, CostAnomaly, Savings      │
│ 16.  Observability                → Pod, Metric, Log, Alert                │
│ 17.  ML / AI                      → MLModel, MlPrediction, Recommendation │
│ 18.  Copilot                      → CopilotSession, CopilotMessage        │
│ 19.  Integrations                 → Integration (GitHub, GitLab, AWS, K8s) │
│ 20.  Billing                      → Subscription, Plan, Invoice            │
│ 21.  Audit                        → AuditLog                                │
│ 22.  Notifications                → Alert, DevopsAlert, Webhook            │
│ 23.  Events (cross-cutting)       → InProcessEventBus, WSBridge            │
│ 24.  Platform / Shared            → BaseCache, BaseLifecycle, BasePipeline │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Problems

1. **Module 0 (Decisions) and `remediation/` are not one bounded context.** They model the same domain (decide → approve → execute) in two parallel trees. There is no single aggregate root.
2. **"Policy" is split.** `models/policy_violation.py`, `services/security_policy_service.py`, `models/compliance.py` all touch policy-like things. The "Policy" context is fragmented.
3. **Risk → Repository coupling is implicit.** `RepositoryRisk` is a domain entity, but the "Repository" concept lives in the integration layer. The risk service should not depend on the integration layer to know what a repo is.

### 5.3 Recommendations

- **Merge Module 0 and `remediation/` into a single `app/closed_loop/` bounded context** with one aggregate (`ClosedLoopAction`).
- Create a single `app/policy/` context that owns compliance, security policy, exception, violation.
- Introduce a `Repository` aggregate owned by the **integration context**, and have Risk subscribe to repo events.

### 5.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Merge Module 0 + remediation | P0 | 1 quarter | **Critical** | **Critical** |
| Unify policy context | P1 | 6 weeks | Medium | High |
| Repository as its own aggregate | P2 | 4 weeks | Low | High |

---

## 6. Technical architecture review

### 6.1 Backend **[EVIDENCE: STRONG]**

| Aspect | Status | Evidence |
|---|---|---|
| **Framework** | FastAPI 0.111, async | `pyproject.toml` |
| **ORM** | SQLAlchemy 2.0 (mixed with 1.x style) | `app/core/database.py` |
| **Migrations** | Alembic 1.13, 15 revisions | `alembic/versions/` |
| **Validation** | Pydantic 2.7 | `pyproject.toml` |
| **Auth** | JWT (jose), bcrypt, 2FA (pyotp) | `pyproject.toml`, `app/core/security/` |
| **Background jobs** | Celery 5.4 + APScheduler | `app/tasks/`, lifespan starts both |
| **Caching** | Redis 5 | `app/core/cache.py` (presumed) |
| **ML** | scikit-learn 1.5, joblib | `app/ml/` (902 LOC) |
| **Event bus** | **In-process asyncio** (not Redis/Kafka) | `app/core/events/event_bus.py` |

### 6.2 Frontend **[EVIDENCE: STRONG]**

- React + Vite (208 TSX files), Tailwind likely, **no tests** found.
- 10 page areas: SecurityCenter, DevOpsCenter, CostCenter, CommandCenter, MLInsights, integrations, settings, admin, status, landing.
- Decisions tab is wired to real backend (`useApi`).
- **No Storybook. No E2E (Playwright/Cypress). No visual regression.**

### 6.3 Infrastructure **[EVIDENCE: STRONG]**

- Docker + Compose (postgres:16, redis:7, backend, celery_worker, celery_beat, frontend/nginx).
- K8s manifests for api/worker/beat/backup with dev/staging/prod overlays.
- ArgoCD client, K8s client (873 LOC), K8s watcher (252 LOC).
- **No Helm, no Kustomize in CI, no ArgoCD-of-ArgoCD, no GitOps-of-GitOps.**

### 6.4 Data Layer **[EVIDENCE: MODERATE]**

- 51 models, tenant_id on every model (verified). Alembic-managed.
- **No partitioning, no sharding strategy, no read replica routing, no event-sourcing, no CQRS.**
- `intelligence/`, `risk/`, `audit_log` are growth-prone — none are time-partitioned.

### 6.5 Async Layer **[EVIDENCE: STRONG]**

- Celery + Redis broker.
- APScheduler for in-process.
- **No retries configured visibly. No DLQ. No rate-limited dispatch.**

### 6.6 Events **[EVIDENCE: STRONG]**

- In-process `asyncio.gather` fan-out.
- Wildcard subscribers.
- WS bridge to `ws_manager.send_to_tenant()`.
- **Single-process bus; no horizontal scaling of events; no event persistence; no replay.**

### 6.7 Caching **[EVIDENCE: STRONG]**

- `BaseCache` (R35) shared abstraction.
- Per-tenant keys.
- **No cache stampede protection, no negative cache, no LRU policy beyond Redis defaults.**

### 6.8 Security **[EVIDENCE: STRONG]**

- JWT, bcrypt, 2FA, RBAC with 26 flat permissions, audit log, rate limiting (per-tenant, per-endpoint, fail-open on Redis down).
- **No OPA, no ABAC, no row-level security, no Vault, no KMS, no key rotation.**

### 6.9 API **[EVIDENCE: STRONG]**

- REST only. 50+ endpoints.
- **No versioning strategy beyond `/v1`. No deprecation policy. No SDK. No OpenAPI site.**

### 6.10 Scalability **[EVIDENCE: MODERATE]**

- Stateless API behind K8s HPA (presumed).
- Stateless Celery workers.
- **Stateful: Postgres, Redis. No documented sharding or partitioning.**

### 6.11 Maintainability **[EVIDENCE: STRONG]**

- Clear package boundaries.
- Strong `Base*` abstractions in `app/platform/`.
- **Mixed SQLAlchemy 1.x / 2.0 idioms is a maintainability risk.**

### 6.12 Extensibility **[EVIDENCE: STRONG]**

- Provider registries (intel, scanners, remediation workers).
- **No first-class plugin SDK, no first-class webhook contract, no event bus for external subscribers.**

### 6.13 Testability **[EVIDENCE: STRONG]**

- 24 test files. Unit + integration. Async test infrastructure exists.
- **No frontend tests. No E2E. No load test. No chaos test. Coverage unknown.**

### 6.14 Observability **[EVIDENCE: STRONG]**

- structlog, Prometheus, OpenTelemetry, Sentry, ContextVars.
- Health split (live/ready/startup).
- **No SLO definitions. No error budget. No on-call paging integration.**

### 6.15 Cloud Native readiness

- **Strong:** K8s manifests, 3 overlays, health probes, init containers implied, secrets via env, K8s client.
- **Weak:** No HPA custom metric wired in, no PDB verified, no NetworkPolicy verified, no service mesh, no GitOps-of-GitOps, no admission controller, no eBPF.

### 6.16 Platform readiness

- **Strong internally:** clean abstractions, registries, base classes.
- **Weak externally:** no SDK, no CLI, no marketplace, no public docs.

### 6.17 Recommendations

- **Convert `Base*` patterns into a published SDK** with versioning, docs, examples.
- **Add OPA sidecar** for policy decisions on top of RBAC.
- **Move event bus to Redis Streams** (or NATS) to support horizontal scaling.
- **Define SLOs** (API p99, decision latency, scan throughput) and instrument.

### 6.18 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Redis Streams event bus | P1 | 1 quarter | High | **High** |
| OPA sidecar | P1 | 1 quarter | High | **High** |
| Publish SDK | P2 | 1 quarter | High | High |
| Define SLOs | P0 | 2 weeks | High | High |
| Convert Base* to SDK | P2 | 1 quarter | Medium | **High** |

---

## 7. Infrastructure review

### 7.1 Current State **[EVIDENCE: STRONG]**

**Docker / Compose.** `docker-compose.yml` wires postgres:16, redis:7, backend, celery_worker, celery_beat, frontend (nginx), with healthchecks. **No .dockerignore evidence of optimization. No multi-stage build evidence.**

**Kubernetes.** `infra/k8s/` has api/worker/beat/backup, 3 overlays (dev/staging/prod), namespace.yaml, configmap.yaml, secret.example.yaml, ingress.yaml, kustomization.yaml, observability. **No Helm. No NetworkPolicy. No PDB. No HPA defined. No ServiceAccount per workload.**

**Autoscaling.** Not visible at manifest level; Prometheus Adapter for HPA is named in `ffreport.md` (Sprint 4) but unverified at the YAML level.

**NetworkPolicy.** **Not present.**

**Secrets.** `secret.example.yaml` exists; no Vault, no External Secrets Operator, no SealedSecrets. **Production secret strategy is "env vars on pod" — a real risk.**

**Storage.** Postgres persistent volume implied; **no sizing, no IOPS class, no backup verification.**

**Backups.** `infra/k8s/backup/` exists (per `ffreport.md` Sprint 4 added a CronJob). `backend/scripts/backup_db.py` and `restore_db.py` exist. **No verification that backups restore correctly in CI.**

**Disaster Recovery.** `docs/DISASTER_RECOVERY.md`, `docs/RPO_RTO.md`, `docs/RUNBOOK.md` exist (Sprint 4 docs).

**RPO/RTO.** Documented, not yet **drilled**. A document without a drill is a story, not a plan.

**Helm.** **None.**

**GitOps.** ArgoCD client exists; **no ArgoCD app-of-apps for UniOps itself, no GitOps-of-GitOps, no Flux/Bootstrap.**

**ArgoCD.** Real client code, but no ArgoCD installation in the repo.

### 7.2 Problems

1. **No HPA, no PDB, no NetworkPolicy** — K8s deployment is not production-grade by 2026 standards.
2. **Secrets via env vars** is a single-source-of-secret-leakage.
3. **DR is documented, not drilled.** A runbook that has never been run is a hope.
4. **No Helm** makes the install story dependent on a human. That's a sales-blocker.

### 7.3 Recommendations

- Add **HPA + PDB + NetworkPolicy** in next sprint.
- Adopt **External Secrets Operator** + cloud KMS.
- Add a **monthly DR drill** with measured RPO/RTO that goes into the deck.
- Convert Kustomize overlays to a **Helm chart** with values per env.

### 7.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| HPA + PDB + NetworkPolicy | P0 | 1 sprint | High | High |
| External Secrets Operator | P1 | 1 sprint | High | High |
| Helm chart | P1 | 1 quarter | High | Medium |
| Monthly DR drill | P0 | 1 day/month | **Critical** | High |

---

## 8. DevSecOps readiness

### 8.1 Current State **[EVIDENCE: STRONG]**

| Capability | Status | Evidence |
|---|---|---|
| **SAST** | Partial | Semgrep integration (37 LOC stub-like). No own SAST. |
| **DAST** | None | No DAST scanner integrated. |
| **IAST** | None | No agent-based runtime analysis. |
| **Container Security** | Real | Trivy integration (126 LOC) — real, not stub. |
| **SBOM** | Real | Syft integration produces SBOM. SBOM model exists. |
| **Secrets scanning** | None | No TruffleHog / Gitleaks integrated into pipelines. |
| **Supply chain** | None | No Sigstore, no Cosign, no SLSA, no attestations. |
| **Policy as Code** | None | No OPA, no Kyverno, no Conftest, no admission controller. |
| **Dependency Mgmt** | Real | `pip-audit` is a dev dep; uv-managed. |

### 8.2 Problems

1. **UniOps is a consumer of security signals, not a producer of supply-chain attestations.** This is fine for a Security Data Platform, fatal for a "DevSecOps Platform" claim.
2. **No admission controller integration** — UniOps cannot actually enforce a policy in a cluster.

### 8.3 Recommendations

- **Reframe:** UniOps is a Security Decision & Remediation Platform. It *consumes* SAST/DAST/SCA from other tools, *normalizes* them, and *remediates*. It does not replace them. Update the homepage.
- Add a **policy admission integration** (Kyverno/OPA Gatekeeper) so decisions can be enforced.

### 8.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Reframe product positioning | P0 | 1 week | **Critical** | — |
| OPA / Kyverno admission integration | P1 | 1 quarter | High | **High** |
| DAST integration (ZAP baseline) | P2 | 6 weeks | Medium | Medium |

---

## 9. Security architecture review

### 9.1 Current State **[EVIDENCE: STRONG]**

| Aspect | Status | Evidence |
|---|---|---|
| **Identity** | Username/password + JWT + 2FA | `app/core/security/` |
| **SSO/OIDC/SAML/SCIM** | **None** | Not in repo |
| **RBAC** | Flat 26-permission dict, 5 roles | `constants/permissions.py` (91 LOC) |
| **ABAC** | **None** | No attribute-based predicates |
| **OPA** | **None** | |
| **Audit** | `AuditLog` model, audit_service (verified) | `app/services/audit_service.py` |
| **Encryption at rest** | Postgres (no TDE verified) | |
| **Encryption in transit** | TLS assumed at ingress; not verified | |
| **Key Management** | **None** — no Vault, no KMS, no rotation | |
| **Secrets** | env vars | `secret.example.yaml` |
| **Zero Trust** | Not implemented (no mTLS, no SPIFFE) | |
| **Threat Modeling** | Not documented in repo | |

### 9.2 Problems

1. **No enterprise identity** — this is the #1 reason a real CISO cannot buy.
2. **No key management** — losing a database is a total compromise.
3. **RBAC is too coarse** — 26 permissions cannot express "can view vulnerabilities in prod but not in staging" or "can approve a fix only for repos in their team."

### 9.3 Recommendations

- **Add OIDC + SAML + SCIM** in next 2 quarters. Use `authlib` or `pyoidc`; do not roll your own.
- **Add ABAC** via OPA with a small policy bundle.
- **Adopt Vault** (or cloud KMS) for secret and key management.
- Define a **threat model document** as a deliverable.

### 9.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| OIDC + SAML | P0 | 1 quarter | **Critical** | High |
| SCIM 2.0 | P1 | 1 quarter | High | High |
| ABAC via OPA | P1 | 1 quarter | High | **High** |
| Vault / KMS | P1 | 1 quarter | High | **High** |
| Threat model doc | P0 | 1 week | High | Medium |

---

## 10. AI architecture review

### 10.1 Current State **[EVIDENCE: STRONG]**

| Aspect | Status | Evidence |
|---|---|---|
| **Copilot endpoint** | Real (101 LOC) | `endpoints/copilot.py` |
| **Copilot service** | Real (210 LOC) | `services/copilot_service.py` |
| **Copilot context builder** | Real (168 LOC) | `services/copilot_context_builder.py` |
| **Copilot data model** | Real | `models/copilot.py` + migration `55a7b04e2fda_add_copilot_tables.py` |
| **LLM Gateway** | **None** | Not in repo |
| **Memory** | DB-backed session + messages | |
| **Knowledge Graph** | `services/graph/` exists; `models/graph.py` exists | Real, not integrated with LLM |
| **Agents** | None | No agent framework |
| **Tool Calling** | None | |
| **RAG** | None | No vector store, no embeddings |
| **MCP** | **None** | Not in repo |
| **Prompt Governance** | None | No prompt registry, no eval, no red-team |
| **Model Routing** | None | |
| **AI Cost Control** | None | |
| **AI Security** | None | |
| **Human Approval** | Implemented (via Module 0) | Indirect — Copilot is not in the decision loop |

### 10.2 Problems

1. **The Copilot is a chat UI with no brain.** Context builder is real; LLM is not. The repo is shipping the shape of AI without the substance.
2. **No Knowledge Graph integration with Copilot.** The KG is its own service. This is a major missed connection.
3. **No MCP, no agent framework, no RAG.** These are table stakes for an "AI platform" in 2026.

### 10.3 Recommendations

- **60-day plan:** pick a single LLM provider (Anthropic or OpenAI), wire a gateway with provider abstraction, rate limiting, prompt logging, and cost control. Wire to Copilot.
- **Add a vector store** (pgvector, which Postgres 16 supports) for RAG over the Knowledge Graph and runbooks.
- **Adopt MCP** as the agent protocol, not a custom one.

### 10.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| LLM gateway with provider abstraction | P0 | 4 weeks | **Critical** | High |
| pgvector RAG over KG + runbooks | P1 | 6 weeks | High | **High** |
| MCP integration | P2 | 1 quarter | High | High |
| Prompt registry + eval + red-team | P1 | 1 quarter | High | High |

---

## 11. Data architecture review

### 11.1 Current State **[EVIDENCE: STRONG]**

- 51 models, 15 migrations, all tenant-isolated.
- No partitioning, no sharding.
- No event-sourcing, no CQRS.
- `audit_log`, `intelligence`, `risk`, `cost_metric`, `scan` will grow without bound.

### 11.2 Problems

1. **No retention policy** is enforceable in code.
2. **No time-series partitioning** for growth tables.
3. **No read-replica routing** — all reads hit primary.

### 11.3 Recommendations

- Add **Postgres native partitioning** for `audit_log`, `cost_metric`, `intelligence` (monthly partitions).
- Add a **read-replica router** for heavy analytics queries.
- Define **retention** (e.g., 7 years for audit, 1 year for intel cache).

### 11.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Partitioned growth tables | P1 | 1 quarter | Medium | **High** |
| Read-replica router | P2 | 1 quarter | Medium | High |
| Retention policies | P1 | 6 weeks | Medium | High |

---

## 12. Integration architecture

### 12.1 Current State **[EVIDENCE: STRONG]**

| Integration | LOC | Status |
|---|---|---|
| `kubernetes/client.py` | 873 | Real |
| `kubernetes/watcher.py` | 252 | Real |
| `github/client.py` | 376 | Real |
| `aws/cost_explorer.py` | 327 | Real |
| `aws/security_hub.py` | 290 | Real |
| `observability/prometheus.py` | 296 | Real |
| `observability/loki.py` | 245 | Real |
| `email/client.py` | 269 | Real |
| `gitops/argocd_client.py` | 255 | Real |
| `gitlab/client.py` | 178 | Real |
| `stripe/client.py` | 163 | Real |
| `scanners/trivy.py` | 126 | Real |
| `slack/client.py` | 82 | Real |
| `scanners/semgrep.py` | 37 | Likely stub (verify) |
| `aws/eks.py` | 17 | Likely stub |
| `github/actions.py` | 29 | Likely stub |
| `aws/client.py` | 109 | Generic wrapper |

### 12.2 Problems

1. **No Azure DevOps, no Bitbucket, no GCP, no Datadog, no PagerDuty, no ServiceNow, no Jira, no Linear** — the platform engineering buyer uses these.
2. **No integration marketplace** — every integration is hand-built.

### 12.3 Recommendations

- Prioritize **PagerDuty, ServiceNow, Datadog, Azure DevOps** for the platform-engineering buyer.
- Build a **plugin SDK** so customers can write their own integrations.

### 12.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| PagerDuty + ServiceNow | P0 | 6 weeks | **High** | Medium |
| Datadog | P1 | 6 weeks | High | Medium |
| Azure DevOps + Bitbucket | P1 | 1 quarter | High | Medium |
| Plugin SDK | P2 | 1 quarter | High | **High** |

---

## 13. Scalability review

### 13.1 Current State **[EVIDENCE: MODERATE]**

| Tenants | Verdict | First to break |
|---|---|---|
| 100 | ✅ | — |
| 1,000 | ✅ likely | Redis connection pool, Celery prefetch tuning |
| 10,000 | ⚠️ | Postgres (no partitioning, no read replicas), audit log growth, single Redis |
| 100,000 | ❌ | Event bus (in-process), Postgres write contention, audit retention |

### 13.2 Problems

1. **In-process event bus** is a horizontal-scale killer.
2. **Single Postgres** is a SPOF at 10K+ tenants.
3. **Audit log growth** without partitioning will hit the IOPS ceiling.

### 13.3 Recommendations

- Move to **Redis Streams** (or NATS JetStream) for events.
- Move audit/intelligence to **partitioned tables** with cold storage offload.
- Define a **sharding strategy** for tenants (e.g., tenant_id modulo).

### 13.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Redis Streams event bus | P0 | 1 quarter | **High** | **Critical** |
| Partitioning + cold storage | P1 | 1 quarter | High | **Critical** |
| Tenant sharding plan | P2 | 1 quarter | High | High |

---

## 14. Enterprise readiness

### 14.1 Current State **[EVIDENCE: STRONG]**

| Capability | Status |
|---|---|
| SSO (OIDC) | ❌ |
| OIDC | ❌ |
| SAML | ❌ |
| SCIM 2.0 | ❌ |
| SOC 2 | Not started (likely) |
| ISO 27001 | Not started (likely) |
| PCI DSS | Not applicable (we don't take card data via app) |
| HIPAA | Not started |
| FedRAMP | Not started |
| GDPR | Partial (tenant isolation, audit) |
| Air Gap | Not supported |
| Offline Mode | Not supported |
| Multi Region | Single region only |
| HA | Single-region HA possible; not multi-AZ verified |
| DR | Documented, not drilled |
| Feature Flags | None visible |
| License Management | Plans exist; no license server |
| Quota | Not visible |
| Entitlements | RBAC only |

### 14.2 Problems

1. **No SSO = no enterprise sale.** This is the single biggest enterprise blocker.
2. **No compliance posture** is the #2 blocker.
3. **No air-gap / offline mode** rules out defense / intel / gov.

### 14.3 Recommendations

- 2-quarter sprint: **OIDC + SAML + SCIM + audit-export + role delegation**.
- 4-quarter sprint: **SOC 2 Type II readiness**.
- 6-quarter sprint: **FedRAMP Moderate readiness** (only if a gov buyer materializes).

### 14.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| OIDC + SAML | P0 | 1 quarter | **Critical** | High |
| SCIM 2.0 | P0 | 1 quarter | **Critical** | High |
| SOC 2 Type II | P1 | 4 quarters | **Critical** | Medium |
| FedRAMP Moderate | P3 | 6 quarters | High | High |
| Air-gap mode | P3 | 2 quarters | Medium | High |

---

## 15. Competitive benchmark

### 15.1 Current State **[EVIDENCE: MODERATE]**

| Competitor | UniOps relative position |
|---|---|
| **Wiz** | Loses on UX, agentless scan depth, ecosystem. **Wins on** open architecture, multi-cloud normalizer, audit-trail depth. |
| **Prisma Cloud** | Loses on runtime defense, policy library, install footprint. **Wins on** pricing transparency (presumed), tenant model. |
| **Orca** | Similar to Wiz. Loses on data depth. |
| **Snyk** | Loses on dev-toolchain integration, IDE presence. **Wins on** decision/remediation depth. |
| **GitHub Advanced Security** | Loses on ecosystem. **Wins on** cross-repo, cross-cloud, K8s-native. |
| **GitLab Ultimate** | Loses on bundled CI. **Wins on** standalone, K8s-first, AI-ready. |
| **Harness** | Loses on CI/CD feature depth. **Wins on** security decision quality. |
| **Backstage** | Loses on adoption, plugins. **Wins on** security context in the portal. |
| **Port** | Same as Backstage. Loses on UX polish. |
| **Cortex** | Loses on catalog depth. **Wins on** decision loop. |
| **Humanitec** | Loses on platform orchestration. **Wins on** security context. |
| **Datadog** | Loses on telemetry scale. **Wins on** decision depth per finding. |
| **Cortex XSIAM** | Loses on telemetry scale, SIEM features. **Wins on** open architecture. |
| **CrowdStrike Falcon** | Loses on endpoint, scale. **Wins on** cloud-native. |
| **Microsoft Defender for Cloud** | Loses on Azure integration. **Wins on** neutrality, K8s-first. |

### 15.2 Where UniOps can dominate (if executed)

1. **Decision-quality for cloud-native security** — best-in-class strategy + approval + execution chain.
2. **Multi-cloud normalizer with provenance** — the unification layer.
3. **Closed-loop remediation** — the only platform where a finding becomes a PR that becomes a deploy that becomes an audit entry, in one chain.
4. **Open architecture for AI** — when the LLM gateway is real, UniOps can be the substrate for security copilots in a way Wiz and Defender cannot.

### 15.3 Where UniOps will lose (if unchanged)

- UX polish.
- Telemetry/observability.
- Compliance content library.
- Ecosystem reach.

### 15.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| Lead the decision-quality narrative | P0 | 1 quarter | **Critical** | — |
| Build the "closed-loop" demo | P0 | 6 weeks | **Critical** | — |
| Invest in UX polish | P1 | ongoing | High | — |

---

## 16. Developer experience

### 16.1 Current State **[EVIDENCE: STRONG]**

| Capability | Status |
|---|---|
| CLI | None (`start.sh` only) |
| Python SDK | None |
| TypeScript SDK | None |
| Terraform provider | None |
| Pulumi provider | None |
| VSCode extension | None |
| JetBrains plugin | None |
| Marketplace | None |
| Plugin SDK | None |
| Public REST docs | None |
| GraphQL | None |
| CLI scaffolder | None |

### 16.2 Problems

1. **A platform without a CLI is a product.** This is the most fixable gap on this list and the highest ROI per engineering hour.
2. **No public docs site** is the second-most fixable.

### 16.3 Recommendations

- **8-week plan:** ship a `uniops` CLI binary (Go) with `init`, `login`, `scan`, `policy`, `decision`, `remediate`. Reuse the OpenAPI spec.
- **12-week plan:** ship a TypeScript SDK and a Terraform provider.

### 16.4 Priority / Cost / Value

| Item | Priority | Eng Cost | Business Value | Technical Value |
|---|---|---|---|---|
| CLI binary | P0 | 8 weeks | **High** | High |
| TS SDK | P1 | 1 quarter | High | High |
| Terraform provider | P1 | 1 quarter | High | High |
| Public docs site (Mintlify) | P0 | 4 weeks | **High** | Medium |

---

## 17. Architecture quality — scorecard

| Subsystem | Score | Notes |
|---|---|---|
| **Backend core (FastAPI, deps, lifespan)** | 78 | Clean, production-shaped. |
| **Persistence (SQLAlchemy + Alembic)** | 65 | Strong; mixed 1.x/2.x idioms. |
| **Auth + RBAC** | 55 | Real, but coarse; no ABAC/SSO. |
| **Multi-tenancy** | 82 | Verified across all 51 models. |
| **API surface** | 70 | REST solid; no SDK, no GraphQL, no docs. |
| **Background jobs (Celery + APScheduler)** | 60 | No retries/DLQ visible. |
| **Events (In-process bus)** | 50 | Won't scale horizontally. |
| **Caching** | 65 | Real, no stampede protection. |
| **Observability (logs, metrics, traces, Sentry)** | 78 | Strong. |
| **Frontend (React/Vite)** | 60 | No tests. No Storybook. |
| **Scanning (Trivy, Semgrep, K8s, SBOM)** | 75 | Trivy real; Semgrep shallow. |
| **Intelligence providers** | 25 | 8/10 stubs; 2 real (NVD, OSV). |
| **Risk scoring** | 75 | Real, weighted. |
| **Investigation engine** | 70 | Sub-engines real, not flight-tested. |
| **Decision Engine (Module 0)** | 78 | Real, well-designed, but redundant with remediation. |
| **Remediation engine** | 82 | Most mature subsystem. |
| **Deployment / GitOps** | 75 | Real, but no Helm, no app-of-apps. |
| **Cost / FinOps** | 70 | Real. |
| **AI / Copilot** | 25 | Skeleton, no brain. |
| **Integrations** | 60 | Real where implemented; thin catalog. |
| **Infra (K8s, Compose, secrets)** | 60 | Solid base, no HPA/PDB/NetworkPolicy. |
| **Documentation** | 70 | RUNBOOK, RPO/RTO, DR exist. |
| **Tests** | 45 | 24 test files; no frontend; no E2E. |
| **CI/CD** | 50 | 1 workflow. |
| **Overall** | **64 / 100** | Beta → Production boundary, not yet defensible. |

---

## 18. Technical debt — prioritized

| ID | Item | Severity | Effort | Notes |
|---|---|---|---|---|
| TD-01 | No SSO / OIDC / SAML / SCIM | **P0** | 1Q | Sales blocker |
| TD-02 | No real LLM behind Copilot | **P0** | 1M | Marketing risk |
| TD-03 | Module 0 + remediation duplicate | **P0** | 1Q | Architectural confusion |
| TD-04 | In-process event bus | P1 | 1Q | Scale blocker |
| TD-05 | 8/10 intel providers are stubs | P1 | 1Q | Differentiation gap |
| TD-06 | Mixed SQLAlchemy 1.x/2.x | P1 | 1Q | Maintenance |
| TD-07 | No retries / DLQ on Celery | P1 | 1M | Reliability |
| TD-08 | No HPA / PDB / NetworkPolicy | P1 | 1 sprint | K8s maturity |
| TD-09 | No key management | P1 | 1Q | Security |
| TD-10 | No DR drill | P1 | 1 day/mo | Operability |
| TD-11 | No frontend tests | P1 | 1Q | Quality |
| TD-12 | No public OpenAPI docs | P1 | 1M | DX |
| TD-13 | No CLI / SDK | P1 | 1Q | DX |
| TD-14 | No vector store / RAG | P2 | 1Q | AI |
| TD-15 | No partitioning for growth tables | P2 | 1Q | Scale |
| TD-16 | No Helm | P2 | 1Q | Install story |
| TD-17 | No GitOps-of-GitOps | P2 | 1Q | Operability |
| TD-18 | No MCP / agent framework | P2 | 1Q | AI |
| TD-19 | No plugin SDK | P2 | 1Q | Ecosystem |
| TD-20 | No DAST | P3 | 1Q | Coverage |
| TD-21 | No secret scanning integrated | P3 | 1Q | Coverage |
| TD-22 | No SLSA / Sigstore | P3 | 1Q | Supply chain |
| TD-23 | No multi-region | P3 | 1 year | Scale |
| TD-24 | No air-gap mode | P3 | 1Q | Gov |
| TD-25 | No quota / entitlements | P2 | 1Q | SaaS maturity |
| TD-26 | RBAC too coarse (no ABAC) | P2 | 1Q | Enterprise |
| TD-27 | No feature flags | P2 | 1Q | Operability |
| TD-28 | Audit retention not enforced | P2 | 1M | Compliance |
| TD-29 | No E2E tests | P1 | 1Q | Quality |
| TD-30 | No SOC 2 | P1 | 4Q | Enterprise sales |

---

## 19. Missing business domains

| Domain | Why it matters | Effort to enter |
|---|---|---|
| **Compliance content library** (SOC 2 / ISO 27001 / HIPAA controls) | Enterprise sale requires it | 2Q |
| **Case management / SOC workflow** | SOC analysts won't adopt without it | 2Q |
| **Vulnerability disclosure / bug-bounty intake** | Differentiation | 1Q |
| **Asset inventory / CMDB** | CISO buys a CMDB, not a scanner | 2Q |
| **Identity governance** (joiner-mover-leaver) | Identity buyers expect it | 2Q |
| **Data classification / DSPM** | Cloud security buyers want it | 2Q |
| **Attack surface management (external)** | ASM is a top-3 CISOs spend | 2Q |
| **Application security posture (ASPM)** | Trendiest 2026 category | 2Q |
| **Cloud detection & response (CDR)** | Wedge into XDR | 3Q |

**Do not** try to own all of them. **Pick 1–2 for the next 18 months.**

---

## 20. Missing critical modules

| Module | Why |
|---|---|
| **Patch Generator** | The single feature that closes the loop. Without it, UniOps is an alert, not an action. |
| **Validation Engine** | Without it, every remediation is a guess. |
| **Git-side effects (PR creation, branch, commit)** | Same. |
| **Real Intel providers (EPSS, VulnCheck, KEV, CISA)** | Without them, the "intelligence" is OSV+NVD. |
| **OIDC + SAML + SCIM** | Sales. |
| **OPA / Kyverno** | Enforce the decisions. |
| **Workflow Engine DSL** | Customers will demand it. |
| **Plugin SDK** | Ecosystem. |
| **Public API + OpenAPI docs + CLI + SDK** | Platform. |
| **Vector store + RAG + LLM gateway** | AI. |
| **Compliance content library** | Enterprise. |
| **Case management** | SOC adoption. |
| **Multi-region** | Scale. |
| **DR drill automation** | Operability. |
| **Webhooks for inbound** | Extensibility. |

---

## 21. Roadmap critique

### 21.1 What the existing roadmap does well

- Phases by EPIC; each EPIC has 3–10 modules; modules are atomic.
- Front-loads hardening.
- Acknowledges the AI gap and the intelligence gap.

### 21.2 What the existing roadmap does badly

1. **Too many EPICs (15+)**. A team of 12 engineers cannot meaningfully execute 15 EPICs in 4 quarters. This is a wish list, not a plan.
2. **Lumping AI and Identity into mid-roadmap positions.** They are the two P0 enterprise blockers and should be EPIC 1 and EPIC 2.
3. **No explicit deprecation list.** A roadmap that does not say what to *stop* is not a roadmap.
4. **No explicit revenue / outcome per EPIC.** An EPIC without a measurable outcome is R&D, not a roadmap.

### 21.3 Deletions / merges / splits

- **Merge** Module 0 (Decisions) and `remediation/` into one EPIC.
- **Delete** the "AI Copilot" EPIC; replace with "Real LLM Gateway + RAG".
- **Split** the "Enterprise Identity" EPIC into OIDC+SAML (EPIC 1) and SCIM (EPIC 3).
- **Split** "Compliance" into "Compliance content" (EPIC 6) and "SOC 2 readiness" (EPIC 7).
- **Add** "Closed-loop demo" as EPIC 0.

---

## 22. New roadmap

**Principles:** ≤ 6 EPICs per quarter. Every EPIC has one measurable business outcome. No more than 2 EPICs run in parallel.

### Quarter 1 (Q1)

| # | EPIC | Outcome | Eng effort |
|---|---|---|---|
| **Q1-E0** | Closed-loop demo (Patch Gen + Git effects + Validation) | 1-click: finding → PR → review → merge | 6 weeks |
| **Q1-E1** | OIDC + SAML + audit export | First enterprise sale | 1 quarter |
| **Q1-E2** | Real LLM gateway + Copilot-on-KG | First AI demo that works | 1 quarter |

### Quarter 2 (Q2)

| # | EPIC | Outcome | Eng effort |
|---|---|---|---|
| **Q2-E0** | Module 0 ↔ remediation merge | One bounded context | 1 quarter |
| **Q2-E1** | SCIM 2.0 + role delegation | Enterprise procurement unblocked | 1 quarter |
| **Q2-E2** | Real intel providers (EPSS, KEV, VulnCheck) | Differentiation back | 6 weeks |

### Quarter 3 (Q3)

| # | EPIC | Outcome | Eng effort |
|---|---|---|---|
| **Q3-E0** | Workflow Engine DSL | First non-engineer can build a flow | 1 quarter |
| **Q3-E1** | CLI + TypeScript SDK + public docs | "Platform" claim becomes true | 1 quarter |
| **Q3-E2** | OPA / Kyverno admission integration | Decisions are *enforced* | 1 quarter |

### Quarter 4 (Q4)

| # | EPIC | Outcome | Eng effort |
|---|---|---|---|
| **Q4-E0** | SOC 2 Type II readiness | Enterprise sales motion | 4-quarter program, this is the year |
| **Q4-E1** | PagerDuty + ServiceNow + Datadog | Platform-team fit | 1 quarter |
| **Q4-E2** | Compliance content library (SOC 2 controls) | First compliance product | 1 quarter |

### Year 2

| # | EPIC | Outcome |
|---|---|---|
| **Y2-E0** | Plugin SDK + Marketplace v1 | Ecosystem |
| **Y2-E1** | Multi-region + tenant sharding | Scale |
| **Y2-E2** | Case management (SOC workflow) | SOC adoption |
| **Y2-E3** | Vector DB + RAG + MCP + agent framework | AI platform |

### Year 3

| # | EPIC | Outcome |
|---|---|---|
| **Y3-E0** | ASPM | Adjacent category |
| **Y3-E1** | DSPM | Adjacent category |
| **Y3-E2** | External ASM | Adjacent category |

### Year 4–5

| # | EPIC | Outcome |
|---|---|---|
| **Y4-E0** | FedRAMP Moderate | Gov |
| **Y4-E1** | Air-gap | Defense / intel |
| **Y5-E0** | Acquisition / partner surface for IDP | Category-defining |

---

## 23. 5-year vision

**North star:** *UniOps becomes the Operating System for Enterprise DevSecOps — the substrate that turns every security signal into an audited, governed, machine-executable action.*

**Year 1:** Closed-loop platform, enterprise-identity ready, real AI. **One product, one buyer (platform team), one demo.**

**Year 2:** Platform posture — SDK, CLI, marketplace, workflow engine. **The product becomes a platform.**

**Year 3:** Adjacent categories — ASPM, DSPM, ASM. **The platform becomes a portfolio, but still with one operating system underneath.**

**Year 4:** Compliance and government posture. **The portfolio becomes enterprise-default.**

**Year 5:** Category-defining. Either UniOps is acquired as the platform layer of a Wiz/Defender, or it becomes the next Wiz. The board's $100M question.

---

## 24. Engineering investment plan

**Assumed context:** $5M–$100M raise; team currently appears to be ~10–15 engineers (1 backend, 1 infra, 1 frontend, 1 ML, ~6 services). Plan below assumes a **target** steady-state team.

### $5M (12-month runway, lean)

| Role | Headcount | Focus |
|---|---|---|
| Backend Senior | 2 | Closed-loop, Module 0 merge |
| Backend Mid | 2 | OIDC/SAML, intel providers |
| Frontend Senior | 1 | Decisions tab, dashboard polish |
| DevOps Senior | 1 | HPA/PDB/NetworkPolicy, Helm, DR drill |
| QA | 1 | E2E, load, chaos |
| Product | 1 | Positioning, customer interviews |
| **Total** | **8** | **$1.6M loaded + $3.4M infra** |

### $10M (18-month runway)

| Role | Headcount | Focus |
|---|---|---|
| Backend Senior | 3 | Closed-loop, Module 0 merge, workflow engine |
| Backend Mid | 4 | OIDC/SAML/SCIM, intel, compliance, integrations |
| Frontend Senior | 2 | UI polish, Storybook, design system |
| Frontend Mid | 1 | Public docs site |
| DevOps Senior | 2 | Helm, GitOps, multi-region, DR drill |
| DevOps Mid | 1 | Observability, SLO |
| QA | 2 | E2E, load, chaos |
| Security Engineer | 1 | SOC 2, threat model |
| Product | 1 | Positioning |
| Designer | 1 | UX |
| **Total** | **18** | **$3.6M loaded + $6.4M infra** |

### $50M (3-year runway)

Add: ML engineering team (4), Security research (3), Solutions architects (4), Sales engineers (3), Customer success (3), Developer relations (2), Design (3), Compliance (2), SRE (3). **Total ~50.** Hire in waves Q1/Q3.

### $100M (5-year runway)

Build: a 110-person org with platform, product, GTM, customer success, security research, ML, design systems, and ecosystem teams. Hire a CMO, a VP Sales, a VP Customer Success, a CISO. **$25M/yr loaded; $75M product/infra/market.**

---

## 25. Organization design

**Recommended top-level teams (3 platforms × 4 GTM).**

```
UniOps Engineering
├── Platform Foundations (8)
│   ├── Persistence
│   ├── Identity & Access
│   ├── Events & Async
│   ├── SDK & CLI
│   └── SRE / Observability
├── Security Plane (10)
│   ├── Findings & Risk
│   ├── Intelligence
│   ├── Decision & Remediation (one team, not two)
│   ├── Investigation
│   └── Scanners
├── DevOps Plane (8)
│   ├── Deployment & GitOps
│   ├── Integrations
│   ├── Cost (FinOps)
│   └── Workflow Engine
├── AI Plane (5)
│   ├── LLM Gateway
│   ├── Copilot & RAG
│   ├── Agents / MCP
│   └── AI Safety / Eval
└── Shared
    ├── Frontend Platform
    ├── Design System
    └── Documentation / DX
```

**Repositories:** monorepo (current) is fine for ≤30 engineers. Beyond, split into `uniops/platform`, `uniops/security-plane`, `uniops/ai-plane`, `uniops/sdk`, `uniops/cli`, `uniops/contracts` (OpenAPI, JSON Schemas).

**Team boundaries:** Each team owns a **bounded context** (see §5). They own the models, the services, the API surface, the events, and the migrations. They do not own the UI.

---

## 26. Risk matrix

| Risk | Severity | Probability | Mitigation |
|---|---|---|---|
| **AI claim collapses under scrutiny** (no LLM) | High | High | Ship real LLM in 60 days, or rename |
| **No SSO blocks enterprise sales** | High | High | Q1-E1 |
| **Module 0 + remediation tech debt compounds** | High | Medium | Q2-E0 |
| **In-process event bus blocks 10K tenants** | High | Medium | Q3-E0 (Streams) |
| **No SOC 2 blocks enterprise** | High | High | Q4-E0 + parallel program |
| **Single Postgres SPOF** | High | Low | Read-replica + backups + drill |
| **Key person dependency** | High | Medium | Document, pair, on-call |
| **Hiring risk in ML / security** | Medium | High | Use contractors; partner with universities |
| **Compliance scope creep** | Medium | High | Cap at SOC 2 + ISO 27001 in year 1 |
| **Frontend test debt at scale** | Medium | High | 1 quarter E2E plan |
| **Public API drift** | Medium | Medium | OpenAPI CI gate |
| **No DR drill** | High | High | Monthly drill in Q1 |
| **Pricing strategy unclear** | High | Medium | Q1 customer interviews |
| **AI cost blow-up** (if LLM ships) | Medium | High | Token quotas, caching, model routing |
| **Vendor lock-in (ArgoCD, Stripe, etc.)** | Low | Medium | Document exit plans |

---

## 27. Top 100 improvements (ranked)

> Top-100 list (high ROI first). Each line: ID, title, priority, effort, ROI.

| # | Title | P | Effort | ROI |
|---|---|---|---|---|
| 1 | Pick a single positioning (closed-loop) | P0 | 1w | **Critical** |
| 2 | Ship real LLM gateway + Copilot-on-KG | P0 | 1M | Critical |
| 3 | Build Patch Generator + Git effects + Validation | P0 | 6w | Critical |
| 4 | Add OIDC + SAML | P0 | 1Q | Critical |
| 5 | Add SCIM 2.0 | P0 | 1Q | Critical |
| 6 | Real intel providers (EPSS, KEV, VulnCheck) | P1 | 6w | High |
| 7 | Merge Module 0 + remediation | P1 | 1Q | High |
| 8 | Move event bus to Redis Streams | P1 | 1Q | High |
| 9 | Add HPA + PDB + NetworkPolicy | P0 | 1 sprint | High |
| 10 | External Secrets + cloud KMS | P1 | 1 sprint | High |
| 11 | Monthly DR drill (automated) | P0 | 1 day/mo | High |
| 12 | Ship CLI binary (`uniops`) | P0 | 8w | High |
| 13 | Public OpenAPI docs site | P0 | 4w | High |
| 14 | TypeScript SDK | P1 | 1Q | High |
| 15 | Terraform provider | P1 | 1Q | High |
| 16 | Frontend E2E tests (Playwright) | P1 | 1Q | High |
| 17 | Frontend unit + Storybook | P1 | 1Q | High |
| 18 | OPA / Kyverno admission integration | P1 | 1Q | High |
| 19 | pgvector + RAG over KG | P1 | 6w | High |
| 20 | MCP integration | P2 | 1Q | High |
| 21 | Workflow Engine DSL | P1 | 1Q | High |
| 22 | Plugin SDK + Marketplace v1 | P2 | 1Q | High |
| 23 | SOC 2 Type II readiness (year program) | P1 | 4Q | High |
| 24 | Compliance content library (SOC 2 controls) | P1 | 1Q | High |
| 25 | PagerDuty + ServiceNow integrations | P0 | 6w | High |
| 26 | Datadog integration | P1 | 6w | High |
| 27 | Azure DevOps + Bitbucket | P1 | 1Q | High |
| 28 | Partition growth tables (audit, intel, cost) | P1 | 1Q | High |
| 29 | Read-replica router | P2 | 1Q | Medium |
| 30 | Audit retention enforcement | P1 | 1M | High |
| 31 | Mixed SQLAlchemy 1.x/2.x cleanup | P1 | 1Q | Medium |
| 32 | Celery retries + DLQ | P1 | 1M | Medium |
| 33 | Helm chart for install | P1 | 1Q | High |
| 34 | GitOps-of-GitOps (ArgoCD app-of-apps) | P2 | 1Q | Medium |
| 35 | Vault / KMS adoption | P1 | 1Q | High |
| 36 | Threat model document | P0 | 1w | High |
| 37 | Feature flags (LaunchDarkly or OSS) | P2 | 1Q | Medium |
| 38 | Quota + entitlements | P2 | 1Q | Medium |
| 39 | SLO definitions (per service) | P0 | 2w | High |
| 40 | Error budget policy | P1 | 2w | High |
| 41 | Cost anomaly → decision automation | P2 | 6w | High |
| 42 | Investigation sub-engines flight test | P1 | 1Q | Medium |
| 43 | Risk scoring: add CVE age + EPSS to formula | P1 | 1M | High |
| 44 | Multi-tenant rate limit dashboard | P1 | 1M | Medium |
| 45 | Per-tenant feature flag | P2 | 1Q | Medium |
| 46 | Audit log export to S3 / SIEM | P1 | 6w | High |
| 47 | Webhook outbound (per tenant) | P1 | 6w | High |
| 48 | Webhook inbound (per tenant) | P1 | 6w | High |
| 49 | Public status page per tenant | P3 | 1Q | Low |
| 50 | Tenant-scoped API keys | P1 | 1M | High |
| 51 | OAuth2 client credentials for B2B | P1 | 1M | High |
| 52 | Air-gap mode (offline bundle) | P3 | 1Q | Medium |
| 53 | Multi-region active/passive | P3 | 1y | High |
| 54 | Multi-region active/active | P3 | 2y | High |
| 55 | Sharding strategy (tenant_id) | P3 | 1Q | High |
| 56 | DAST (ZAP baseline) | P2 | 6w | Medium |
| 57 | Secret scanning (TruffleHog) | P2 | 1M | Medium |
| 58 | SLSA Level 3 for own artifacts | P2 | 1Q | Medium |
| 59 | Cosign signing for own images | P2 | 1M | Medium |
| 60 | In-toto attestations for own builds | P3 | 1Q | Low |
| 61 | Add `kube-bench` and `kube-hunter` scans | P1 | 1M | High |
| 62 | CIS benchmark mapping (Kubernetes, AWS) | P1 | 1Q | High |
| 63 | PCI DSS scope assessment | P3 | 1Q | Low |
| 64 | HIPAA scope assessment | P3 | 1Q | Low |
| 65 | ABAC via OPA (in addition to RBAC) | P1 | 1Q | High |
| 66 | Row-level security in Postgres | P2 | 1Q | Medium |
| 67 | mTLS between services (Linkerd or Istio) | P3 | 2Q | Medium |
| 68 | SPIFFE for workload identity | P3 | 2Q | Medium |
| 69 | Chaos engineering (Chaos Mesh) | P2 | 1Q | High |
| 70 | Load test (k6) on critical paths | P1 | 1M | High |
| 71 | Synthetic monitoring (Blackbox exporter) | P2 | 1M | Medium |
| 72 | Distributed tracing rollout (OTel) | P1 | 1Q | High |
| 73 | Span-level RBAC in traces | P3 | 1Q | Low |
| 74 | Refactor to ASGI lifespan (already done) | — | — | — |
| 75 | Reduce cold start (worker pool) | P2 | 1M | Medium |
| 76 | Add /readyz, /livez, /startupz (done in S4) | — | — | — |
| 77 | Multi-tenant cache isolation (namespaces) | P1 | 1M | High |
| 78 | Cache stampede protection (singleflight) | P2 | 1M | Medium |
| 79 | Negative cache (intel) | P2 | 1M | Medium |
| 80 | Backfill workflows (idempotent) | P1 | 1Q | High |
| 81 | Replay events (idempotency) | P2 | 1Q | Medium |
| 82 | Time-series DB for cost (TimescaleDB) | P3 | 1Q | Medium |
| 83 | Data warehouse export (Snowflake/BigQuery) | P3 | 1Q | Medium |
| 84 | Reverse ETL (Hightouch or Census) | P3 | 1Q | Low |
| 85 | CDP / event streaming to external Kafka | P3 | 1Q | Medium |
| 86 | Customer-managed encryption keys (CMEK) | P1 | 1Q | High |
| 87 | Tenant-scoped KMS keys | P1 | 1Q | High |
| 88 | Data residency (EU, US, APAC) | P2 | 2Q | High |
| 89 | Backup encryption verification | P1 | 1M | High |
| 90 | Backup restore verification in CI | P1 | 1M | High |
| 91 | Pen test (annual) | P0 | annual | Critical |
| 92 | Bug bounty program | P1 | 1Q | High |
| 93 | Threat intel feed ingestion (own module) | P2 | 1Q | Medium |
| 94 | Investigation timeline visualization | P1 | 1Q | High |
| 95 | Graph query language (Cypher-like) | P2 | 1Q | Medium |
| 96 | Decision simulator (replay) | P1 | 1Q | High |
| 97 | Approval delegation chain | P1 | 1M | High |
| 98 | Auto-remediation rollback (built-in) | P1 | 1Q | High |
| 99 | "What changed?" diff for policies | P1 | 1M | High |
| 100 | Pricing page that is honest | P0 | 1w | Critical |

---

## 28. Top 50 mistakes / deletions

| # | Mistake | Action |
|---|---|---|
| 1 | "AI Copilot" shipped without an LLM | Either ship LLM in 60 days, or rename to "Context API" |
| 2 | Two parallel decision/remediation trees | Merge |
| 3 | In-process event bus scaled as if it were distributed | Replace with Redis Streams in Q3 |
| 4 | 8/10 intel providers as stubs | Implement 2 in Q2 |
| 5 | `intelligence/normalization/mappers/impls/capec.py` returns `None` | Delete the stub; or implement |
| 6 | `services/investigation/session/` empty | Delete or implement |
| 7 | `services/investigation/query/optimizer.py` 12-line stub | Delete or implement |
| 8 | RBAC as a 91-line flat dict | Replace with OPA |
| 9 | Secrets as env vars in K8s | Replace with ESO + KMS |
| 10 | Single Postgres, no partitioning | Partition growth tables |
| 11 | No DR drill | Drill monthly |
| 12 | `services/intelligence/service.py` `get_exploit()` returns `None` | Delete method or implement |
| 13 | The "ML service" is scikit-learn on pandas | Reframe as "ML inference" or build real MLOps |
| 14 | Frontend has zero tests | Add E2E + unit |
| 15 | CI is one workflow | Build proper CI matrix |
| 16 | No Helm | Build a chart |
| 17 | No HPA/PDB/NetworkPolicy | Add in next sprint |
| 18 | No SSO | Add in Q1 |
| 19 | Pricing page is aspirational | Make it honest |
| 20 | Module 0 has 4 sub-modules; remediation has 12 sub-modules | One bounded context, one team |
| 21 | `intelligence/providers/impls/base_stub.py` returns `None` for everything | Delete stubs or implement |
| 22 | `remediation/registry/provider.py` 10 lines | Either expand or delete |
| 23 | `core/kubernetes/__init__.py` 0 bytes | Add public exports |
| 24 | `app/integrations/__init__.py` 0 bytes | Add public exports |
| 25 | `app/remediation/plugins/` empty | Delete or build |
| 26 | `app/remediation/factories/` empty | Delete or build |
| 27 | `app/remediation/providers/` empty | Delete or build |
| 28 | `app/remediation/strategies/` empty | Delete or build |
| 29 | `app/remediation/validators/` empty | Delete or build |
| 30 | `app/events/` empty | Either replace `core/events` or delete |
| 31 | `app/core/` is a junk drawer | Refactor by domain |
| 32 | `app/services/` is a junk drawer | Refactor by domain |
| 33 | 208 TSX files; no `__tests__` directory | Add tests or die |
| 34 | No feature flags | Adopt one |
| 35 | "Rate limiting fail-open" — good, but no rate-limit dashboard | Add dashboard |
| 36 | Audit log retention not enforced | Enforce |
| 37 | No SLA / SLO definitions | Define |
| 38 | No public API docs | Add |
| 39 | No CLI | Add |
| 40 | No SDK | Add |
| 41 | No Terraform provider | Add |
| 42 | No marketplace | Either build or remove from roadmap |
| 43 | "Decision Engine" naming conflicts with "remediation decision" | One name, one thing |
| 44 | Approval engine in `remediation/` AND in `decision_approval/` | Merge |
| 45 | "Strategy engine" is a one-off; not a pattern | Promote or demote |
| 46 | Multiple Redis uses not namespaced | Namespace |
| 47 | `init_db` no-op in prod — good, but no migration gating | Add pre-deploy migration check |
| 48 | `start.sh` not portable | Replace with Make targets or a CLI |
| 49 | Compliance is data, not code | Promote to executable tests-as-code |
| 50 | Two reports named `readme*.md` and one `ffreport.md` | Consolidate |

---

## 29. Top 25 competitive advantages (if executed)

1. **Closed-loop remediation, in one chain** (finding → PR → review → merge → deploy → audit).
2. **Multi-cloud normalizer with provenance** (audit trail of every score, every source).
3. **Decision-quality at the strategy layer** (10-dim scoring, comparator, ranking).
4. **Open architecture for AI** (MCP, RAG, agent-ready).
5. **Audit-grade approval** (9-state lifecycle, evaluators, escalation).
6. **Deployment / GitOps as a first-class citizen** (not a separate tool to integrate).
7. **Real K8s-first semantics** (pod, cluster, watcher, GitOps).
8. **Real Trivy + real SBOM** (not a UI claim).
9. **Tenant isolation at the model layer** (verified across 51 models).
10. **Real Stripe billing** (no theater).
11. **Real ArgoCD client** (not a wrapper).
12. **Real email/Slack notifications**.
13. **Real Prometheus + Loki integration**.
14. **Per-tenant rate limit** with **fail-open** (operator-friendly).
15. **Health split live/ready/startup** (K8s-native).
16. **Production validators** in config (SECRET_KEY, CORS, DEBUG).
17. **Shared `Base*` abstractions** (BaseCache, BaseLifecycle, BasePipeline).
18. **Transaction manager** with `commit_or_rollback` + side-effects.
19. **In-process event bus with WS bridge** (good enough for ≤1k tenants).
20. **Pydantic 2 + SQLAlchemy 2** (modern stack).
21. **Real investigation engine** (filter/search/timeline/correlation).
22. **Real risk scoring** (repo + tenant weighted).
23. **Copilot context builder** is real (even if the LLM is not).
24. **Multi-tenant per row, not per schema** (operational simplicity).
25. **Production docs** (RUNBOOK, RPO/RTO, DR, per-module READMEs).

The wedge is **#1 + #2 + #5**. The rest is table stakes or filler.

---

## 30. Final verdict

**If you became UniOps CTO tomorrow:**

### What I would stop building immediately
- The "AI Copilot" UI as it exists. It is a lie. Either ship a real LLM in 60 days, or rebrand the endpoint as "Context API" and remove it from the homepage.
- Module 0 and `remediation/` as two parallel engines. Stop adding features to either until they are merged.
- In-process event bus as a long-term assumption. Stop building features that depend on cross-process ordering.
- "Compliance" as data. Stop pretending framework rows are a product.
- Aspirational marketplace / plugin SDK. Stop writing it in the roadmap until year 2.

### What I would start building tomorrow morning
- **Patch Generator + Validation Engine + Git effects.** The closed-loop. The wedge.
- **OIDC + SAML.** The next enterprise deal requires it. Nothing else matters if we cannot get past procurement.
- **Real LLM gateway.** Either the AI claim is real, or the AI claim is gone.
- **A single `uniops` CLI binary.** A platform without a CLI is a product.
- **A real intel provider gap-fill.** EPSS, KEV, VulnCheck in 6 weeks.

### What I would delete
- Empty `remediation/plugins/`, `remediation/factories/`, `remediation/providers/`, `remediation/strategies/`, `remediation/validators/`.
- Empty `app/events/`.
- Empty `services/investigation/session/`.
- 12-line `services/investigation/query/optimizer.py` stub (or implement, but not in this half-shipped state).
- The 8 stub intel providers (or implement; do not leave in 50% state).
- `capec.py` mapper that returns `None`.
- Two `readme*.md` files and a `ffreport.md` file. Consolidate.

### What I would rewrite
- **Module 0 ↔ remediation merge.** One bounded context. One team. One aggregate.
- **RBAC.** Replace flat dict with OPA. Add ABAC.
- **Event bus.** Redis Streams.
- **Decision → Strategy → Approval → Execution naming.** Pick one vocabulary; "decision" is too overloaded.
- **Frontend.** Add tests, Storybook, design system. The 208 TSX files need a Storybook and a test per page.
- **The "AI Copilot"** end-to-end (gateway, RAG, MCP, eval).

### What I would merge
- Module 0 and `remediation/`.
- `decision_approval` and `remediation/engine/approval_engine`.
- `core/events` and `app/events` (delete the latter).
- `core/kubernetes` and `integrations/kubernetes` (or document the split).

### What I would split
- "Security" into "Findings" and "Policies" and "Intelligence" and "Investigation" — 4 contexts, not 1.
- "Platform" into "Foundations" and "DevOps" — 2 contexts.

### What I would postpone
- FedRAMP (year 4+).
- Air-gap (year 3+).
- Multi-region active/active (year 4+).
- DSPM, ASPM, ASM (year 3+, not now).
- Acquisition surface (year 5+).

### Smallest roadmap capable of making UniOps category-defining within 18 months

```
Q1: Closed-loop demo (Patch Gen + Git + Validation)        [hero feature]
Q1: OIDC + SAML + audit export                            [enterprise sale]
Q1: Real LLM gateway + Copilot-on-KG                      [AI claim real]
Q2: Module 0 ↔ remediation merge                          [bounded context]
Q2: SCIM 2.0 + role delegation                            [enterprise sale]
Q2: Real intel providers (EPSS, KEV, VulnCheck)           [differentiation]
Q3: Workflow Engine DSL                                   [extensibility]
Q3: CLI + TypeScript SDK + public docs                    [platform posture]
Q3: OPA / Kyverno admission integration                   [enforcement]
Q4: SOC 2 Type II readiness, year program                 [enterprise sale]
Q4: PagerDuty + ServiceNow + Datadog                      [platform team fit]
Q4: Compliance content library (SOC 2 controls)           [enterprise sale]
```

**If we ship Q1, we have a category-defining product. If we ship Q1 + Q2 + Q3 + Q4, we are a category-defining platform.**

**If we don't ship Q1, we die in the chasm between "lots of features" and "the platform team picks us."**

That is the answer.

---

## Appendix A — Evidence index (one-line per file)

> *Not exhaustive.* High-signal files only.

- `backend/app/main.py` (247 LOC) — FastAPI lifespan, observability init, scheduler, ML listener, deployment worker, event bus, K8s watcher, webhooks, startup-complete, Sentry handler.
- `backend/app/config.py` (191 LOC) — Pydantic Settings, production validators (SECRET_KEY ≥32, no placeholder, CORS ≠ * in prod, DEBUG=False in prod), RATE_LIMIT_* per-tenant.
- `backend/app/api/v1/router.py` (74 LOC) — 50+ REST endpoints registered with explicit tags.
- `backend/app/core/database.py` — Async SQLAlchemy 2.0, AsyncSessionLocal (FastAPI) + CelerySessionLocal (Celery), init_db no-op in prod.
- `backend/app/modules/security/_shared/transaction_manager.py` — TransactionManager.commit_or_rollback, run_in_transaction with side_effects, Prometheus metrics.
- `backend/app/modules/security/decision_engine/services/decision_pipeline.py` — 7-stage pipeline: Create Decision → Context Build → Validation → Decision Creation → Persistence → Statistics Update → R5 Rejection finalizer.
- `backend/app/modules/security/decision_strategy/services/strategy_engine.py` (14,927 bytes) — 10-dim scoring, comparator, ranking.
- `backend/app/modules/security/decision_approval/services/approval_engine.py` (10,383 bytes) — 7 default evaluators, 9-state lifecycle.
- `backend/app/modules/security/execution_orchestration/services/execution_pipeline.py` (20,629 bytes) — 12 readiness checks, immutable ExecutionPackage.
- `backend/app/remediation/` (2,317 LOC across 30+ files) — Detection → classification → decision → approval → recovery → quotas → locks → policy → estimator.
- `backend/app/services/intelligence/service.py` — facade, hard-codes NVD + OSV, `get_exploit()` returns None.
- `backend/app/services/intelligence/providers/impls/base_stub.py` — 10 providers, all `fetch_*` return None.
- `backend/app/services/investigation/engine.py` — InvestigationEngine, sub-engines (Filter, Search, Timeline, Correlation) + query pipeline (planner/optimizer/executor).
- `backend/app/core/events/event_bus.py` — InProcessEventBus, subscribe/emit + WS bridge.
- `backend/app/core/deployment_engine/` (1,408 LOC) — service, generators, argocd, git_provider, worker.
- `backend/app/integrations/kubernetes/client.py` (873 LOC) — real K8s client.
- `backend/app/integrations/gitops/argocd_client.py` (255 LOC) — real ArgoCD client.
- `backend/app/integrations/aws/cost_explorer.py` (327 LOC) — real Cost Explorer.
- `backend/app/integrations/stripe/client.py` (163 LOC) — real Stripe.
- `backend/app/ml/` (902 LOC across 8 files) — scikit-learn, model registry, feature store.
- `backend/app/services/copilot_*.py` (378 LOC) — tables, context builder, service, endpoint. No LLM gateway.
- `backend/app/constants/permissions.py` (91 LOC) — 26 flat permissions, 5 roles. No ABAC.
- `backend/app/constants/plans.py` — plans exist.
- `backend/app/services/billing_service.py` — billing service exists.
- `backend/app/models/subscription.py` — subscription model exists.
- `backend/app/api/v1/endpoints/billing.py` — billing endpoint exists.
- `backend/app/api/webhooks/stripe.py` — Stripe webhook exists.
- `backend/alembic/versions/001..015` (15 revisions + 1 copilot) — schema history.
- `docs/RUNBOOK.md` (12,209 bytes) — production runbook.
- `docs/RPO_RTO.md` — RPO/RTO documented.
- `docs/DISASTER_RECOVERY.md` — DR documented.
- `infra/k8s/` — api/worker/beat/backup, 3 overlays, probes, secrets strategies.
- `infra/k8s/backup/` — Backup CronJob (Sprint 4).
- `docker-compose.yml` — postgres:16, redis:7, backend, celery_worker, celery_beat, frontend (nginx) with healthchecks.
- `pyproject.toml` — FastAPI 0.111, SQLAlchemy 2.0.30, Celery 5.4, Redis 5, scikit-learn 1.5, Stripe 9.5, etc.
- `tests/services/investigation_test.py` and 23 others — 24 test files; no frontend tests; no E2E; no load.
- `artifacts/uniops/src/pages/SecurityCenter/sections/Decisions.tsx` — Sprint 3 R33 real backend.
- `artifacts/uniops/src/` — 208 TSX files, no tests, no Storybook.

---

## Appendix B — Decision register (this is not a code review; it is a decision document)

| Decision | Owner | Deadline | Status |
|---|---|---|---|
| Adopt the "Decision & Remediation Plane" positioning | CEO + CTO | This week | **Open** |
| Either ship LLM in 60 days or rename Copilot | CTO | 60 days | **Open** |
| Merge Module 0 + remediation | Eng Director | Q2 | **Open** |
| Adopt OIDC + SAML | Eng Director | Q1 | **Open** |
| Adopt OPA for policy | Eng Director | Q3 | **Open** |
| Move event bus to Redis Streams | Eng Director | Q3 | **Open** |
| Adopt Helm | DevOps Lead | Q1 | **Open** |
| Adopt External Secrets Operator | DevOps Lead | Q1 | **Open** |
| Adopt LaunchDarkly or OSS feature flags | Eng Director | Q1 | **Open** |
| Ship `uniops` CLI | DX Lead | Q3 | **Open** |
| Public docs site (Mintlify) | DX Lead | Q1 | **Open** |
| SOC 2 Type II readiness program | CISO hire | Year 1 | **Open** |
| Pen test (annual) | CISO hire | Q1 | **Open** |
| Monthly DR drill | SRE | This month | **Open** |
| Pricing page that is honest | CMO + CEO | Q1 | **Open** |
| Stop calling it "AI Copilot" if LLM not shipped | CTO | 60 days | **Open** |
| Delete empty stub directories | Eng Director | Q1 | **Open** |
| Consolidate `readme*.md` + `ffreport.md` | DX Lead | Q1 | **Open** |

---

**End of report.**

*For the one-pager companion, see `readme23_executive_brief.md`.*
