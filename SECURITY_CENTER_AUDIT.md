# Security Center / DevSecOps Center Verification Audit

**Audit date:** 2026-09-24  
**Scope:** Current repository state only  
**Method:** Read-only source tracing plus unauthenticated runtime checks  
**Constraint honored:** No features, business logic, architecture, mock data, or demo data were added or changed.

## Evidence standard and limitations

This audit follows each feature from UI to API, service, persistence, provider, returned data, and UI handling. A rendered screen, registered route, or HTTP 200 response is not treated as proof of end-to-end functionality.

The development database currently contains zero rows for tenants, users, integrations, repositories, scans, threats, vulnerabilities, assets, Kubernetes scans/findings, SBOMs, posture snapshots, reports, Copilot conversations, exceptions, and remediation plans. Consequently:

- Tenant isolation and empty-state behavior can be inspected in code and partially checked through unauthenticated requests.
- Provider calls, populated responses, write actions, repeated scans, deduplication, and populated-tenant calculations cannot be runtime-verified in this environment.
- External provider permissions, credentials, network behavior, Celery execution, and deployment configuration remain unverified.

Runtime checks against the running backend produced:

```text
/api/v1/health                         200 {"status":"ok", ...}
Security Center protected endpoints    401 {"success":false,"message":"Authentication required",...}
```

This confirms the process is up and protected endpoints are not anonymously readable. It does not confirm authenticated feature behavior.

## A. Executive Summary

### Overall conclusion

The project contains a substantial real implementation: tenant-aware API routes, database-backed models, scanner adapters, AWS/GitHub/GitLab/Kubernetes provider clients, posture aggregation, report compilation, SBOM persistence, policy/exception/remediation workflows, and empty-state-aware UI components.

It is not currently evidence-qualified as a working Security Center product. The most serious finding is that the repository scan worker has a deterministic failure before successful persistence:

1. `dedup_count` is used for threat deduplication before initialization in `backend/app/tasks/run_scan.py:201-209`; initialization occurs only at `:213`.
2. If any non-CVE finding is present, `ResultAdapter.to_threats()` reads `f.raw_data` at `backend/app/services/scan_engine.py:1066`, but `RawFinding` defines the field as `raw` at `:38-51`.

The first defect can fail even a scan with no findings. The second fails scans that produce a threat finding. The exception handler marks the scan failed at `backend/app/tasks/run_scan.py:360-375`. Therefore repository scanning is classified **BROKEN**, not merely unverified.

### High-confidence classifications

- **REAL at source level:** Authentication dependency coverage on the inspected Security Center routes; tenant-scoped list/detail queries in many services; database-backed CRUD for threats, vulnerabilities, assets, policies, exceptions, ownership, SLA, reports, SBOM metadata, and Copilot conversations; provider sync orchestration.
- **PARTIAL:** Most UI sections; AWS/GitHub/GitLab/Kubernetes integration flows; posture and score dashboards; compliance, remediation, intelligence, ownership, SLA, and report workflows; SBOM generation; Copilot.
- **BROKEN:** Repository scan completion/persistence path; Excel report export; SBOM package vulnerability lookup; parts of integration error handling; several advertised provider/security feeds.
- **MOCK/FAKE:** Copilot deterministic fallback is explicitly synthetic response logic; Security Posture misconfiguration categories are explicitly described as mock/derived categories; SBOM dependency tree is synthetic rather than parsed from dependency relationships.
- **STUB:** Trivy/Semgrep integration `sync()` paths; Kubernetes remediation cancel hook; ownership UI edit alert; Excel export placeholder; some report template fallback behavior.
- **UNVERIFIED:** Any populated-tenant end-to-end workflow, external provider synchronization, Celery runtime task execution, authenticated UI data rendering, concurrent uniqueness behavior, and production/deployment behavior.

## B. Feature-by-Feature Verification Matrix

### B1. Overview

| Item | Evidence |
|---|---|
| UI | `artifacts/uniops/src/pages/SecurityCenter/sections/Overview.tsx:1` re-exports `sections/overview/index.tsx`. |
| API | `overview/index.tsx:152-164` requests posture summary/history, threat and vulnerability stats, compliance, repositories/risk, assets, clusters, score, scan history, critical vulnerabilities, and exception stats. |
| Services/models | Routes map to posture, threat, vulnerability, compliance, repository, asset, cluster, scan, and exception data. |
| External providers | None directly; data depends on scanner and integration feeds. |
| Data reality | KPI collections and scores are normalized/derived at `overview/index.tsx:167-243`; zeros/defaults are used at `:222-233`. |
| Empty/error handling | Child components have empty states at `OverviewFindings.tsx:68-69`, `OverviewCompliance.tsx:170`, `OverviewInfra.tsx:104-126`, `OverviewCharts.tsx:374-378`, and `OverviewActivity.tsx:125`. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** The UI is API-driven, but no populated tenant exists and upstream repository scans are broken. |

### B2. Repositories and repository scanning

