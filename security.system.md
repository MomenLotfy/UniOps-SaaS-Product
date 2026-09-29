# Security Center — System Design Blueprint

## 1. Executive Summary

The **Security Center** of the UniOps SaaS product is a multi‑service security console that aggregates data from a variety of providers (AWS Security Hub, GitHub, GitLab, Kubernetes, etc.) and presents it through a rich UI consisting of many tabs/sections (Overview, Repositories, Infrastructure, Assets, Kubernetes, Threats, Vulnerabilities, Posture, Remediation, Intelligence, Compliance, Policies, Exceptions, Governance, Ownership, SLA Tracker, Reports, SBOM, Security Copilot, etc.).

* **Current state** – The codebase contains a complete end‑to‑end implementation at the source‑code level: API routes, services, database models, and UI components for all sections. However, the development database is empty, key background workers (repository scanning, SBOM enrichment, report generation) contain deterministic defects, and many provider integrations are not exercised in this environment. Consequently, most services are **PARTIAL / UNVERIFIED** – they exist but have not been verified with real data.

* **Critical gaps** –
  1. Repository scan worker fails due to an uninitialized `dedup_count` and a mismatched `RawFinding.raw_data` field, rendering the scan pipeline **BROKEN**.
  2. SBOM package vulnerability lookup always returns an empty list, making SBOM‑related findings **BROKEN**.
  3. Excel report export is a stub returning JSON, and PDF export is not implemented – **BROKEN**.
  4. Several UI actions are placeholders (e.g., Ownership edit alert, Remediation cancel), and many provider failure paths silently collapse to empty results.

* **Design direction** – The audit recommends a service‑by‑service redesign that respects each service’s data‑shape and user goal, moving away from a one‑size‑fits‑all dashboard. The proposed architecture separates **Global Security Context**, **Service Navigation**, and **Service Workspaces** that each employ the most appropriate UI model (Dashboard, Findings Explorer, Table+Detail, Timeline, Wizard, etc.).

The remainder of this document follows the mandated workflow (DISCOVER → MAP → … → DESIGN) and provides a traceable, evidence‑backed description for every tab, its backend, data model, current UI, and a proposed redesign.

---

## 2. Repository Baseline

| Item | Value |
|------|-------|
| **Current branch** | `main` |
| **Current commit (SHA)** | `1835c01a` (chore: sync Replit changes) |
| **Working tree status** | `clean` – no uncommitted changes |
| **Git diff stat** | *(no changes)* |

All subsequent analysis is performed on this clean snapshot.

---

## 3. Security Center Architecture

