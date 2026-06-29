# UniOps — Recovery Point Objective (RPO) / Recovery Time Objective (RTO)

> **Audience**: platform team, SREs, customers in enterprise deals, compliance auditors.
> **Scope**: production UniOps platform data plane (PostgreSQL primary, Redis cache, Celery broker, secrets).

---

## 1. Definitions

* **RPO** — the maximum acceptable data loss, measured in time.  If the
  database is destroyed at `T`, the most data we can lose is the work
  done in the last `RPO` seconds.
* **RTO** — the maximum acceptable downtime, measured in time.  After a
  disaster at `T`, the platform MUST be serving traffic again by
  `T + RTO`.

Both are committed values; failing to meet them is itself an incident.

---

## 2. Committed Objectives

| Tier | RPO | RTO | Notes |
|---|---|---|---|
| **Tier 1 — Primary PostgreSQL** | **1 hour** | **4 hours** | Daily `pg_dump` + WAL shipping (operator-configured) |
| Tier 2 — Redis (cache + broker) | 0 (rebuildable) | 30 minutes | No persistent state; broker queue can be drained from producers |
| Tier 3 — Celery in-flight tasks | 0 (drained) | 30 minutes | Tasks are re-queued on broker recovery |
| Tier 4 — Secrets / config | 0 (in git) | 30 minutes | Secrets in cluster + Sealed Secrets backup |

### Why these numbers

* **RPO = 1h** is the cron-driven `pg_dump` cadence (default 03:00 UTC)
  plus an optional WAL archive (operator-configured).  Production
  deployments that need sub-hour RPO MUST enable WAL archiving (e.g.
  WAL-G / pgBackRest) and update this document.
* **RTO = 4h** assumes the on-call can rebuild a fresh cluster from the
  `pg_dump`, re-run Alembic, redeploy the API and workers, and warm
  Redis.  This is well above the documented manual restore time of
  ~90 minutes for a 50GB database.

---

## 3. Backup Frequency

| Asset | Mechanism | Frequency | Retention |
|---|---|---|---|
| PostgreSQL data | `pg_dump` cronjob (`infra/k8s/backup/cronjob.yaml`) | Daily 03:00 UTC | 14 days local + configurable object store |
| PostgreSQL WAL (optional) | WAL-G / pgBackRest — operator-configured | Continuous (every 5 min) | 7 days |
| Redis | None (in-memory only) | n/a | n/a |
| Kubernetes manifests | Git | Every push | Permanent |
| Secrets (Sealed Secrets / External Secrets) | Git + cluster backup | Every push | Permanent |

### Backup validation

* Every backup job exits with a status code that the Kubernetes Job
  controller records; the alert `UniOpsBackupFailing` pages on any
  failure.
* **Quarterly restore drill** — the on-call must perform a full restore
  to a scratch cluster and run `make smoke-restore`.  Result is logged
  in `#uniops-ops` with the date and outcome.
* **Annual DR exercise** — a controlled region-failover test (if
  multi-region) or a full cluster rebuild (single-region).

---

## 4. Restore Procedure (summary)

Full step-by-step in [`RUNBOOK.md`](RUNBOOK.md § 3).  Sequence:

1. Stop the API (scale to zero) — preserve any in-flight requests by
   waiting 30 s for graceful shutdown.
2. Stop Celery workers and beat.
3. Select the latest `pg_dump` from `/backups/` (or object store).
4. `gunzip` and pipe into `psql`.
5. Run `alembic upgrade head` to reconcile any later migrations.
6. Verify with `make smoke-restore`.
7. Scale API + workers back up.
8. Verify health endpoints:
   * `/api/v1/health/live`  → 200
   * `/api/v1/health/ready` → 200
   * `/api/v1/health/startup` → 200
9. Update Statuspage.
10. Open postmortem ticket (Sev1 / Sev2).

---

## 5. Recovery Time Estimates

| Step | Estimated time |
|---|---|
| 1. Acknowledge page + open incident | 5 minutes |
| 2. Stop API + workers | 2 minutes |
| 3. Identify + pull backup | 5 minutes |
| 4. `gunzip` + `psql` import (50GB DB) | 60–90 minutes |
| 5. Alembic reconcile | 5 minutes |
| 6. Smoke test | 10 minutes |
| 7. Scale API + workers back up | 5 minutes |
| 8. Health verify + statuspage | 10 minutes |
| **Total RTO (best case)** | **~100 minutes** |
| **Total RTO (with delays)** | **~240 minutes** |

---

## 6. Recovery Point Estimates

| Scenario | Data lost |
|---|---|
| Single PVC corruption, restore from latest `pg_dump` | ≤ 24 hours |
| Single PVC corruption, restore from latest `pg_dump` + WAL archive | ≤ 5 minutes |
| Total database loss, only `pg_dump` available | ≤ 24 hours |
| Total database loss, last `pg_dump` AND object store available | ≤ 24 hours |
| Total database loss + corrupt last `pg_dump` | use previous-day backup → ≤ 48 hours |

If RPO ≤ 5 min is a contractual requirement (e.g. PCI / financial
workloads), operators MUST enable continuous WAL archiving (e.g.
WAL-G to S3 with `WALG_DELTA_MAX_STEPS=10`).

---

## 7. Communication During Recovery

* Statuspage updated within 15 minutes of declaring the incident.
* Internal updates in `#uniops-incidents` every 30 minutes.
* Final "All Clear" only after `/health/ready` returns 200 and
  `make smoke-restore` passes.

---

## 8. Compliance Mapping

| Framework | Control | Evidence |
|---|---|---|
| SOC 2 CC7.5 | Backup & restore tested | Quarterly restore drill logs |
| SOC 2 CC7.4 | Incident response | [`RUNBOOK.md`](RUNBOOK.md) |
| ISO 27001 A.12.3.1 | Backup policy | This document |
| GDPR Art. 32 | Availability | RPO/RTO committed in DPA |

---

## 9. Owner

Platform team (`#uniops-platform`).  Review this document quarterly;
update when SLOs change.