| Item | Evidence |
|---|---|
| UI | `sections/repositories/index.tsx`; drawer in `sections/repositories/RepoDrawer.tsx`. |
| API | `/security/repos`, `/repos/risk`, `/security/scan-history?limit=30` at `repositories/index.tsx:171-173`; scan detail `/security/scan/${scanId}` at `:294`. |
| Persistence | `Scan` and `Repository` models in `backend/app/models/scan.py:7-77`; scan task persists lifecycle, counts, score, raw results, and AI fields. |
| Scanner pipeline | `scan_engine.py:1387-1459` runs SAST, secrets, dependency, optional container, and optional CI/CD scanners. |
| Critical defect | Threat `dedup_count` use-before-initialization at `run_scan.py:201-209`; `RawFinding.raw` versus `f.raw_data` mismatch at `scan_engine.py:38-51,1066`. |
| UI limitation | Repository drawer has no scanner/security/scan-history data and displays no-data scores at `RepoDrawer.tsx:112,230,468-471,649,701`. |
| Status | **BROKEN** for scan completion and **PARTIAL** for repository browsing. Authenticated populated behavior is otherwise **UNVERIFIED**. |

### B3. Infrastructure overview

| Item | Evidence |
|---|---|
| UI/API | `sections/infrastructure/index.tsx:114-122` requests clusters, assets, asset sync status, posture, vulnerability stats, costs, alerts, and Kubernetes pods. |
| Data handling | Arrays are normalized to empty arrays at `:125-136`. |
| Persistence/providers | Uses cluster, asset, posture, vulnerability, cost, alert, and pod APIs; provider data is indirect. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** The UI is API-driven and has no-data states, but provider-fed values and authenticated rendering were not exercised. |

### B4. Assets

| Item | Evidence |
|---|---|
| UI/API | `sections/assets/index.tsx:363-365` requests `/assets`, `/assets/stats`, and `/assets/sync/status`; `AssetDrawer.tsx:94` loads details. |
| Persistence | `backend/app/api/v1/endpoints/assets.py:40-124,215-261,327-...` queries tenant-scoped `Asset` rows. |
| Sync | `assets.py:286-320` queues background sync with in-memory `_SYNC_STATE`; `asset_discovery_service.py:70-122` dispatches provider discovery. |
| Actions | Drawer uses `apiPost` actions; exact provider-side effects require authenticated populated testing. |
| Empty handling | No high-risk/recent assets, no discovered assets, chart no-data, and missing relationship/finding breakdown states are explicit in `index.tsx:199,250,290`, `AssetCharts.tsx:143`, and `AssetDrawer.tsx:285,373`. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** Database-backed and tenant-scoped, but the background sync is not verified against a connected provider; sync state is process-local. |

### B5. Kubernetes Security

| Item | Evidence |
|---|---|
| UI/API | `KubernetesSecurity.tsx:794,850-904` requests clusters, pod stats, K8s finding stats, topology resources, pods, findings, and scan history. |
| Service | `k8s_security_service.py:795-911` lists tenant clusters/findings, computes stats, and creates tenant/cluster-scoped scans; `:950-1054` executes and persists findings/history. |
| Provider | Kubernetes client exists at `backend/app/integrations/kubernetes/client.py:131-170,571-575`; pod sync persists operational rows in `sync_pods.py:110-160`. |
| Direct security feed | K8s pod sync does not directly insert Threat/Vulnerability/Compliance records; no direct provider-to-Security-Center finding feed was demonstrated. |
| Empty handling | Topology, resource, findings, cluster, namespace, and node no-data states at `KubernetesSecurity.tsx:296,476,515,541,567,601,662-671,1294-1295,1470-1471`. |
| Status | **PARTIAL / EXTERNAL RUNTIME UNVERIFIED.** K8s scan code is real, but provider execution and direct feed coverage are not verified. |

### B6. Threats

| Item | Evidence |
|---|---|
| UI/API | `Threats.tsx:698-701` requests `/threats` and `/threats/stats`; detail `/threats/{id}` at `:331`. |
| API/service | `backend/app/api/v1/endpoints/threats.py:14-69` provides list, stats, detail, update, resolve, and suppress actions. |
| Tenant isolation | List/stats/detail/update pass `tenant_id`; admin actions use `current_user["tenant_id"]` at `threats.py:69-102`. |
| Data sources | Scan adapter and AWS Security Hub can create threats; scan path currently fails before successful persistence. |
| UI limitations | MITRE/raw fields can be missing at `Threats.tsx:274,507`; empty active/filter states at `:956-960`. |
| Status | **PARTIAL.** CRUD/query code is real, but populated data, scan-produced threats, and AWS feed runtime are **UNVERIFIED**; scan-produced threat creation is currently blocked by the scan worker defects. |

### B7. Vulnerabilities

| Item | Evidence |
|---|---|
| UI/API | `Vulnerabilities.tsx:745-746` requests list/stats; detail `/vulnerabilities/{id}` at `:251`. |
| API/service | Vulnerability routes and service provide tenant-scoped queries/actions; GitHub Dependabot and AWS Security Hub have insertion paths. |
| Derived data | Fixable/no-fix and CVSS cards are derived at `Vulnerabilities.tsx:775-777,854-867`. |
| Empty/error handling | No-vulnerability/filter states at `:1013-1017`; external references/fix fallback at `:225,355,505`. |
| Feed limitation | GitHub Dependabot is wired; GitHub CodeQL client exists but is not called by the pipeline task; GitLab pipeline sync does not insert vulnerabilities. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** Database-backed query paths are real; complete scanner/provider coverage is not. |