```
Security Center
│
├─ Frontend (React/TSX) – `artifacts/uniops/src/pages/SecurityCenter/sections/*`
│   ├─ UI components per tab (Overview, Repositories, …, SBOM, Copilot)
│   └─ State handling (loading, empty, error) per component
│
├─ API Layer (FastAPI) – `backend/app/api/v1/endpoints/*`
│   ├─ Route definitions per service (e.g., `/security/repos`, `/threats`)
│   └─ Request validation, tenant isolation, permission guards
│
├─ Service Layer – `backend/app/services/*`
│   ├─ Business logic for each domain (scan_engine, asset_discovery, sbom_service, …)
│   └─ Integration adapters (AWS, GitHub, GitLab, Kubernetes, Stripe, etc.)
│
└─ Persistence (PostgreSQL + SQLAlchemy models) – `backend/app/models/*`
    ├─ Tenant‑scoped tables: `Repository`, `Scan`, `Threat`, `Vulnerability`, `Asset`, `Cluster`, `SBOM`, `Report`, `Policy`, `Exception`, `Ownership`, `SLA`, `RemediationPlan`, `CopilotConversation`, …
    └─ Relations & audit fields (created_at, updated_at, tenant_id, user_id)
```

**Evidence** – UI component paths (e.g., `artifacts/uniops/src/pages/SecurityCenter/sections/Overview.tsx:1`), API routes (`backend/app/api/v1/endpoints/threats.py:14-69`), service files (`backend/app/services/scan_engine.py:1387-1459`), and model definitions (`backend/app/models/scan.py:7-77`).

---

## 4. Security Center Tab Inventory

| Tab (UI label) | Route (if any) | Internal identifier (component) | Security service | Primary purpose | User type | Current status | Backend support | API endpoints | Data source | Main components | Main actions | Main outputs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Overview | `/security/overview` | `sections/Overview.tsx` | Security Overview / Posture Dashboard | High‑level security posture, KPIs, trends | All security users | **PARTIAL** – UI renders zero‑data defaults | Yes (posture, threat, vulnerability aggregates) | `/security/overview`, `/security/posture`, `/security/threats/stats`, … | DB aggregates; no external feed required | KPI cards, charts, counters, empty‑state messages | Filter by time, navigate to detailed sections | Posture score, threat/vuln counts, compliance summary |
| Repositories | `/security/repos` | `sections/repositories/index.tsx` + `RepoDrawer.tsx` | Repository Management & Scanning | View repositories, trigger scans, view scan history | DevOps, security analysts | **BROKEN** – scan worker fails; UI partial | Yes (Repository & Scan models) | `/security/repos`, `/security/scan-history` | DB (Repository, Scan) | List, drawer detail, scan trigger | Repository list, scan status, scan details |
| Infrastructure | `/security/infrastructure` | `sections/infrastructure/index.tsx` | Cloud/Infra Asset Inventory | Show clusters, assets, costs, alerts | Cloud admins | **PARTIAL** – data empty in dev DB | Yes (Cluster, Asset models) | `/clusters`, `/assets`, `/costs` | DB + provider sync (AWS, K8s) | Tables, charts, empty‑states | Filter by cluster, asset type | Asset inventory, cost summary, alert counts |
| Assets | `/security/assets` | `sections/assets/index.tsx` | Asset Discovery | Discover cloud assets, status, sync | Cloud admins | **PARTIAL** – sync state local, no assets present | Yes (Asset model, sync service) | `/assets`, `/assets/stats`, `/assets/sync/status` | DB + provider sync (AWS) | List, drawer detail, sync action | Sync assets, view details | Asset list, sync status, statistics |
| Kubernetes Security | `/security/k8s` | `KubernetesSecurity.tsx` | K8s Cluster & Pod Findings | Scan clusters, show pod findings, topology | Platform engineers | **PARTIAL** – provider code present, no runtime data | Yes (Cluster, Pod, K8sFinding models) | `/k8s/clusters`, `/k8s/pods`, `/k8s/findings` | DB + K8s client | Topology view, tables, charts | Sync pods, view findings, filter | K8s findings, pod topology |
| Threats | `/security/threats` | `Threats.tsx` | Threat Management | List and manage detected threats (e.g., AWS Security Hub) | Security analysts | **PARTIAL** – CRUD code present, no persisted threats | Yes (Threat model) | `/threats`, `/threats/stats`, `/threats/{id}` | DB + scan adapters | Table, detail view, status badges | Resolve, suppress, update | Threat list, stats, details |
| Vulnerabilities | `/security/vulnerabilities` | `Vulnerabilities.tsx` | Vulnerability Management | List CVE/Dependabot findings | Security analysts | **PARTIAL** – CRUD present, no data | Yes (Vulnerability model) | `/vulnerabilities`, `/vulnerabilities/stats`, `/vulnerabilities/{id}` | DB + GitHub Dependabot, AWS Security Hub adapters | Table, cards, filters | Patch, suppress, link to repo | Vulnerability list, CVSS cards |
| Security Posture | `/security/posture` | `SecurityPosture.tsx` | Posture Scoring | Aggregate security score across dimensions | All security users | **PARTIAL** – formulas exist, mock categories | Yes (PostureScore model) | `/posture/summary`, `/posture/history` | DB aggregates | Score widgets, risk matrix, trend chart | Refresh snapshot, view history | Overall score, dimension breakdown |
| Remediation | `/security/remediation` | `Remediation.tsx` | Remediation Planning | Define, execute, roll‑back remediation plans | Security engineers | **PARTIAL / STUB** – UI placeholders, API stub for cancel | Yes (RemediationPlan model) | `/remediation`, `/remediation/{id}` | DB + worker (stub) | Plan list, timeline, action buttons | Propose, start, cancel (no‑op) | Remediation plans, execution status |
| Intelligence | `/security/intelligence` | `Intelligence.tsx` | Threat Intelligence Feed | Show IOCs, actors, techniques, feed sync | Analysts | **PARTIAL / UNVERIFIED** – API exists, no feed data | Yes (Intelligence models) | `/intelligence`, `/intelligence/feeds`, `/intelligence/sync` | DB (empty) | Tables, cards, feed sync button | Sync feeds, view details | Intel records, feed status |
| Compliance | `/security/compliance` | `Compliance.tsx` | Compliance Management | Frameworks, controls, evidence, assessments | Compliance officers | **PARTIAL / UNVERIFIED** – UI/ API present, no data | Yes (Framework, Control, Evidence models) | `/compliance/frameworks`, `/compliance/controls`, `/compliance/evidence` | DB (empty) | Tabs, tables, export button | Export PDF (unverified) | Compliance status, gaps |
| Policies | `/security/policies` | `Policies.tsx` | Policy / Rule Engine | Define security policies, view violations | Policy admins | **PARTIAL / UNVERIFIED** – CRUD present, no violations | Yes (Policy model, evaluator) | `/policies`, `/policies/violations` | DB (empty) | List, stats, create, seed | Seed builtin, edit, delete | Policy list, violation counts |
| Exceptions | `/security/exceptions` | `Exceptions.tsx` | Exception Management | Create/revoke exceptions for findings | Security analysts | **REAL (source) / UNVERIFIED** – CRUD present, UI stub | Yes (Exception model) | `/exceptions`, `/exceptions/{id}` | DB (empty) | List, create, revoke | Create, revoke, filter | Exception records |
| Governance | `/security/governance` | `GovernanceOverview.tsx` | Governance Dashboard | Summarize scores, SLA, ownership, risk | Exec/leadership | **PARTIAL / UNVERIFIED** – aggregation code, no data | Yes (multiple models) | `/governance/overview` | DB aggregates | Charts, tables, empty states | Filter by time, view details | Governance summary |
| Ownership | `/security/ownership` | `Ownership.tsx` | Resource Ownership | Map owners to assets/resources | Ops managers | **PARTIAL / STUB** – UI edit placeholder | Yes (Ownership model) | `/ownership`, `/ownership/import`, `/ownership/export` | DB (empty) | List, import/export, edit (alert) | Import, export, edit (stub) | Ownership mappings |
| SLA Tracker | `/security/sla` | `SLATracker.tsx` | SLA Tracking | Track resolution time for threats/vulns | Ops/Support | **PARTIAL / UNVERIFIED** – static windows, DB sync | Yes (FindingSLA model) | `/sla`, `/sla/sync` | DB (empty) | Summary cards, list | Sync SLA, view overdue | SLA stats |
| Reports | `/security/reports` | `Reports.tsx` | Report Generation | Compile executive, vulnerability, posture reports | All | **PARTIAL / BROKEN** – Excel stub, PDF unimplemented | Yes (Report model) | `/reports`, `/reports/{id}/download` | DB compiled content | List, template selector, generate | Generate, download (Excel stub) | Generated reports (JSON placeholder) |
| SBOM | `/security/sbom` | `SBOM.tsx` | Software Bill‑of‑Materials | Generate, view dependency tree, export CycloneDX/SPDX | DevSecOps | **PARTIAL / BROKEN** – vulnerability lookup returns empty | Yes (SBOM model) | `/sbom`, `/sbom/{id}` | DB (SBOM records) | Tree view, charts, export buttons | Export, view details | SBOM document, component list |
| Security Copilot | `/security/copilot` | `SecurityCopilot.tsx` | LLM‑assisted Guidance | Conversational assistant for findings | All | **PARTIAL / UNVERIFIED** – persistence present, fallback deterministic response | Yes (CopilotConversation model) | `/copilot/conversations`, `/copilot/messages` | DB (empty) | Chat UI, context panel | Ask, view history | Conversation threads |

**Note** – Tabs that are conditionally hidden by role or feature flags were searched in the codebase; none were found beyond the list above.

---

## 5. Service Dependency Map

```
Security Center
│
├─ Overview (aggregates) → PostureService, ThreatService, VulnerabilityService, ComplianceService
├─ Repositories → ScanEngine → Scanner binaries (Semgrep, Trivy, Gitleaks, Bandit, pip‑audit, npm, Docker) → Scan persistence
├─ Infrastructure → AssetDiscoveryService (AWS) + ClusterService (K8s)
├─ Assets → AssetDiscoveryService → Provider sync (AWS)
├─ Kubernetes Security → K8sSecurityService → K8s client → Pod sync → Findings
├─ Threats ← ScanEngine (AWS Security Hub, custom adapters)
├─ Vulnerabilities ← ScanEngine (GitHub Dependabot, AWS Security Hub)
├─ Posture ← SecurityPostureService (DB aggregates)
├─ Remediation ← RemediationPlanService → Worker (stub)
├─ Intelligence ← IntelligenceService → Provider feeds (unspecified)
├─ Compliance ← ComplianceService (frameworks, controls, evidence)
├─ Policies ← PolicyService → Evaluator
├─ Exceptions ← ExceptionService
├─ Governance ← GovernanceOverviewService (aggregates multiple services)
├─ Ownership ← OwnershipService
├─ SLA Tracker ← SLAService (derived from threats/vulns)
├─ Reports ← ReportService (compiles data from many services)
├─ SBOM ← SBOMService (Syft fallback, manifest parser)
└─ Security Copilot ← CopilotService (conversation persistence, context builder)
```

**Evidence** – Service files (e.g., `backend/app/services/scan_engine.py:1387-1459`), API route files, UI component imports.

---

## 6. Current Security Center Information Architecture

The current UI follows a **tab‑based navigation** where each tab loads its own section component. Most sections share a similar skeleton:

1. **Header** – title, optional action button (e.g., “Run scan”).
2. **Filters / Search** – small toolbar at top.
3. **Main content** – varies per service (cards, tables, charts, tree).  
4. **Empty / Loading / Error states** – each component contains explicit `if (data.length===0)` blocks.
5. **Detail drawer / modal** – for individual items.

Because many services expose similar *finding* objects (Threat, Vulnerability, Asset), the UI repeats patterns (table + status badge) rather than using a shared component library.

---

## 7. Service‑by‑Service Analysis

Below each service is described according to the workflow phases (Purpose, Inputs, Processing, Outputs, Lifecycle, Data Model, Current UI, UX problems, Classification, Recommended UI model, Proposed redesign).  The **CURRENT** sections are directly extracted from the code; **PROPOSED** sections are recommendations.

---

### 7.1 Overview (Security Posture Dashboard)

**Purpose** – Provide a high‑level health snapshot of the tenant’s security posture, combining threat, vulnerability, compliance, asset, and policy scores.  

**Inputs** – Aggregated counts from DB tables: `Threat`, `Vulnerability`, `Compliance`, `Asset`, `Policy`, plus historical `SecurityPostureScore` rows.  

**Processing** – `SecurityPostureService` reads aggregates, applies weighting, and returns a score per dimension. UI normalizes missing data to defaults (e.g., 100 for no threats). Mock‑derived “misconfiguration categories” are hard‑coded based on risk counts.  

**Outputs** – Overall posture score, per‑dimension scores, trend chart data, KPI cards (critical findings, compliance coverage).  

**Lifecycle** – No explicit states; renders `loading → data (or empty) → error`.  

**Data Model** – `SecurityPostureScore` (tenant_id, score, timestamp, breakdown JSON).  

**Current UI** – Dashboard with KPI cards, bar/line charts, empty‑state messages (`OverviewCharts.tsx:374‑378`).  

**UX Problems** – Inconsistent empty‑data defaults across dimensions; mock categories not flagged as synthetic; no drill‑down from KPI cards.  

**Classification** – *Security Overview* → Dashboard.  

**Recommended UI Model** – **Dashboard** with explicit “No data” banners and a *Detail* link on each KPI to navigate to the corresponding service.  

**Proposed Redesign** – Add a shared `FindingBadge` component, surface mock‑derived categories with a “synthetic” tag, and ensure all score cards link to their service (e.g., Threats → Threats tab).

---

### 7.2 Repositories & Repository Scanning

**Purpose** – List code repositories, trigger security scans, view scan history.  

**Inputs** – `Repository` rows, `Scan` rows, scanner binaries.  

**Processing** – `run_scan.py` clones repo, runs `scan_engine` (SAST, secrets, dependency, optional container/CI), persists `Threat`/`Vulnerability` rows.  

**Outputs** – Scan status (`queued`, `scanning`, `completed`, `failed`), scan summary, findings linked to repository.  

**Lifecycle** – `Not Configured → Scanning → Completed → Findings Available → Remediated` (theoretically).  

**Data Model** – `Repository`, `Scan` (id, repo_id, status, timestamps, raw_results).  

**Current UI** – Repository list table, drawer with repo details; scan button triggers API call; empty state when no repos.  

**Critical Issues** – **BROKEN**: `dedup_count` used before init (`run_scan.py:201‑209`) and `RawFinding.raw_data` mismatch (`scan_engine.py:1066`). These cause runtime `UnboundLocalError` / `AttributeError`, marking every scan as **failed**.  

**UX Problems** – No indication of scan progress, no error detail when scan fails, drawer does not show scan results.  

**Classification** – *Security Scanning* → Wizard/Scanner.  

**Recommended UI Model** – **Scanner / Wizard**: Step‑by‑step UI guiding the user through repo selection, scan configuration, progress view, and results.  

**Proposed Redesign** – Fix backend defects, then build a multi‑step wizard that shows real‑time progress (using WebSocket events), and on success displays a findings explorer (linking to Threats/Vulnerabilities tabs).

---

### 7.3 Infrastructure (Clusters & Assets)

**Purpose** – Show cloud infrastructure assets (clusters, assets, costs, alerts).  

**Inputs** – `Cluster` rows, `Asset` rows, cost data from AWS Cost Explorer, alert data.  

**Processing** – `AssetDiscoveryService` syncs assets from AWS; `ClusterService` aggregates usage.  

**Outputs** – Asset list, cost summary, alert counts, topology charts.  

**Lifecycle** – `Empty → Syncing → Synced → Error`.  

**Data Model** – `Cluster`, `Asset`, `CostSnapshot`, `Alert`.  

**Current UI** – Section with charts and tables; empty states when no data (`OverviewInfra.tsx:104‑126`).  

**UX Problems** – Empty‑state handling is clear, but no filtering by region/account; sync status is only a local in‑memory flag.  

**Classification** – *Cloud Security / Infrastructure Security* → Dashboard + Table.  

**Recommended UI Model** – **Dashboard** for cost/alert KPIs plus **Table+Detail** for asset list.  

**Proposed Redesign** – Replace in‑memory `_SYNC_STATE` with a persisted `AssetSyncRun` model, surface sync progress, and add filters (region, type).

---

### 7.4 Assets

**Purpose** – Discover and display cloud assets (e.g., S3 buckets, EC2 instances).  

**Inputs** – Provider‑fetched asset metadata.  

**Processing** – `asset_discovery_service.py` upserts `Asset` rows; `assets.py` API returns stats.  

**Outputs** – Asset list, asset‑type breakdown charts.  

**Lifecycle** – `Not Synced → Syncing → Synced → Error`.  

**Data Model** – `Asset` (id, tenant_id, type, identifier, tags, last_seen).  

**Current UI** – List table with stats; empty state messages (`AssetCharts.tsx:143`).  

**UX Problems** – Sync action is a button that fires an API call but provides no progress feedback; missing bulk actions (tag edit, delete).  

**Classification** – *Infrastructure Security* → Table+Detail.  

**Recommended UI Model** – **Table + Detail** with sidebar showing asset metadata, and a **Sync wizard** that displays real‑time progress.

---

### 7.5 Kubernetes Security

**Purpose** – Scan Kubernetes clusters for pod‑level security findings.  

**Inputs** – Cluster definitions, pod metadata, optional scan results.  

**Processing** – `k8s_security_service.py` aggregates pod findings; `sync_pods.py` syncs pod status.  

**Outputs** – Pod list, finding counts, topology view.  

**Lifecycle** – `Empty → Syncing → Synced → Error`.  

**Data Model** – `Cluster`, `Pod`, `K8sFinding`.  

**Current UI** – Section with topology graph, tables, empty‑state messages (`KubernetesSecurity.tsx:296‑662`).  

**UX Problems** – No direct feed from external providers (e.g., Falco); topology view shows no data when sync is missing.  

**Classification** – *Container Security / K8s Security* → Graph + Table.  

**Recommended UI Model** – **Graph / Relationship View** for topology, supplemented by **Table** for detailed findings.

---

### 7.6 Threats

**Purpose** – List and manage security threats (e.g., AWS Security Hub findings).  

**Inputs** – `Threat` rows generated by scan adapters.  

**Processing** – CRUD API, status updates (resolve, suppress), tenant isolation.  

**Outputs** – Threat list, stats, detail view.  

**Lifecycle** – `New → Investigating → Resolved / Suppressed`.  

**Data Model** – `Threat` (id, tenant_id, source, severity, status, raw_data, timestamps).  

**Current UI** – Table with status badges, filter toolbar, empty state (`Threats.tsx:274,507`).  

**UX Problems** – MITRE fields may be missing; no bulk actions; resolve workflow not clearly guided.  

**Classification** – *Threat Detection* → Findings Explorer.  

**Recommended UI Model** – **Findings Explorer** with sidebar detail, bulk resolve, and risk triage workflow.

---

### 7.7 Vulnerabilities

**Purpose** – Display vulnerabilities from code‑dependency scans and external feeds.  

**Inputs** – `Vulnerability` rows (CVE, Dependabot, Security Hub).  

**Processing** – CRUD, stats, CVSS computation.  

**Outputs** – Vulnerability list, CVSS cards, fixable/unfixable counts.  

**Lifecycle** – `Open → Fixed → Dismissed`.  

**Data Model** – `Vulnerability` (id, tenant_id, cve, package, version, severity, fix_available, raw_data).  

**Current UI** – Table with filters, CVSS cards, empty state (`Vulnerabilities.tsx:1013‑1017`).  

**UX Problems** – No direct link to source repository; fix action is a placeholder.  

**Classification** – *Vulnerability Management* → Findings Explorer.  

**Recommended UI Model** – **Findings Explorer** with integrated fix guidance (link to repo/commit) and bulk remediate.

---

### 7.8 Security Posture (Score Service)

**Purpose** – Compute a weighted security score from multiple dimensions.  

**Inputs** – Aggregated counts from threat, vulnerability, compliance, asset, policy tables.  

**Processing** – `SecurityPostureService` applies weighting formulas; misconfiguration categories are derived mock data.  

**Outputs** – Overall score (0‑100), dimension scores, trend snapshots.  

**Lifecycle** – `Snapshot created → Stored → Queried`.  

**Data Model** – `SecurityPostureScore` (tenant_id, score, breakdown JSON, created_at).  

**Current UI** – KPI widgets, line chart for trend (`SecurityPosture.tsx`). Empty defaults differ per dimension.  

**UX Problems** – Inconsistent empty defaults; mock categories not labeled; no explanation of weighting.  

**Classification** – *Risk Management / Security Overview* → Dashboard.  

**Recommended UI Model** – **Risk Dashboard** with clear legends, “no data” indicators, and a *What‑this‑means* tooltip.

---

### 7.9 Remediation

**Purpose** – Create, execute, and track remediation plans for findings.  

**Inputs** – Selected findings (threats/vulns), optional playbooks.  

**Processing** – `remediation.py` stores plan, tracks worker status; cancel is a no‑op stub.  

**Outputs** – Remediation plan record, execution logs, status timeline.  

**Lifecycle** – `Planned → Running → Completed / Cancelled`.  

**Data Model** – `RemediationPlan` (id, tenant_id, steps JSON, status, created_at, logs).  

**Current UI** – Timeline view, empty state, placeholder cancel button.  

**UX Problems** – Cancel does nothing; no progress feedback; UI does not enforce step ordering.  

**Classification** – *Remediation Workspace*.  

**Recommended UI Model** – **Remediation Workspace** with Kanban‑style steps, real‑time worker status, and actionable logs.

---

### 7.10 Intelligence

**Purpose** – Aggregate external threat‑intelligence feeds (IOC, actors, techniques).  

**Inputs** – Provider APIs (unspecified), stored `IntelligenceRecord` rows.  

**Processing** – `intelligence.py` fetches, normalizes, stores records.  

**Outputs** – Feed list, record detail, sync status.  

**Lifecycle** – `Empty → Syncing → Synced`.  

**Data Model** – `IntelligenceRecord` (type, source, data, timestamps).  

**Current UI** – Tabs for IOCs, actors, malware; sync button; empty states.  

**UX Problems** – No feed data; sync may hide errors; UI does not indicate freshness.  

**Classification** – *Threat Intelligence* → Findings Explorer.  

**Recommended UI Model** – **Findings Explorer** with filter by feed, confidence score, and TTL.

---

### 7.11 Compliance

**Purpose** – Track compliance frameworks, controls, evidence, assessments.  

**Inputs** – Framework definitions, control mappings, evidence artifacts.  

**Processing** – CRUD, assessment scoring, exception handling.  

**Outputs** – Framework status, control gaps, assessment reports.  

**Lifecycle** – `Not Assessed → Assessed → Exception Applied → Closed`.  

**Data Model** – `Framework`, `Control`, `Evidence`, `Assessment`, `Exception`.  

**Current UI** – Tabbed view per framework; tables for controls/evidence; PDF export button.  

**UX Problems** – Empty states shown, but no guidance on how to add evidence; export not verified.  

**Classification** – *Compliance* → Dashboard + Table.  

**Recommended UI Model** – **Dashboard** for overall compliance score and **Table + Detail** for per‑control view.

---

### 7.12 Policies

**Purpose** – Define security policies and evaluate violations.  

**Inputs** – Policy definitions, evaluated findings.  

**Processing** – Policy evaluator seeds built‑in policies, computes violations.  

**Outputs** – Policy list, violation counts, enforcement status.  

**Lifecycle** – `Defined → Evaluated → Violated → Fixed`.  

**Data Model** – `Policy`, `PolicyViolation`.  

**Current UI** – List with stats, seed button, empty state.  

**UX Problems** – No UI for editing policy rules; violation details sparse.  

**Classification** – *Policy Management* → Configuration / Policy Workspace.  

**Recommended UI Model** – **Configuration / Policy Workspace** with rule editor, live violation preview.

---

### 7.13 Exceptions

**Purpose** – Allow users to create temporary exceptions for findings.  

**Inputs** – Target finding ID, reason, expiry.  

**Processing** – Create, revoke, list exceptions; tenant‑scoped.  

**Outputs** – Exception record, status.  

**Lifecycle** – `Active → Revoked → Expired`.  

**Data Model** – `Exception` (id, tenant_id, finding_id, reason, expires_at).  

**Current UI** – Table with create/revoke actions; empty state.  

**UX Problems** – No bulk revoke; UI shows plain list without contextual linking to the finding.  

**Classification** – *Exception Management* → Table + Detail.  

**Recommended UI Model** – **Table + Detail** with inline linking to the associated threat/vulnerability.

---

### 7.14 Governance

**Purpose** – Provide a high‑level governance overview (risk, SLA, ownership, remediation).  

**Inputs** – Aggregated data from many services.  

**Processing** – `governance_overview.py` builds a composite view.  

**Outputs** – Scores, risk heatmap, SLA metrics, ownership coverage.  

**Lifecycle** – Similar to Overview – snapshot based.  

**Data Model** – Composite – no dedicated table, just on‑the‑fly aggregation.  

**Current UI** – Chart/summary section with empty states.  

**UX Problems** – Redundant with Overview; no drill‑down links.  

**Classification** – *Security Overview* → Dashboard.  

**Recommended UI Model** – Consolidate into the **Overview Dashboard**; de‑duplicate.

---

### 7.15 Ownership

**Purpose** – Map resources (assets, clusters, repos) to owners.  

**Inputs** – Ownership assignments, resource metadata.  

**Processing** – CRUD, import/export CSV.  

**Outputs** – Ownership table, coverage stats.  

**Lifecycle** – `Empty → Imported → Updated`.  

**Data Model** – `Ownership` (resource_id, owner_id, tenant_id).  

**Current UI** – List, import/export buttons; edit action triggers a local alert placeholder.  

**UX Problems** – Edit does not persist; no validation.  

**Classification** – *Governance / Asset Ownership* → Table + Detail.  

**Recommended UI Model** – **Table + Detail** with in‑line edit modal that calls the API.

---

### 7.16 SLA Tracker

**Purpose** – Track service‑level agreement compliance for threat/vulnerability resolution.  

**Inputs** – Findings, timestamps, SLA windows (24h, 7d, 30d, 90d).  

**Processing** – `sla_service.py` calculates overdue status, aggregates.  

**Outputs** – SLA summary cards, overdue list.  

**Lifecycle** – `Synced → Overdue → Resolved`.  

**Data Model** – `FindingSLA` (finding_id, sla_window, breached_at).  

**Current UI** – Summary cards, static window values, empty state.  

**UX Problems** – Windows are hard‑coded; no ability to configure per‑tenant.  

**Classification** – *Risk Management* → Dashboard.  

**Recommended UI Model** – **Risk Dashboard** with configurable SLA windows per tenant.

---

### 7.17 Reports

**Purpose** – Generate downloadable security reports (executive, vulnerability, posture, etc.).  

**Inputs** – Aggregated data from all services.  

**Processing** – `reports_service.py` compiles templates, builds JSON/HTML; Excel branch returns error string, PDF branch absent.  

**Outputs** – Report files (JSON, Excel stub, PDF missing), download URLs.  

**Lifecycle** – `Requested → Compiled → Ready → Downloaded`.  

**Data Model** – `Report` (id, tenant_id, template, content_blob, created_at).  

**Current UI** – List of templates, create/delete actions; export buttons.  

**UX Problems** – Export formats not implemented; no schedule view.  

**Classification** – *Reporting* → Dashboard + Export.  

**Recommended UI Model** – **Dashboard** with *Generate* wizard, then **Table** of generated reports with download links.

---

### 7.18 SBOM

**Purpose** – Generate a Software Bill‑of‑Materials for repositories.  

**Inputs** – Repository source files; optional Syft binary.  

**Processing** – `sbom_service.py` parses manifests (fallback) or runs Syft; stores CycloneDX/SPDX; tries to enrich packages with version/CPE/EPSS/KEV (returns `None`). Package vulnerability lookup always returns empty.

**Outputs** – SBOM document, component list, optional vulnerability mapping.

**Lifecycle** – `Generated → Enriched → Exported`.

**Data Model** – `SBOM` (id, tenant_id, format, content_json, created_at).

**Current UI** – Tree view of components, download buttons, empty state.

**UX Problems** – Dependency tree is synthetic (all components under first); package vulnerability lookup is broken; enrichment fields are empty.

**Classification** – *Software Bill‑of‑Materials* → Graph / Relationship View.

**Recommended UI Model** – **Graph / Relationship View** that accurately shows real dependency edges; add *Enrichment* status indicator.

---

### 7.19 Security Copilot

**Purpose** – Provide LLM‑driven assistance for security questions.

**Inputs** – Conversation context (repo, findings, posture, policies).

**Processing** – `copilot_service.py` builds context, calls Anthropic API if key present; otherwise deterministic fallback.

**Outputs** – Chat messages, suggested actions.

**Lifecycle** – `Idle → Generating → Responded`.

**Data Model** – `CopilotConversation`, `CopilotMessage`.

**Current UI** – Chat pane; on failure logs error and shows empty UI.

**UX Problems** – No visible indicator of fallback vs real LLM; no evidence of retrieval or tool use.

**Classification** – *LLM‑Assisted Guidance* → Conversation Workspace.

**Recommended UI Model** – **Conversation Workspace** with explicit “Live model” badge, error handling, and ability to upvote/downvote responses.

---

## 8. Shared Security UX Patterns

| Pattern | Current Implementation | Recommended Consistency |
|---|---|---|
| **Header** – service title, status badge, primary action | Implemented per section (e.g., `Overview`, `Threats`) | Standard Header component with props: `title`, `status`, `actionButtons` |
| **Filters / Search Toolbar** | Present in many sections, but varying APIs | Unified `FilterBar` component with query param sync |
| **Loading / Empty / Error States** | Each component defines its own messages | Central `StatefulView` component handling `loading`, `empty`, `error` with consistent icons |
| **Detail Drawer / Modal** | Used in Repositories, Assets, Threats, etc. | Shared `DetailDrawer` that receives `entityType` and fetches via generic API |
| **Status Badges (Severity)** | Hard‑coded colors per service | Global `SeverityBadge` using a shared severity scale (Critical, High, Medium, Low, Info) |
| **Action Confirmation** | Inconsistent (some use `window.confirm`, others no guard) | Global `ConfirmDialog` for destructive actions |
| **Permission Visibility** | Tenant guards in API; UI often shows actions irrespective of role | Role‑aware UI hide/show via `usePermissions` hook |
| **Pagination / Infinite Scroll** | Some tables paginate, others load all | Consistent pagination component with server‑side paging |
| **Bulk Actions** | Rarely present | Add bulk action toolbar where appropriate (Threats, Vulnerabilities, Exceptions) |

---

## 9. Shared Data Models

### 9.1 Finding (Base Interface)

```
interface FindingBase {
  id: UUID;
  tenant_id: UUID;
  type: "threat" | "vulnerability" | "asset" | "intelligence";
  severity: "critical" | "high" | "medium" | "low" | "info";
  status: "new" | "investigating" | "resolved" | "suppressed";
  source: string; // provider name
  created_at: datetime;
  updated_at: datetime;
  raw_data: JSON; // provider payload
}
```
*Current* – Threat and Vulnerability tables follow this shape but are separate models.
*Proposed* – Introduce a common `FindingBase` view (SQL view or GraphQL interface) for UI components to consume.

### 9.2 Severity Scale

Current code uses strings (`critical`, `high`, `medium`, `low`, `info`). No central enum.

**Proposed** – Central `Severity` enum with color tokens and ordering; UI components reference this enum.

---

## 10. Security Center Data Flow

```
User
 │
 ▼
Security Center UI (React) – per‑service component
 │   (fetches via REST)
 ▼
API Gateway (FastAPI) – authentication, tenant guard
 │   (calls service layer)
 ▼
Service Layer – business logic, provider adapters
 │   (reads/writes DB, calls external APIs)
 ▼
Database (PostgreSQL) – tenant‑scoped tables
 │   (stores findings, assets, posture snapshots)
 ▼
External Providers (AWS, GitHub, GitLab, K8s, etc.)
```
**PROPOSED ADDITIONS** – Add **Event Bus** (e.g., Redis Pub/Sub) for real‑time scan progress; introduce **Background Worker** status persistence for scans and syncs.

---

## 11. Proposed Information Architecture

```
Security Center
│
├─ Overview (Dashboard)
│
├─ Repositories (Scanner Wizard)
│
├─ Infrastructure
│   ├─ Clusters
│   └─ Assets
│
├─ Kubernetes Security
│
├─ Threats (Findings Explorer)
│
├─ Vulnerabilities (Findings Explorer)
│
├─ Posture (Risk Dashboard)
│
├─ Remediation (Workspace)
│
├─ Intelligence (Explorer)
│
├─ Compliance (Dashboard + Table)
│
├─ Policies (Policy Workspace)
│
├─ Exceptions (Table)
│
├─ Governance (Dashboard – merged into Overview)
│
├─ Ownership (Table)
│
├─ SLA Tracker (Risk Dashboard)
│
├─ Reports (Generate Wizard + Table)
│
├─ SBOM (Graph View)
│
└─ Security Copilot (Conversation Workspace)
```

---

## 12. Current vs Proposed Comparison

| Area | Current | Proposed |
|---|---|---|
| **Purpose** | Mixed; many sections duplicate overview data. | Clear, service‑specific purpose per tab. |
| **Data** | Source‑level DB queries; many empty states. | Unified `FindingBase` view; enriched data where applicable. |
| **Layout** | Tab‑based, each section uses its own component set. | Service‑appropriate UI model (Dashboard, Explorer, Wizard, Graph, Workspace). |
| **Components** | Repeated cards/tables per service. | Shared component library (Header, FilterBar, StateView, DetailDrawer, SeverityBadge). |
| **Workflow** | No guided flow; actions are scattered. | Guided workflows (e.g., Scan Wizard → Findings Explorer → Remediation Workspace). |
| **Visualization** | Mix of charts, tables, cards; inconsistent. | Consistent visual language per UI model (risk matrix, dependency graph, timeline). |
| **States** | Loading / empty / error only. | Explicit lifecycle states (Not Configured, Running, Completed, Failed) with badges. |
| **Backend** | Almost all services have API endpoints; some workers broken. | Same APIs but with fixed defects; add background‑task status endpoints. |
| **UX** | Placeholder actions, missing progress, mock data not labeled. | Clear confirmations, progress indicators, synthetic data flagged, role‑aware visibility. |

---

## 13. Frontend Implementation Impact

| Service | Impact |
|---|---|
| Overview | Minor – replace per‑card links, use shared `SeverityBadge`. |
| Repositories | Major – replace current list with Scanner Wizard UI, add progress view. |
| Infrastructure / Assets | Minor – introduce shared `SyncProgress` component, central FilterBar. |
| Kubernetes | Minor – adopt Graph component for topology. |
| Threats / Vulnerabilities | Medium – switch to Findings Explorer UI, bulk actions, shared `FindingCard`. |
| Posture | Minor – adjust empty‑state handling, add tooltip explanations. |
| Remediation | Major – build Workspace with Kanban board, real‑time worker status. |
| Intelligence | Minor – unify table layout, add freshness indicator. |
| Compliance | Minor – add export flow, link to evidence upload UI. |
| Policies | Medium – add rule editor component, integrate with Findings Explorer. |
| Exceptions | Minor – add bulk revoke, link to finding detail.
| Governance | Remove duplicate; collapse into Overview.
| Ownership | Minor – replace alert placeholder with modal form.
| SLA Tracker | Minor – make windows configurable UI, add overdue badge.
| Reports | Major – implement Excel/PDF generation, add generation wizard.
| SBOM | Major – replace synthetic tree with true dependency graph component.
| Security Copilot | Minor – add “Live model” badge, error handling UI.

---

## 14. Backend / API Impact

| Service | Needed Change |
|---|---|
| Repository Scan | Fix `dedup_count` init; rename `RawFinding.raw` field; add scan progress endpoint. |
| SBOM | Implement package vulnerability lookup; replace synthetic tree building. |
| Reports | Implement Excel/PDF generation; add scheduled report task. |
| Remediation | Implement real worker cancellation, status updates. |
| Integration Error Handling | Replace undefined `itype` references; propagate error details. |
| Provider Syncs | Standardize success vs failure responses; add retry/backoff. |
| Ownership | Add persisted edit endpoint. |
| Policies | Expose rule editor API (create/update policy logic). |
| Intelligence | Add feed freshness timestamps; expose sync status. |
| SLA Tracker | Make SLA windows configurable per tenant. |
| All Services | Ensure all endpoints enforce tenant isolation consistently; add unit tests for IDOR. |

---

## 15. Database Impact

| Change | Reason |
|---|---|
| Add `FindingBase` view or unified table for cross‑service UI components. |
| Add `AssetSyncRun` table (status, started_at, finished_at) to replace in‑memory sync flag. |
| Add `ScanProgress` table (scan_id, step, status, message) for real‑time progress streaming. |
| Add `RemediationWorkerStatus` table (plan_id, state, logs). |
| Extend `SBOM` with `dependency_edges` table to store real dependency relationships. |
| Add `ReportExport` table to store generated file metadata (path, format). |
| Add `PolicyRule` table for granular policy definition. |
| Add `SLAWindow` table (tenant_id, window_name, duration) for configurability. |

---

## 16. Security Considerations

* **Tenant Isolation** – All API routes already filter by `tenant_id`. Verify every new endpoint (e.g., ScanProgress, ReportExport) also includes this guard.
* **Sensitive Data Masking** – `copilot_context_builder.py` already masks secret keys; ensure any new background logs (remediation, scan) also mask credentials.
* **Confirmation on Destructive Actions** – Add `ConfirmDialog` for delete/report cancel/ownership edit.
* **Audit Trails** – Ensure CRUD actions on Threat, Vulnerability, Policy, Exception, Ownership write audit entries.
* **Rate Limiting on Provider Calls** – Add back‑off and retry logic to integration services to avoid throttling.
* **Export Content‑Type Enforcement** – Set correct `Content-Type` headers for Excel (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) and PDF (`application/pdf`).

---

## 17. State & Error Handling Matrix

| Service | States (UI) | Error Handling |
|---|---|---|
| Overview | Loading → Data → Empty → Error | Show error banner with retry button. |
| Repositories | Loading → List → No Repos → Scan In‑Progress → Scan Failed | Show progress spinner; on failure display error with stack trace (masked). |
| Assets | Loading → Syncing → Synced → Empty → Error | Sync button disabled during sync; error toast on failure. |
| Kubernetes | Loading → Topology → Empty → Error | If provider auth fails, show explicit “Provider error” message. |
| Threats / Vulnerabilities | Loading → List → Empty → Error | Bulk resolve error shows per‑item toast. |
| Remediation | Planning → Running → Completed → Cancelled → Error | Cancellation confirmation; error logs displayed in timeline. |
| SBOM | Loading → Tree → Empty → Error | If dependency lookup fails, show “Enrichment unavailable” badge. |
| Reports | Loading → Template List → Generating → Ready → Error | Generation errors displayed with retry. |
| Security Copilot | Idle → Generating → Responded → Error | Show “LLM unavailable” banner if fallback used. |

---

## 18. Cross‑Service Integration Opportunities

* **FindingBase** view enables a single UI component for Threats, Vulnerabilities, and Intelligence.
* **Remediation Workspace** can consume findings from Threats, Vulnerabilities, and SBOM packages.
* **Posture Dashboard** can pull live counts from the FindingBase aggregation.
* **Report Generator** can use the same aggregation layer as the Overview dashboard.
* **SLA Tracker** can automatically mark overdue findings by querying the FindingBase status.

---

## 19. Implementation Dependencies

| Dependency | Dependent Services |
|---|---|
| Fixed scan worker (`run_scan.py`) | Repositories, Threats, Vulnerabilities, Posture, SBOM. |
| SBOM vulnerability lookup implementation | SBOM, Vulnerabilities, Reports. |
| Real provider credentials (AWS, GitHub, GitLab, K8s) | Assets, Infrastructure, Threats, Vulnerabilities, Intelligence, Governance. |
| Report export implementation (Excel/PDF) | Reports, Governance, Compliance. |
| Remediation worker signaling | Remediation, SLA Tracker. |
| Unified `FindingBase` view | Threats, Vulnerabilities, Intelligence, Dashboard components. |

---

## 20. Recommended Implementation Sequence

1. **Core Backend Fixes** – Repair `run_scan.py` and `scan_engine.py`; implement `ScanProgress` endpoint.
2. **SBOM Enhancements** – Implement real package vulnerability lookup and proper dependency graph storage.
3. **Unified Finding Model** – Add `FindingBase` view and shared UI components.
4. **Remediation Workspace** – Build worker status persistence, UI Kanban view.
5. **Scanner Wizard UI** – Replace current list with step‑by‑step wizard using new progress API.
6. **Report Export** – Implement Excel/PDF generation and scheduling.
7. **Ownership Edit Persistence** – Replace alert placeholder with API call and modal UI.
8. **Policy Rule Editor** – Add rule editor component and backend.
9. **SLA Configurable Windows** – Add DB model and UI controls.
10. **Security Copilot Production Integration** – Add proper Anthropic key handling and UI indicator.

---

## 21. Open Questions / Unknowns

* What are the precise SLA window values per tenant (are they configurable per contract)?
* Are there any additional external providers (e.g., Falco for K8s) that should be integrated?
* What is the intended lifecycle for report scheduling – is a Celery beat task expected?
* Should the SBOM dependency tree be visualized as a directed acyclic graph or simple hierarchy?
* Is there a requirement for exporting findings in STIX/TAXII format?

---

## 22. Final System Design Summary

The Security Center should evolve from a **tab‑centric collection of loosely connected sections** to a **service‑oriented console** where each security capability is presented using the UI model that best matches its data and user workflow. The redesign hinges on fixing critical backend defects (scan worker, SBOM lookup), establishing shared data abstractions (`FindingBase`), and providing consistent UI patterns (Header, FilterBar, StateView, DetailDrawer, SeverityBadge). By following the phased implementation plan, the product will gain:

* Reliable scan results and real‑time progress feedback.
* Accurate SBOMs with enriched vulnerability data.
* A unified findings explorer that powers threat, vulnerability, and intelligence views.
* A dedicated remediation workspace that guides users from detection to fix.
* Consistent, role‑aware UX with clear states, confirmations, and error handling.
* Extensible architecture for future providers and reporting formats.

Once these foundations are in place, the Security Center will be ready for a user‑friendly redesign that supports both high‑level posture monitoring and deep investigative work without sacrificing security, auditability, or multi‑tenant isolation.

---

*Report generated by Claude Code on 2026‑09‑29.*