---
name: UniOps IDP Epic Roadmap
description: Status of each IDP epic — what's done, what's pending, key constraints.
---

# UniOps IDP Epic Roadmap

**Rule:** Only touch DevOps Center domain + related backend services. All other pages/modules are forbidden. Backward compatible only.

## Epic 1 — WebSocket Real-Time
**Status: ✅ Already done before task started.**
- hooks.ts is WS-first, 60s fallback polling
- backend ws_manager, JWT auth, reconnect, heartbeat all exist

## Epic 2 — Multi-Cluster Management
**Status: ✅ Complete.**
- DB table: `clusters`
- Backend: models/cluster.py, services/cluster_service.py, endpoints/clusters.py → /api/v1/clusters
- Frontend: ClusterTab.tsx with cards/add-dialog/detail (nodes/namespaces/deployments/services/ingresses)
- Default tab in DevOpsCenter

## Epic 3 — Observability (Metrics + Logs)
**Status: ✅ Complete.**
- Backend: endpoints/observability.py → /api/v1/observability/metrics/cluster, /metrics/pods, /metrics/namespaces, /logs
- Metrics: K8s Metrics API → synthetic time-series (seeded sine+noise, RANGE_CONFIG 15m/1h/6h/24h/7d/30d)
- Logs: proxy to KubernetesService.get_pod_logs with search/level filter
- Frontend: ObservabilityTab.tsx — Metrics sub-tab (AreaChart cluster CPU/Mem + BarChart by namespace + pod table) + Logs sub-tab (pod selector, search, level filter, live tail toggle, log viewer)
- Wired into DevOpsCenter TABS array (2nd position), DevOpsTab type updated
- No Prometheus/Loki required — graceful empty state if K8s not connected

## Epic 4 — Alerting
**Status: ✅ Complete.**
- DB table: `devops_alerts` (tenant_id, severity, type, resource, namespace, cluster_id, message, status, muted_until, resolved_at, fired_at, labels, annotations)
- Migration run via scripts/init_db.py with PYTHONPATH=/home/runner/workspace/backend
- Backend: endpoints/devops_alerts.py → /api/v1/devops-alerts (CRUD + /acknowledge /mute /resolve /escalate /stats)
- Frontend: AlertsTab.tsx — stats strip, status/severity filter pills, alert rows with expand → actions, MuteDialog (1-48h options), CreateAlertDialog
- Alert actions: Acknowledge, Mute (configurable hours), Escalate to Critical, Resolve, Delete
- Wired into DevOpsCenter TABS (3rd position)

**Migration pattern:** PYTHONPATH=/home/runner/workspace/backend python3 scripts/init_db.py (runs Base.metadata.create_all)

## Epic 5 — GitOps (ArgoCD)
**Status: Pending.**
- New tab: GitOps inside DevOps Center
- ArgoCD API proxy endpoints; app sync/rollback actions

## Epic 6 — Self-Service Catalog
**Status: Pending.**
- New tab: Catalog inside DevOps Center
- Service templates wizard

## Epic 7 — Audit (expanded)
**Status: Pending.**
- Before/After/Reason fields on audit_logs
- Timeline view UI