### B8. Security posture and scores

| Item | Evidence |
|---|---|
| UI/API | `SecurityPosture.tsx:400-405` requests dashboard, summary, asset stats, and compliance score; snapshot POST at `:469`. |
| Service | `SecurityPostureService` calculates threat, vulnerability, compliance, asset, policy, and weighted overall scores from DB aggregates. |
| Empty defaults | Threat/vulnerability/asset dimensions use different defaults; compliance and policy defaults are zero. No-data semantics therefore differ by dimension. |
| History | Historical trend requires persisted posture snapshots; `security_posture.py:26-36` reads history and `:53-62` records snapshots. |
| Mock-derived behavior | `SecurityPosture.tsx:484-490` explicitly calls misconfiguration categories “mock categories (derived from real risk counts)”; risk dimensions are derived at `:534`. |
| Status | **PARTIAL.** Formulas are source-verifiable, but populated score outputs, trend records, and interpretation of empty data are not runtime-verified. Misconfiguration category display is **MOCK/DERIVED**, not an independent finding feed. |

### B9. Remediation

| Item | Evidence |
|---|---|
| UI/API | `Remediation.tsx:627-629` requests plans, summary, and worker status; timeline/history at `:325-326`; action calls are imported at `:11`. |
| API | `remediation.py:57-351` provides summary, plans, propose, start, cancel, rollback, execute, detail, and history routes. All inspected routes use `get_tenant_id` and tenant predicates. |
| Actionability | Plan records and controller calls exist, but `cancel_execution` is described as a worker-signal hook and is a no-op today (`remediation.py:272`). |
| UI empty handling | Plans/workers default empty at `Remediation.tsx:640,644`; empty actions/history/required-input states at `:413,509,545,583,594,757-760`. |
| Status | **PARTIAL / STUBBED.** Proposal and persistence paths are real; actual execution, cancellation, rollback side effects, and worker behavior are not verified. |

### B10. Intelligence

| Item | Evidence |
|---|---|
| UI/API | `Intelligence.tsx:547,750,854,942,1012,1087-1105` requests records, IOCs, actors, malware, techniques, summary, feeds, and feed sync. |
| Backend | `intelligence.py:20-536` exposes list, sync, health, providers, lookup, enriched finding, recommendations, and canonical CVE/package routes. |
| Persistence/providers | Provider metadata and intelligence records are queried, but no connected feeds exist in the database. |
| Empty handling | Provider, record, IOC, actor, malware, ATT&CK, and feed empty states are explicit. |
| Status | **PARTIAL / UNVERIFIED.** API surface and DB queries exist; external feed ingestion, enrichment quality, and sync behavior are unverified. |

### B11. Compliance

| Item | Evidence |
|---|---|
| UI/API | `Compliance.tsx:1810-1812` loads summary/frameworks; tabs request controls, evidence, resources, assessments, exceptions, policy mapping, and timeline at `:1013,1173,1269,1361,1441,1505,1705`. |
| Persistence | Compliance routes/services query tenant-scoped framework/control/evidence/assessment data. |
| Export | PDF export is requested at `Compliance.tsx:269`; actual content/authenticated download was not exercised. |
| Empty handling | Each tab unwraps data to arrays and has explicit no-data states at `:1014,1174,1270,1362,1442,1506,1706` and `:837,1083,1202,1302,1383,1455-1457,1558,1755`. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** The UI and route structure are real, but no framework/control/evidence data or external compliance feed is present. |

### B12. Policies

| Item | Evidence |
|---|---|
| UI/API | `Policies.tsx:934-937` loads policies, stats, violations, and exception stats; create/seed actions at `:698,952`; patch/delete at `:195,259,788`. |
| API | `security_policies.py:25-169` supports list/create/stats/seed/violations/summary/detail/update/enforcement/delete with security read/write dependencies and tenant predicates. |
| Evaluation | Seeded built-in policies call `evaluator.seed_builtin_policies`; policy violation routes call evaluator summary. |
| Empty handling | No rules, violations, exceptions, and policy-match states at `Policies.tsx:370,403,435,528,606,799`. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** CRUD/evaluator paths are real, but no seeded/evaluated populated tenant exists. |

### B13. Exceptions

| Item | Evidence |
|---|---|
| UI/API | `Exceptions.tsx:879-880` lists/stats; create/review/revoke at `:210,659,741`. |
| Tenant/auth | `security_exceptions.py:20-129` uses security read/write/compliance dependencies and passes tenant IDs; revoke explicitly supplies tenant ID. |
| Data handling | Search/filter/export/summary are locally derived at `Exceptions.tsx:482-496,895-929`; list defaults to empty at `:883`. |
| UI limitations | Missing compensating controls/expiry states at `:115,375`. |
| Status | **REAL at source level / RUNTIME UNVERIFIED.** CRUD and tenant guard evidence is strong; review/revoke side effects and populated behavior were not exercised. |

### B14. Governance

| Item | Evidence |
|---|---|
| UI/API | `GovernanceOverview.tsx:380` requests `/governance/overview`; export at `:447`. |
| Backend | `governance_overview.py:17-250` calls tenant-scoped service builders for scores, risk, health, ownership, SLA, remediation, compliance, policy, threats, timeline, and business impact. |
| Empty handling | Arrays/default objects at `GovernanceOverview.tsx:394-397,428-437`; no-data indicators/events at `:321,330,649,807,869`. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** Aggregation is database-backed, but the empty development database prevents verification of meaningful governance output. |

