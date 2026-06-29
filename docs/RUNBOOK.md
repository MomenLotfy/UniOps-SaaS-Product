# UniOps Runbook

> **Audience**: on-call engineers, SREs, and incident commanders.
> **Scope**: production UniOps platform (FastAPI backend + Celery workers + PostgreSQL + Redis).
> **Owner**: Platform team.  Every alert, dashboard, and procedure below is owned by the team listed in `OWNERS`.

---

## 0. Quick Reference

| Channel | Use |
|---|---|
| `#uniops-incidents` Slack | Active incidents, paging, status updates |
| `#uniops-oncall` Slack | Non-urgent ops discussion, handoffs |
| PagerDuty `uniops-prod` | Sev1 / Sev2 pages |
| Statuspage (`status.uniops.io`) | Customer-facing status |
| Runbook source of truth | This document (repo) |

| Severity | Definition | Response Time |
|---|---|---|
| Sev1 | Customer-impacting outage, data loss, security incident | Acknowledge ≤ 5 min |
| Sev2 | Major degradation, single feature unavailable | Acknowledge ≤ 15 min |
| Sev3 | Minor degradation, internal-only | Acknowledge ≤ 1 hour |
| Sev4 | Cosmetic, advisory | Next business day |

---

## 1. Incident Response (Sev1 / Sev2)

1. **Acknowledge** the page in PagerDuty within 5 minutes.
2. **Open incident channel** `#inc-YYYY-MM-DD-<short-name>` in Slack.
3. **Declare IC** — the first responder becomes Incident Commander until they hand off.
4. **Page secondary** if root cause is unclear after 15 minutes.
5. **Status update** every 30 minutes in `#uniops-incidents`.
6. **Customer comms** at Sev1 — coordinate with comms lead to draft a Statuspage update within 15 minutes of declaration.
7. **Postmortem** scheduled within 5 business days of resolution.

### Decision tree (API down)

```
API returning 5xx?
├── Yes →  Is /health/ready failing?
│         ├── Yes → Is PostgreSQL up?
│         │         ├── Yes → Are migrations pending?  → run alembic upgrade head
│         │         ├── No  → follow "PostgreSQL down" below
│         └── No  → App-level crash; check uvicorn logs and recent deploys
├── No  → Are requests slow?
│         ├── Yes → check CPU/memory in Grafana; check pipeline duration metrics
│         └── No  → check rate-limit headers; check upstream callers
```

---

## 2. Deployment & Rollback

### 2.1 Deploy (rolling)

```bash
# From a release manager laptop:
git tag -s v$(date +%Y.%m.%d)-$(git rev-parse --short HEAD) -m "release"
git push --tags

# CI builds the image and pushes to the registry; Argo CD / Flux
# detects the new tag and rolls out.  Watch:
kubectl -n uniops rollout status deployment/uniops-api --timeout=10m
```

### 2.2 Rollback (immediate)

If a deploy is causing customer harm:

```bash
# 1. Pause the rollout so it doesn't auto-heal
kubectl -n uniops rollout pause deployment/uniops-api

# 2. Roll back to the previous ReplicaSet
kubectl -n uniops rollout undo deployment/uniops-api

# 3. Verify the rollback completed
kubectl -n uniops rollout status deployment/uniops-api

# 4. Resume auto-rollout once you have confirmation
kubectl -n uniops rollout resume deployment/uniops-api

# 5. Announce in #uniops-incidents
```

### 2.3 Rollback (Celery worker / beat)

```bash
kubectl -n uniops rollout undo deployment/uniops-celery-worker
kubectl -n uniops rollout undo deployment/uniops-celery-beat
```

### 2.4 Failed migration

If `alembic upgrade head` fails in the entrypoint, the API will not start
(Sprint 4: the `create_all` fallback is disabled in production).

```bash
# Get the failing pod:
kubectl -n uniops get pods -l app=uniops-api

# Inspect:
kubectl -n uniops logs <pod> | grep -i alembic

# Fix the migration script, commit, push.  The next CI run will
# rebuild the image with the corrected migration.  DO NOT bypass
# the migration with create_all.
```

---

## 3. Restore (Database)

See [`RPO_RTO.md`](RPO_RTO.md) for the recovery objectives.

### 3.1 From a PVC-archived `pg_dump`

