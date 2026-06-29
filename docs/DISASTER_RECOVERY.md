# UniOps — Disaster Recovery

> **Audience**: on-call engineers, SREs, engineering leadership.
> **Purpose**: define the response for catastrophic failures (region loss, data corruption, secret compromise).
> **Related**: [`RUNBOOK.md`](RUNBOOK.md) (day-to-day incidents), [`RPO_RTO.md`](RPO_RTO.md) (recovery objectives).

---

## 1. Failure Scenarios

Each scenario is documented with:
* **Detection** — what fires the alert
* **Impact** — user-visible consequence
* **Response** — ordered steps to recover
* **Owner** — who has authority to act

---

### 1.1 Cluster Loss (Kubernetes control plane unreachable)

**Detection**: All `kubectl` calls fail; alerts stop arriving; PagerDuty never fires.

**Impact**: Total outage.  Customers cannot reach the API.  No automation can run.

**Response**:
1. Confirm it's not just a laptop problem — check status.cloud provider for K8s managed-service incidents.
2. Page the engineering manager immediately.
3. If the cluster is hosted (EKS / GKE / AKS), open a critical ticket with the cloud provider.
4. If self-hosted, attempt etcd restore from snapshot (provider-specific).
5. If recovery is impossible within 30 minutes, begin **failover**:
   * Bring up the warm-standby cluster (if configured in multi-region).
   * Update DNS (Route 53 / Cloud DNS) to point to the standby ingress.
   * Verify the standby can reach the same database (RDS cross-region replica promotion).
6. Customer comms: Statuspage incident opened within 15 minutes.

**Owner**: IC declares the failover; SRE executes the steps.

---

### 1.2 Node Loss

**Detection**: `NodeNotReady` alert; HPA cannot schedule new pods; PodDisruptionBudget stops replacement.

**Impact**: Reduced capacity; some requests may fail.

**Response**:
1. Confirm: `kubectl get nodes` shows the node as `NotReady`.
2. Drain: `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`.
3. If the node does not come back in 10 minutes, the cluster autoscaler will replace it.
4. If autoscaler is broken, manually delete the node: `kubectl delete node <node>`.
5. Confirm HPA rebalances pods: `kubectl -n uniops get pods -o wide`.

**Owner**: on-call.

---

### 1.3 Database Corruption / Loss

**Detection**: `UniOpsDatabaseDown` alert; API returns 500; replication lag spikes.

**Impact**: Total outage until DB is restored.

**Response**: See [`RUNBOOK.md`](RUNBOOK.md § 3) for full steps.

1. STOP THE API FIRST — `kubectl -n uniops scale deployment/uniops-api --replicas=0`.
2. Stop workers (they may be holding open sessions).
3. Pick the most recent clean backup.
4. Restore (`pg_dump` → `psql`).
5. Run `alembic upgrade head`.
6. Run `make smoke-restore`.
7. Bring services back up.

**Owner**: IC + DBA.

---

### 1.4 Redis Failure

**Detection**: `UniOpsRedisDown` alert; rate-limit middleware logs `fail-open` warnings; Celery workers cannot dequeue.

**Impact**:
* API continues to serve (rate limiter deliberately fails open).
* Decision / approval / execution pipelines stall because the broker is down.

**Response**:
1. Confirm: `kubectl -n redis get pods` — if pod is dead, let the StatefulSet replace it.
2. If Redis data is lost (no AOF), accept that:
   * Rate-limit counters reset (acceptable — Redis is not the source of truth).
   * Broker queue is empty (in-flight tasks were never persisted; producers must re-enqueue).
3. If persistent broker loss is unacceptable, switch to RabbitMQ / SQS (operator decision).

**Owner**: on-call.

---

### 1.5 Broker Failure (Celery)

**Detection**: `UniOpsAPIHighErrorRate` spikes with 503s from `/api/v1/executions/*`; worker logs show `ConnectionError` to Redis.

**Impact**: Asynchronous jobs cannot be queued; synchronously-callable endpoints still work.

**Response**:
1. Same as Redis failure — broker is Redis in our deployment.
2. If the broker is migrated to RabbitMQ in future, follow the broker-specific recovery runbook.

**Owner**: on-call.

---

### 1.6 Storage Failure

**Detection**: PVC alert; backup CronJob fails; persistent volume claims cannot bind.

**Impact**: Depending on which PVC:
* `postgres_data` — total data loss (see §1.3).
* `models_data` — ML models reload from object store on next boot.
* `backend_logs` — logs lost (recoverable from structlog stdout + Loki).
* `celery_beat_data` — schedule lost (rebuilt on next boot).

**Response**:
1. Identify which PVC is failing (`kubectl get pvc -A`).
2. For data PVCs, recover from backup (PostgreSQL: §1.3).
3. For ephemeral PVCs, delete and let the StatefulSet recreate them.