### B15. Ownership

| Item | Evidence |
|---|---|
| UI/API | `Ownership.tsx:316-319` requests list/summary/coverage/resource types; import/export at `:381,403`. |
| Backend | `ownership.py:28-368` provides tenant-scoped list, detail, profile, update, bulk assignment, import, export, audit, defaults, and type metadata routes. |
| Service | `ownership_service.py:74-101,315-357,432-598,707-771` consistently includes tenant predicates while resolving resources and findings. |
| UI stub | Edit action is a local alert placeholder at `Ownership.tsx:1079`; it is not a persisted edit flow. |
| Status | **PARTIAL.** API/service functionality is real; the visible edit action is **STUB**, and populated ownership/coverage/export behavior is unverified. |

### B16. SLA tracker

| Item | Evidence |
|---|---|
| UI/API | `SLATracker.tsx:71-89` loads summary/findings and POSTs sync; due-soon is locally filtered at `:80-86`. |
| Service | `sla_service.py:24-234` creates/syncs FindingSLA records from tenant-scoped threats and vulnerabilities, refreshes overdue records, and computes summary. |
| Static values | SLA windows 24h/7d/30d/90d are UI constants at `SLATracker.tsx:23-28`; they are not tenant/provider-derived. |
| Status | **PARTIAL / RUNTIME UNVERIFIED.** DB-backed SLA sync exists, but no finding rows exist and static windows may not represent configurable policy. |

### B17. Reports

| Item | Evidence |
|---|---|
| UI/API | `Reports.tsx:561-562` lists/templates; create/delete/regenerate/download/email at `:180,363,379,597,609`. |
| Service | `reports_service.py:53-130` persists reports; `_compile_report` at `:366-601` aggregates tenant-scoped tables for several templates. |
| Template coverage | Dedicated compilation exists for executive, vulnerability, threat intelligence, compliance, posture, Kubernetes, SBOM, and remediation templates (`:406-581`). Unknown/unhandled templates fall through to a generic default at `:583-590`. |
| Export defect | Excel branch is explicitly a JSON placeholder at `reports_service.py:714-716`. PDF is advertised by API/UI but no PDF branch is present in `_build_export_content` (`:676-721`). |
| Scheduling | Schedule fields are persisted, but no report scheduling task was found in Celery task/schedule search. Actual recurring execution is therefore unverified and likely incomplete. |
| Status | **PARTIAL / BROKEN EXPORT SUBFEATURE.** DB compilation is real; Excel is **STUB**, PDF support is not evidenced, and recurring execution is **UNVERIFIED**. |

### B18. SBOM

| Item | Evidence |
|---|---|
| UI/API | `SBOM.tsx:267-326` lists/summarizes, loads dependency tree/package details, and downloads exports. |
| Persistence | `sbom.py:23-164` is tenant-scoped; `sbom_service.py:370-...` stores CycloneDX and SPDX content in PostgreSQL. |
| Generation | Syft is used only when installed (`sbom_service.py:214-220,387-...`); runtime inspection found Syft absent. Fallback parses selected manifests at `:40-150`. |
| Dependency tree | `sbom_service.py:302-310` makes the first component the root and attaches every other component as its child; this is synthetic and not a dependency graph. |
| Package metadata | Enterprise package response sets `latest_version`, CPE, SHA256, EPSS, and KEV to `None`/false in `sbom.py:237-255`; KEV explicitly requires an un-ingested external feed at `:227`. |
| Broken lookup | `_get_vulnerabilities_for_package` constructs SQL at `sbom_service.py:324-357` but returns `[]` unconditionally at `:359`. |
| Status | **PARTIAL / BROKEN PACKAGE LOOKUP.** SBOM records and fallback parsing are real, but dependency relationships, enrichment, and package-level vulnerability detail are not fully implemented. |

### B19. Security Copilot

| Item | Evidence |
|---|---|
| UI/API | `SecurityCopilot.tsx:70,79,88,116` uses conversation list/messages/create/chat routes. Failed loads only log and leave empty UI at `:70-81`. |
| Tenant isolation | `copilot_service.py:39-71,86-107` scopes conversations/messages/repo/scan/finding context to tenant and user where applicable. |
| Context | `copilot_context_builder.py:23-43` gathers repository, scan, finding, posture, and active policy context; `:154-168` recursively masks secret/token/key/password/auth keys. |
| LLM reality | Anthropic HTTP call is real when `ANTHROPIC_API_KEY` exists (`copilot_service.py:186-226`), but no such provider/key was verified. The fallback at `:228-253` is deterministic keyword-based text with model `"fallback"`. |
| Missing capabilities | No vector/RAG retrieval or tool/function calling was found. UI imports policies/exceptions but does not call them (`SecurityCopilot.tsx:20`). |
| Status | **PARTIAL / UNVERIFIED.** Persistence/context are real; live LLM behavior is unverified; no-key behavior is explicitly **MOCK/FAKE FALLBACK**, not an AI provider. |

## C. Integration Verification Matrix