```bash
# 1. Scale the API to zero so no traffic hits a half-restored DB
kubectl -n uniops scale deployment/uniops-api --replicas=0

# 2. Stop the celery workers (they may be holding open sessions)
kubectl -n uniops scale deployment/uniops-celery-worker --replicas=0
kubectl -n uniops scale deployment/uniops-celery-beat --replicas=0

# 3. Pick the desired backup
BACKUP=$(kubectl -n uniops exec -it postgres-backup-<jobid> -- \
  ls /backups | sort | tail -1)
echo "Restoring: $BACKUP"

# 4. Copy it locally and decompress
kubectl -n uniops cp postgres-backup-<jobid>:/backups/$BACKUP /tmp/$BACKUP
gunzip /tmp/$BACKUP

# 5. Apply against the database
psql "$DATABASE_URL" < /tmp/${BACKUP%.gz}

# 6. Re-run alembic upgrade head to pick up any later migrations
#    (the backup is from an earlier migration head; alembic stamps will reconcile).
alembic upgrade head

# 7. Verify
psql "$DATABASE_URL" -c "SELECT version_num FROM alembic_version;"

# 8. Bring services back up
kubectl -n uniops scale deployment/uniops-api --replicas=3
kubectl -n uniops scale deployment/uniops-celery-worker --replicas=2
kubectl -n uniops scale deployment/uniops-celery-beat --replicas=1
```

### 3.2 From object store

If `BACKUP_BUCKET` is configured the CronJob copies each `pg_dump` to S3
(or S3-compatible) storage.  Restore via `psql`:

```bash
aws s3 cp s3://$BACKUP_BUCKET/<timestamp>.sql.gz /tmp/
gunzip /tmp/<timestamp>.sql.gz
psql "$DATABASE_URL" < /tmp/<timestamp>.sql
```

### 3.3 Restore validation

After every restore the on-call MUST run the smoke-test script:

```bash
make smoke-restore
```

This verifies row counts in core tables, FK integrity, and that the
`/api/v1/health/ready` endpoint returns 200.

---

## 4. Scaling

### 4.1 Manual scale

```bash
# Bump replicas immediately (overrides HPA)
kubectl -n uniops scale deployment/uniops-api --replicas=10

# Confirm
kubectl -n uniops get deployment uniops-api
```

### 4.2 HPA tuned values

The API HPA is in `infra/k8s/api/hpa.yaml`.  Common knobs:

| Symptom | Change |
|---|---|
| Scaling too late | Lower `behavior.scaleUp.stabilizationWindowSeconds` to 15s |
| Flapping | Raise `behavior.scaleDown.stabilizationWindowSeconds` to 600s |
| Need more headroom | Raise `maxReplicas` |

### 4.3 Worker concurrency

Worker concurrency is fixed at 2 per pod (see `docker-compose.yml`).  To
scale up throughput, bump `--concurrency=N` in `celery-worker`
deployment OR scale replicas.

---

## 5. Monitoring

### 5.1 Dashboards

* **Grafana `uniops-api`** — RED metrics (Rate / Errors / Duration) per
  endpoint, pipeline state-transition counters, rate-limit blocks.
* **Grafana `uniops-workers`** — Celery queue depth, task duration,
  failure rate.
* **Grafana `uniops-infra`** — Postgres / Redis / disk / network.

### 5.2 SLOs

| Service | SLO | Window |
|---|---|---|
| `POST /api/v1/*` | 99.9% success | 30 days |
| `GET /api/v1/health/ready` | 99.99% success | 30 days |
| Decision pipeline | p95 < 5s | 30 days |
| Approval pipeline | p95 < 30s | 30 days |

### 5.3 Alerts

Alerts live in `infra/k8s/observability/prometheus-rules.yaml` (CRD).
Each alert has a `runbook_url` annotation pointing back to this document.

---

## 6. Alerts Reference

| Alert | Severity | First action |
|---|---|---|
| `UniOpsAPIHighErrorRate` | critical | Check recent deploys; consider rollback (§2.2) |
| `UniOpsAPILatencyHigh` | warning | Inspect slow-query log; check DB connections |
| `UniOpsPipelineFailuresSpike` | critical | Inspect pipeline logs (`app.modules.security.*`) |
| `UniOpsRateLimited` | warning | Check upstream caller; consider whitelisting |
| `UniOpsDatabaseDown` | critical | §7 — Database incident |
| `UniOpsRedisDown` | warning | §8 — Redis incident |
| `UniOpsBackupFailing` | critical | Run manual backup; investigate failure (§3) |
| `UniOpsBackupMissing` | critical | Run manual backup now |
| `UniOpsCertificateExpiring` | warning | Renew cert (§9) |

---

## 7. Database (PostgreSQL) Incident

