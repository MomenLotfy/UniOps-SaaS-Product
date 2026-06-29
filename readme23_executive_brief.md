# UniOps — Board / Lead-Investor One-Pager

**Companion to:** `readme23_enterprise_dd.md` (full DD)
**One-line:** UniOps is a credible Security Data Platform with a real remediation engine, a real GitOps layer, and a real multi-tenant core. It is not yet a coherent product, and the AI claim is unbacked.

---

## 1. What is UniOps?

A multi-tenant, K8s-native, cloud-native **Security Decision & Remediation Platform** — *positioned as such*. The repo contains:

- 51 SQLAlchemy models, 15 Alembic migrations, 50+ REST endpoints
- A real **Decision → Strategy → Approval → Execution** chain (Module 0)
- A real **Remediation engine** (detection, classification, decision, approval, recovery, quotas, locks, policy, estimator — 2,317 LOC)
- A real **Deployment / GitOps engine** (1,408 LOC, real ArgoCD client, real K8s client)
- A real **FinOps surface** (Cost Explorer, Prometheus, anomaly, predictor)
- A real **Investigation engine** (filter/search/timeline/correlation)
- A real **multi-tenant core** (tenant_id on every model; per-tenant rate limit; tenant-aware event bus)
- Production docs (RUNBOOK, RPO/RTO, DR)

It also contains:

- An **AI Copilot with no LLM** behind it (572 LOC, 0 inference)
- **8 of 10 intel providers** that are stubs returning `None`
- **Zero SSO / OIDC / SAML / SCIM**
- **Zero CLI, SDK, Terraform provider, or public docs**
- **Zero frontend tests**
- An **in-process event bus** that will not scale past ~1k tenants

---

## 2. Scores

| Axis | Score | Verdict |
|---|---|---|
| **Architecture quality** | **64 / 100** | Beta → Production boundary, not defensible |
| **Operational readiness** | **78 / 100** | Strong (health probes, rate limit, runbook, DR) |
| **Multi-tenancy** | **82 / 100** | Strong |
| **Backend core** | **78 / 100** | Strong |
| **Persistence** | **65 / 100** | Mixed SQLAlchemy styles |
| **Auth + RBAC** | **55 / 100** | Coarse, no SSO/ABAC |
| **Event bus** | **50 / 100** | In-process, not distributed |
| **AI / Copilot** | **25 / 100** | Skeleton, no brain |
| **Intel providers** | **25 / 100** | 8/10 stubs |
| **Frontend** | **60 / 100** | No tests, no Storybook |
| **Integrations** | **60 / 100** | Real where present, thin catalog |
| **Infra** | **60 / 100** | Solid base, no HPA/PDB/NetworkPolicy |
| **CI/CD** | **50 / 100** | 1 workflow |
| **Tests** | **45 / 100** | 24 backend, 0 frontend, 0 E2E |
| **Docs** | **70 / 100** | RUNBOOK, RPO/RTO, DR present |

**Overall: 64 / 100.** *Beta that should not be priced like a platform yet.*

---

## 3. The 5 things that must happen in 12 months

1. **Pick a single positioning** — "Decision & Remediation Plane" for cloud-native security. Stop being six products in a trench coat.
2. **Ship the closed-loop demo** — Patch Generator + Git effects + Validation Engine. Finding → PR → review → merge → deploy → audit, in one chain.
3. **Add OIDC + SAML + SCIM** — first enterprise sale requires it.
4. **Ship a real LLM gateway** — either the AI claim is real in 60 days, or the AI claim is removed from the homepage.
5. **Ship a `uniops` CLI + public OpenAPI docs + TypeScript SDK** — turn the product into a platform.

If 1–5 ship, UniOps is category-defining.
If 1–5 do not ship, UniOps dies in the chasm.

---

## 4. What to stop building (today)

- The empty `remediation/plugins/`, `remediation/factories/`, `remediation/providers/`, `remediation/strategies/`, `remediation/validators/` directories.
- The 8 stub intel providers (or implement; do not leave at 50%).
- The `capec.py` mapper that returns `None`.
- The empty `services/investigation/session/` directory and the 12-line `optimizer.py` stub.
- The "AI Copilot" UI as currently shipped — it is a marketing liability.
- "Compliance" as data — promote to executable tests-as-code or admit it is not a product.
- The aspirational marketplace / plugin SDK — it is year 2+ work.

---

## 5. What to delete (today)

- The 30+ empty stub files and directories enumerated in the full report's §28.
- The duplicate `app/events/` directory (use `app/core/events/`).
- The two `readme*.md` and one `ffreport.md` — consolidate to one canonical engineering handbook.

---

## 6. Money

| Investment | Outcome | Headcount | 12-mo spend |
|---|---|---|---|
| **$5M** | Q1–Q4 EPICs ship, 1 product, 1 buyer | 8 | $1.6M loaded + $3.4M infra |
| **$10M** | Q1–Q4 + SOC 2 + CLI/SDK | 18 | $3.6M loaded + $6.4M infra |
| **$50M** | Add ML, security research, GTM, CS, ecosystem | ~50 | per year |
| **$100M** | Full 5-year roadmap to category leadership | ~110 | $25M/yr loaded |

The **$10M plan** is the right one for a Series B. Anything less ships a beta; anything more burns capital before product-market fit.

---

## 7. Risks the board must know

1. **AI claim collapses under scrutiny.** Mitigation: ship a real LLM in 60 days or rename.
2. **No SSO = no enterprise sale.** Mitigation: Q1.
3. **Module 0 + remediation tech debt compounds.** Mitigation: Q2 merge.
4. **In-process event bus blocks scale past 10K tenants.** Mitigation: Q3 Redis Streams.
5. **No SOC 2 blocks enterprise sales.** Mitigation: parallel 4-quarter program starting Q1.
6. **No DR drill.** Mitigation: monthly drill starting this month.
7. **Key person dependency.** Mitigation: document, pair, on-call rotation.

---

## 8. Final verdict

UniOps is a **legitimately good beta** with a real architectural core, a real remediation engine, a real GitOps surface, and a real multi-tenant platform. The market window for "Decision & Remediation Plane" is open in 2026. The team must pick a positioning, ship a closed-loop demo, add enterprise identity, ship a real LLM, and turn the product into a platform with a CLI / SDK / public docs. **18 months of focused execution** makes this category-defining. **18 months of feature-accumulation** makes this a portfolio that dies in the chasm.

**The smallest roadmap capable of making UniOps category-defining in 18 months is in the full report, §22. The top 5 imperatives are above. The 50 things to stop doing are above. The 100 ranked improvements are in the full report. The risks are above. The investment is above. The decision is yours.**

---

*See `readme23_enterprise_dd.md` for the full 30-section, evidence-backed report.*