| Provider/capability | Evidence and status |
|---|---|
| GitHub | Schema allowlist and client at `integration.py:6-11`, `integration_service.py:666-687`, and `integrations/github/client.py:17-29,46-85,381-386`. Repository/pipeline sync is real; Dependabot feeds vulnerabilities. CodeQL client exists at `:257-275` but is not called by pipeline sync. **PARTIAL / external runtime unverified.** |
| GitLab | Client and generic integration path are real. Pipeline sync is real, but it returns no demonstrated vulnerability feed. **PARTIAL / external runtime unverified.** |
| AWS | AWS client, STS test, Security Hub, cost, asset, and posture orchestration are real. `integrations.py:347-386,424-464` triggers costs/assets/Security Hub/posture. **REAL orchestration / external runtime unverified.** |
| Kubernetes | Client/test/pod sync/cluster scan paths exist. Credential update auto-test omission is present in `integrations.py:194-242`. **PARTIAL / external runtime unverified.** |
| Stripe | Client exists (`integrations/stripe/client.py:41-48,147-169`) and factory exposure exists, but no Security Center feed was found. **UNVERIFIED for Security Center.** |
| Slack/Prometheus/Loki/Semgrep/Trivy | Client code exists, but these are absent from the schema allowlist/factory or have empty sync paths (`integration_service.py:666-687`; Trivy `:42-66`; Semgrep `:6-15`). **PARTIAL/STUB/UNVERIFIED.** |
| Create/list/get/update/test | Integration list/get are tenant-scoped (`integrations.py:45-69`, `integration_service.py:80-109`). Create commits and queues background test/sync (`integrations.py:76-95`). Explicit test has provider-specific branches (`integration_service.py:299-452`). **REAL source path / runtime unverified.** |
| Duplicate prevention | Application singleton merge policy at `integration_service.py:115-176`; non-singleton name/type conflict at `:178-200`; repo upsert at `:495-504,573-613`. Database-level uniqueness/concurrent race behavior is **UNVERIFIED**. |
| Disconnect | Endpoint performs hard delete (`integrations.py:249-258`). Cleanup covers integration/pipeline rows and Git repository vulnerabilities/scans but not AWS findings/compliance/cost/assets/pods. Provider-side credential revocation is absent. **PARTIAL.** |
| Credential security | API schemas omit credentials (`schemas/integration.py:58-77`); sensitive fields are encrypted in normal operation (`integration_service.py:51-65,133-220`). Encryption failure stores plaintext fallback at `:619-640`; K8s/p_asset tasks decrypt indiscriminately (`sync_pods.py:78-86`, `asset_discovery_service.py:36-44`). **PARTIAL.** |
| Retry/error behavior | Celery retries exist in sync tasks, but core clients often make one request or convert failures to empty lists (`github/client.py:46-79`, `gitlab/client.py:57-83`, `aws/cost_explorer.py:53-99`, `aws/security_hub.py:24-40`). Undefined `itype` branches exist at `integration_service.py:477-481,549-568`. **PARTIAL/BROKEN error paths.** |

## D. Real Data / Mock Data Findings

### Real database-backed data paths

- Threats, vulnerabilities, repositories, scans, assets, clusters, K8s findings/scans, compliance, policies, exceptions, reports, SBOMs, posture scores, ownership, SLA, remediation, intelligence, and Copilot conversations all have SQLAlchemy models or tenant-scoped database queries.
- AWS Security Hub mappings create Threat, Vulnerability, and Compliance rows in `backend/app/integrations/aws/security_hub.py` and `backend/app/tasks/sync_security.py`.
- GitHub Dependabot mapping creates Vulnerability rows in `backend/app/tasks/sync_pipelines.py:133-183`.
- Asset discovery and K8s pod sync have persistent upsert paths.

### Explicit mock, fallback, synthetic, or placeholder behavior

1. **Scanner fallback:** real binaries are used when present, but several scanner paths fall back to regex/static lint or empty results when a tool is absent. Syft is absent in this runtime.
2. **Copilot fallback:** deterministic keyword advice in `copilot_service.py:228-253`; response metadata is `"model": "fallback"`.
3. **Posture misconfiguration categories:** explicitly marked “mock categories (derived from real risk counts)” at `SecurityPosture.tsx:484-490`.
4. **SBOM fallback:** direct manifest parsing is a real fallback but not equivalent to Syft; only selected manifest files are parsed.
5. **SBOM dependency tree:** all components after the first are attached to the first component at `sbom_service.py:302-310`.
6. **SBOM enrichment:** latest version/CPE/SHA256/EPSS are null and KEV false in `endpoints/sbom.py:237-255`.
7. **SBOM vulnerability lookup:** SQL is built then discarded by `return []` at `sbom_service.py:324-359`.
8. **Reports Excel:** JSON error payload returned from the Excel branch at `reports_service.py:714-716`.
9. **Ownership edit:** UI alert placeholder at `Ownership.tsx:1079`.
10. **Remediation cancel:** documented no-op worker signal at `remediation.py:272`.

No hardcoded demo threat/vulnerability/asset datasets were found in the inspected Security Center section implementations. The fallbacks above are nevertheless not proof of production functionality.

## E. Security Scanner Verification

### Scanner inventory