1. **Check pod**: `kubectl -n postgres get pods -l app=postgres`
2. **Check logs**: `kubectl -n postgres logs <pod> | tail -200`
3. **Resource pressure?**: `kubectl top pod <pod>` — high memory or throttling?
4. **Connection exhaustion?**: `SELECT count(*) FROM pg_stat_activity;`
   - Compare against `max_connections` (default 100)
   - If saturated, kill long-running idle-in-transaction sessions:
     `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle in transaction';`
5. **Replication lag?** (if HA): `SELECT now() - pg_last_xact_replay_timestamp();`
6. **If data corruption suspected**: STOP writes (§3 step 1) and page DBA.

---

## 8. Redis Incident

1. **Check pod**: `kubectl -n redis get pods -l app=redis`
2. **`redis-cli ping`** — if no PONG, restart: `kubectl -n redis delete pod -l app=redis`
3. **Memory full?**: `redis-cli info memory` — check `used_memory` vs `maxmemory`
4. **Eviction policy too aggressive?** — adjust `maxmemory-policy` in Helm values.
5. **Rate limiter fail-open**: the limiter deliberately allows traffic
   when Redis is down (so the API stays up).  Expect a warning in logs:
   `rate limiter degraded (fail-open)`.

---

## 9. TLS / Certificate Renewal

The ingress uses cert-manager with Let's Encrypt.  Renewal is automatic
when the issuer can reach the ACME challenge endpoint.

```bash
# Check cert status:
kubectl -n uniops get certificate

# Force renewal (debug only):
kubectl -n uniops annotate certificate uniops-tls cert-manager.io/issue-temporary-certificate="true"
```

Manual renewal (debug only — never bypass cert-manager in prod):

```bash
openssl req -newkey rsa:2048 -nodes -keyout tls.key \
  -subj "/CN=api.uniops.io" | \
openssl x509 -req -signkey tls.key -days 90 -out tls.crt

kubectl -n uniops create secret tls uniops-tls --cert=tls.crt --key=tls.key --dry-run=client -o yaml | kubectl apply -f -
```

---

## 10. Emergency Procedures

### 10.1 Disable a misbehaving feature

```bash
# If a feature flag is wired to a ConfigMap:
kubectl -n uniops patch configmap uniops-config --type merge \
  -p '{"data":{"FEATURE_X_ENABLED":"false"}}'

# Restart the API to pick up the change:
kubectl -n uniops rollout restart deployment/uniops-api
```

### 10.2 Throttle an abusive tenant

```bash
# Per-tenant rate limit is set via the JWT `tenant_id` claim and the
# `RATE_LIMIT_TENANT_BURST_PER_MINUTE` / `RATE_LIMIT_TENANT_SUSTAINED_PER_HOUR`
# environment variables.  To throttle in real time:
kubectl -n uniops set env deployment/uniops-api \
  RATE_LIMIT_TENANT_BURST_PER_MINUTE=10 \
  RATE_LIMIT_TENANT_SUSTAINED_PER_HOUR=100

kubectl -n uniops rollout restart deployment/uniops-api
```

### 10.3 Freeze all writes

```bash
# Make the database read-only (Sprint 4-compatible):
psql "$DATABASE_URL" -c "ALTER SYSTEM SET default_transaction_read_only = on;"
psql "$DATABASE_URL" -c "SELECT pg_reload_conf();"

# (Reversed by `ALTER SYSTEM RESET default_transaction_read_only;`.)
```

### 10.4 Evacuate a node

```bash
# Drain gracefully (respects PDB)
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data

# If the node is unresponsive:
kubectl delete node <node>   # do not run without IC approval
```

---

## 11. On-Call Rotation

* Primary on-call: weekly rotation, handoff Monday 09:00 UTC.
* Secondary on-call: receives pages if primary does not acknowledge in 5 min.
* Manager escalation: if primary + secondary are unreachable for 15 min,
  page the engineering manager via the `uniops-mgr` PagerDuty schedule.
* Handoff checklist: review open incidents, pending alerts, recent deploys,
  upcoming maintenance windows.

---

## 12. Postmortem Template

```
## Summary
One-paragraph summary of what happened and customer impact.

## Impact
- Duration:
- Customer-facing degradation:
- Internal-only impact:
- Errors / failed requests:

## Timeline (UTC)
- HH:MM — first alert
- HH:MM — on-call acknowledged
- HH:MM — root cause identified
- HH:MM — mitigation applied
- HH:MM — fully resolved

## Root cause
Technical explanation of the underlying issue.

## Contributing factors
What made the issue worse than it needed to be.

## What went well
Detection, response, comms.

## What went poorly
Gaps in monitoring, runbook, comms, or response.

## Action items
- [ ] Owner 1 — Description (due YYYY-MM-DD)
- [ ] Owner 2 — Description (due YYYY-MM-DD)
```