**Owner**: on-call + SRE.

---

### 1.7 Secrets Recovery

**Detection**: Pods fail to start with `ImagePullBackOff` (wrong registry creds) or `Error from server (Forbidden)` (wrong secret).

**Impact**: Deployments cannot roll out; new pods cannot start.

**Response**:
1. Identify the missing secret: `kubectl -n uniops describe pod <pod>`.
2. If using External Secrets Operator, verify the secret store is reachable.
3. If using Sealed Secrets, the source of truth is `infra/k8s/overlays/production/sealed-secrets.yaml` — re-apply:
   ```bash
   kubectl apply -f infra/k8s/overlays/production/sealed-secrets.yaml
   ```
4. If a sealed secret is itself lost, re-encrypt from the original values:
   ```bash
   kubeseal --format yaml < secret.yaml > sealed-secret.yaml
   ```
5. If the cluster master key is lost, the Sealed Secrets are unrecoverable — restore from the encrypted backup in object storage.

**Owner**: security team + SRE.

---

### 1.8 DNS Recovery

**Detection**: `dig api.uniops.io` returns NXDOMAIN; cert-manager cannot complete ACME challenge.

**Impact**: API unreachable by hostname.

**Response**:
1. Check the DNS provider's health (Route 53 / Cloud DNS).
2. If records were accidentally deleted, restore from IaC (Terraform / Pulumi).
3. If TTL is high, wait for propagation or manually lower TTL.
4. Verify: `dig +short api.uniops.io` returns the ingress IP.

**Owner**: SRE.

---

### 1.9 TLS Recovery

**Detection**: `UniOpsCertificateExpiring` alert; browsers show "Your connection is not private".

**Impact**: Customers cannot connect via HTTPS without a trust exception.

**Response**:
1. cert-manager auto-renews when the issuer can reach the ACME endpoint.  Confirm:
   ```bash
   kubectl -n uniops describe certificate
   ```
2. If renewal is failing:
   * Check the `Challenge` resource: `kubectl -n uniops describe challenge`
   * Verify ingress connectivity (port 80 must be reachable from the internet).
   * If the issuer is broken, rotate the secret manually (§9 of runbook).
3. If expired and cert-manager cannot renew, deploy the manual cert immediately.

**Owner**: SRE.

---

## 2. Multi-Region Failover (if configured)

Production deployments that require sub-30-minute RTO across a region
loss MUST be deployed in active-passive or active-active across at
least two regions.

**Active-passive** (recommended for v1):
* Primary region serves 100% of traffic.
* Secondary region runs a read-replica of PostgreSQL and a hot
  standby of all stateless services.
* On primary loss: promote the read replica, flip DNS, scale the
  standby to full capacity.

**Active-active**:
* Both regions serve traffic via geo-DNS.
* PostgreSQL uses bidirectional replication (e.g. Bucardo) or a
  multi-master (e.g. CockroachDB).
* Requires application-level conflict resolution — not a Sprint 4
  scope item.

Operators MUST update this document with their specific topology.

---

## 3. Communication During DR

| Channel | When |
|---|---|
| Statuspage | Opened within 15 minutes of Sev1 / Sev2 declaration |
| Customer email | For incidents lasting > 1 hour |
| `#uniops-incidents` Slack | Continuous updates every 30 min |
| Engineering manager | For Sev1 / failover decisions |
| Legal / Compliance | For data-breach scenarios |

---

## 4. DR Drill Schedule

| Drill | Frequency | Owner |
|---|---|---|
| Restore from `pg_dump` to scratch cluster | Quarterly | on-call |
| Kill API pod, verify HPA recovers | Monthly | on-call |
| Kill Postgres pod, verify StatefulSet recovers | Quarterly | SRE |
| Failover to standby region (if multi-region) | Annually | SRE + manager |
| Secret rotation | Quarterly | security team |

Drills are scheduled in `#uniops-ops`.  Results logged in the same
channel with the date, scenario, time-to-recover, and follow-ups.

---

## 5. Decision Authority

The Incident Commander (IC) has unilateral authority to:
* Trigger a region failover.
* Stop / scale services.
* Roll back deploys.
* Engage the cloud provider's critical-incident path.

The IC does NOT need manager approval for any of the above during an
active incident.  Post-hoc review covers any decisions made.

---

## 6. Post-Incident

1. Within 5 business days, schedule a blameless postmortem.
2. Use the template in [`RUNBOOK.md`](RUNBOOK.md § 12).
3. Action items tracked in the issue tracker with an owner and due date.
4. If the incident changed the RPO / RTO commitment, update [`RPO_RTO.md`](RPO_RTO.md) and notify customers.

---

## 7. Owner

Platform team (`#uniops-platform`).  Reviewed semi-annually or after any DR-level incident.