Runtime inspection found Semgrep, Trivy, Gitleaks, Bandit, pip-audit, npm, and Docker binaries. Syft was not installed.

The scan engine runs SAST, secrets, and dependency scanners in parallel at `scan_engine.py:1400-1418`, and conditionally runs container and CI/CD scanners at `:1420-1448`. Exceptions are converted into per-scanner `"failed"` status rather than aborting immediately.

### Scan lifecycle

`run_scan.py` creates/updates queued, cloning, scanning, analyzing, completed, and failed statuses, uses Redis/DB locking, persists scanner status/counts/results, writes findings, calculates score, invokes AI analysis, and emits events. The lifecycle is real in design.

### Blocking defects

| Defect | Evidence | Effect |
|---|---|---|
| Threat dedup counter uninitialized | `run_scan.py:201-209` uses `dedup_count`; initialization is only at `:213`. | Any scan reaching threat logging can raise `UnboundLocalError`, including a scan with zero threats. |
| RawFinding field mismatch | `RawFinding` declares `raw` at `scan_engine.py:38-51`; adapter reads `f.raw_data` at `:1066`. | Any non-CVE finding reaching `to_threats()` raises `AttributeError`. |
| No successful runtime scan | Development DB has no repositories/scans and no credentials. | End-to-end clone, scanner execution, persistence, dedup, SBOM, and score remain unverified even aside from static defects. |

### Scanner status

**BROKEN** for the normal repository scan completion path until the two deterministic defects are corrected and retested. Scanner binary presence alone does not change this classification.

## F. Score Calculation Verification

### Verified source behavior

`SecurityPostureService` calculates separate threat, vulnerability, compliance, asset, policy, and weighted overall scores from database aggregates. Repository scan scores use `ScoreCalculator.compute(result.findings)` in `run_scan.py:225-230`.

The report risk score independently starts at 100 and subtracts capped penalties for open/critical threats and vulnerabilities in `reports_service.py:636-644`.

### Findings

- Score sources are database-backed at source level, not fixed demo numbers.
- Empty defaults are inconsistent: some dimensions use 100-style “no findings” semantics while compliance and policy use 0. The audit cannot confirm whether this is intentional or correctly presented.
- Historical trend depends on persisted `SecurityPostureScore` rows; no snapshots exist.
- Overview and posture UIs derive/normalize score values locally, so UI values can be present even when the underlying dataset is empty.
- Misconfiguration category values in the posture UI are derived/mock categories, not independently scanned controls.

### Score status

**PARTIAL / UNVERIFIED.** Formula code exists and uses real aggregates, but no populated tenant was available to validate inputs, boundaries, weighting, trend behavior, or UI interpretation.

## G. Multi-Tenant Isolation Verification

### Positive evidence

- Protected endpoints use `TenantID`, `CurrentUser`, or role-specific dependencies.
- Threat list/stats/detail/update and admin actions pass tenant IDs (`threats.py:14-102`).
- Asset list/stats/graph/detail use `Asset.tenant_id == tenant_id` (`assets.py:40-261,327-...`).
- SBOM endpoints pass tenant ID through every metadata/content/components/package/tree/export operation (`endpoints/sbom.py:23-180`).
- Reports list/get/delete/regenerate use tenant IDs (`reports.py:17-131`; `reports_service.py:64,93-104`).
- Copilot conversations/messages/context use tenant predicates (`copilot_service.py:39-107`; `copilot_context_builder.py:49-75,92-147`).
- Ownership service includes tenant predicates for mappings, findings, resource lookups, and audit logs.
- Exceptions specifically pass tenant ID into revoke, addressing the IDOR issue documented in project memory.
- Integration get/update/test paths use `_assert_tenant` or current-user tenant checks.

### Risks and unverified areas

- Some service methods accept optional tenant IDs; safety depends on every caller passing the tenant.
- Concurrency safety of application-level duplicate prevention is not DB-verified.
- AWS vulnerability dedup by tenant/CVE can merge unrelated targets (`sync_security.py:99-128`).
- Copilot repository risk lookup uses `repo_id` without a visible tenant predicate in `copilot_context_builder.py:56-58` after the repository itself is tenant-checked. This should be reviewed as a defense-in-depth issue.
- No two-tenant authenticated test data exists, so cross-tenant negative tests were not executed.

### Isolation status

**PARTIAL / SOURCE-VERIFIED, RUNTIME UNVERIFIED.** The inspected routes show substantial tenant filtering, but a strict isolation claim requires populated two-tenant tests and review of every ID-addressed endpoint.

## H. Critical Bugs

### Critical

1. **Repository scan worker fails on `dedup_count`**
   - `backend/app/tasks/run_scan.py:201-209` uses the variable before `:213`.
   - This can fail scans with no threat findings as soon as the threat log is reached.
   - The exception handler marks the scan failed at `:360-375`.

2. **Threat adapter reads a nonexistent `RawFinding.raw_data`**
   - `backend/app/services/scan_engine.py:38-51` defines `raw`.
   - `to_threats()` reads `f.raw_data` at `:1066`.
   - Any finding without a CVE can fail the persistence stage.

3. **SBOM package vulnerability lookup always returns empty**
   - SQL is constructed at `backend/app/services/sbom_service.py:324-357`.
   - `return []` at `:359` discards the query.
   - Package details cannot report the intended vulnerability data through that path.

4. **Excel report export is not implemented**
   - `backend/app/services/reports_service.py:714-716` returns a JSON error string instead of an Excel document.

### High

5. **Integration error branches reference undefined `itype`**
   - `backend/app/services/integration_service.py:477-481,549-568`.
   - A provider authentication error can trigger a secondary `NameError` instead of the intended status/message.

6. **Provider failures can become empty success-like results**
   - GitLab/AWS clients often catch exceptions and return empty lists (`gitlab/client.py:57-83`, `aws/cost_explorer.py:53-99`, `aws/security_hub.py:24-40`).
   - Sync tasks can then commit/advance state without clearly distinguishing “no data” from “provider failed.”

7. **Disconnected integration cleanup is incomplete**
   - Hard delete removes selected integration-linked rows but leaves AWS findings, compliance, costs, assets, pods, and related records.

## I. Missing Implementations

- Correct and test the scan worker persistence path.
- Implement actual Excel export and determine whether PDF is supported; the current service does not evidence a PDF branch.
- Complete SBOM package vulnerability query execution.
- Parse real dependency relationships rather than attaching all components under the first component.
- Add external enrichment for latest versions, CPE, SHA256, EPSS, and KEV or label those fields as unavailable.
- Add CodeQL pipeline ingestion if it is advertised as a GitHub security feed.
- Add GitLab security finding ingestion if GitLab integration is expected to populate vulnerabilities/threats.
- Decide and implement direct Kubernetes security finding ingestion if the K8s security UI is expected to represent provider findings rather than only local scans.
- Replace or explicitly label posture misconfiguration mock categories.
- Implement remediation cancellation worker signaling and verify rollback/execute side effects.
- Implement ownership edit action rather than a local alert.
- Implement recurring report execution and email delivery end to end; persistence alone is not scheduling.
- Add real provider integration registration or remove unreachable client code for unsupported providers.
- Replace plaintext credential fallback on encryption failure with an explicit failure path.
- Add HTTP retry/backoff and unambiguous sync-failure state handling.

## J. Architecture Problems

1. **Multiple overlapping report models/services**
   - `reports_service.py` uses `Report`; it also imports a legacy `SecurityReport`.
   - This creates ambiguity about the authoritative report lifecycle.

2. **Process-local background state**
   - Asset sync status uses in-memory `_SYNC_STATE` in `assets.py`; multiple backend workers would not share status.

3. **Source-level provider registry drift**
   - Client modules exist for providers absent from schema/factory, while client availability is not equivalent to reachable integration functionality.

4. **Silent fallback semantics**
   - Tool absence, provider failures, and missing enrichment can collapse into empty arrays/null fields. Consumers cannot always distinguish “no findings” from “scanner/provider unavailable.”

5. **Mixed score semantics**
   - Different no-data defaults and independent score formulas are used across posture, reports, repository scans, and UI-derived metrics.

6. **Synthetic representations presented beside real data**
   - Mock-derived posture categories, synthetic SBOM dependency trees, and deterministic Copilot fallback responses are not consistently surfaced as limited-confidence data.

7. **Incomplete lifecycle ownership**
   - Disconnect, deletion, sync, report scheduling, and remediation worker behavior are not consistently modeled as durable workflows with auditable state.

## K. Recommended Fix Order

This is a verification-driven order, not an implementation performed in this audit.

1. **Repair and regression-test repository scan persistence.**
   - Initialize counters before both dedup loops.
   - Align `RawFinding` and adapter field names.
   - Add a clean scan, one threat, one vulnerability, repeated scan, and multi-repository test.

2. **Run authenticated populated-tenant tests.**
   - Create two tenants and users.
   - Insert or ingest representative repositories, findings, assets, policies, SBOMs, and reports.
   - Test every list/detail/action endpoint for same-tenant success and cross-tenant denial.

3. **Make provider/scanner failure states explicit.**
   - Separate “provider returned zero data” from “provider call failed.”
   - Fix undefined error variables and add retry/backoff where required.
   - Ensure sync state cannot claim success after a swallowed provider exception.

4. **Validate scan and provider feed coverage.**
   - Exercise Semgrep/Gitleaks/Bandit/pip-audit/npm/Trivy/Docker paths.
   - Verify AWS Security Hub, GitHub Dependabot/CodeQL, GitLab, and Kubernetes feeds using test credentials or fixtures that represent real provider responses; do not add demo data to the product database.

5. **Fix SBOM correctness.**
   - Execute vulnerability lookup.
   - Decide whether Syft is required or manifest fallback is a supported reduced mode.
   - Parse actual dependency relationships and mark unavailable enrichment explicitly.

6. **Fix report format and schedule claims.**
   - Implement or remove Excel/PDF options.
   - Add durable scheduled execution and delivery observability.
   - Verify each advertised template produces dedicated content.

7. **Finish action workflows.**
   - Remediation cancellation/rollback/execute.
   - Ownership editing.
   - Provider disconnect cleanup/revocation.
   - Integration update retest coverage.

8. **Normalize score and empty-data semantics.**
   - Document whether “no data” is 0, 100, or unavailable for each metric.
   - Prevent derived/mock categories from being mistaken for independently collected findings.

9. **Add security regression coverage to CI.**
   - Tenant isolation/IDOR tests.
   - Scan worker tests.
   - Provider failure-state tests.
   - Export content-type/format tests.
   - SBOM package/detail tests.

## L. Exact Files / Functions That Need Changes

No changes were made during this audit. The following are the highest-priority change locations identified by evidence:

### Immediate correctness fixes

- `backend/app/tasks/run_scan.py`
  - Scan persistence function around `:187-235`: initialize and scope dedup counters correctly.
- `backend/app/services/scan_engine.py`
  - `RawFinding` at `:38-51` and `ResultAdapter.to_threats()` around `:1040-1098`: use one consistent raw payload field.
- `backend/app/services/sbom_service.py`
  - `_get_vulnerabilities_for_package()` around `:324-359`: execute the prepared query and serialize rows.
- `backend/app/services/reports_service.py`
  - `_build_export_content()` around `:676-721`: implement Excel/PDF or remove unsupported formats.
- `backend/app/services/integration_service.py`
  - Sync/error branches around `:454-489` and `:549-568`: replace undefined `itype` and preserve intended provider error behavior.

### Provider and lifecycle coverage

- `backend/app/tasks/sync_security.py`
  - Revisit vulnerability dedup key around `:99-128` so unrelated targets are not merged by CVE alone.
- `backend/app/tasks/sync_pipelines.py`
  - Add or explicitly document CodeQL/GitLab finding ingestion around `:133-269`.
- `backend/app/api/v1/endpoints/integrations.py`
  - Update retest/sync coverage around `:194-242`; disconnect cleanup around `:249-258`; full sync orchestration around `:347-477`.
- `backend/app/services/asset_discovery_service.py`
  - Credential handling around `:36-44`; provider coverage around `:70-122`.
- `backend/app/tasks/sync_pods.py`
  - Credential handling around `:78-86` and provider failure semantics around `:91-169`.
- `backend/app/services/reports_service.py` and `backend/app/core/celery_app.py`
  - Durable scheduled report execution and delivery.

### UI/action gaps

- `artifacts/uniops/src/pages/SecurityCenter/sections/Ownership.tsx:1079`
  - Replace local alert edit placeholder with persisted API action.
- `artifacts/uniops/src/pages/SecurityCenter/sections/SecurityPosture.tsx:484-490`
  - Label or replace mock-derived misconfiguration categories.
- `backend/app/api/v1/endpoints/remediation.py:272`
  - Implement worker cancellation signal and verify controller side effects.
- `backend/app/services/sbom_service.py:302-310`
  - Replace synthetic dependency tree with actual relationship data.
- `backend/app/api/v1/endpoints/sbom.py:227-255`
  - Populate or explicitly model unavailable package enrichment fields.

## Final Status Lists

### REAL

“Real” here means a source-level implementation with database/provider/action code, not proof of successful populated runtime execution.

- Protected health endpoint and authentication enforcement on inspected Security Center routes.
- Tenant-scoped repository, threat, vulnerability, asset, posture, policy, exception, ownership, SLA, report, SBOM, and Copilot query paths.
- AWS integration connection/test/orchestration path.
- GitHub/GitLab repository and pipeline synchronization paths.
- Kubernetes client, pod synchronization, cluster scan persistence path.
- AWS Security Hub mapping code for threats, vulnerabilities, and compliance.
- GitHub Dependabot vulnerability mapping.
- Database persistence for report, SBOM, posture, Copilot, policy, exception, remediation, ownership, and SLA records.

### PARTIAL

- Overview, repositories, infrastructure, assets, Kubernetes, threats, vulnerabilities, posture, compliance, policies, remediation, intelligence, governance, ownership, SLA, reports, SBOM, and Copilot sections.
- AWS/GitHub/GitLab/Kubernetes integrations as complete Security Center data sources.
- Scanner engine breadth and fallback handling.
- Multi-tenant isolation as a whole.
- Credential encryption and integration lifecycle.
- Score calculation and historical posture.
- Report compilation and scheduling.

### BROKEN

- Repository scan completion/persistence due to the uninitialized `dedup_count` and `RawFinding.raw_data` defects.
- SBOM package vulnerability detail lookup because the query function returns `[]`.
- Excel report export because it returns JSON placeholder content.
- Integration authentication error handling in branches referencing undefined `itype`.

### MOCK / FAKE

- Copilot deterministic fallback when Anthropic is absent or fails.
- Security Posture misconfiguration categories explicitly labeled mock/derived.
- Synthetic SBOM dependency tree.

### STUB

- Excel export branch.
- Ownership edit alert.
- Remediation cancellation worker signal/no-op.
- Trivy/Semgrep integration sync paths.
- Report template generic fallback for unhandled templates.

### UNVERIFIED

- Any authenticated populated-tenant UI/API flow.
- Any successful repository clone and scan through completion.
- Repeated scan deduplication and multi-repository isolation in runtime.
- External AWS, GitHub, GitLab, Kubernetes, intelligence-feed, and LLM calls.
- Celery worker/beat execution and recurring report execution.
- Provider credentials/permissions/network behavior.
- Concurrent duplicate prevention and database uniqueness behavior.
- Cross-tenant negative tests across every ID-addressed route.
- PDF export and email delivery.
- Production/deployed configuration and runtime behavior.