# UniOps — Production Documentation

> All production documentation for the UniOps platform lives in `docs/`.
> The table below is the index.

| Document | Purpose | Owner |
|---|---|---|
| [`docs/RUNBOOK.md`](RUNBOOK.md) | Day-to-day incident response, deployment, scaling, monitoring, alerts, emergency procedures, on-call rotation | Platform team |
| [`docs/RPO_RTO.md`](RPO_RTO.md) | Recovery Point Objective, Recovery Time Objective, backup frequency, restore procedure | Platform team |
| [`docs/DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md) | Catastrophic-failure scenarios (cluster loss, data corruption, secret compromise) and recovery steps | Platform team |
| [`infra/k8s/README.md`](../infra/k8s/README.md) | Kubernetes manifests overview, deployment guide | Platform team |
| [`backend/README.md`](../backend/README.md) | Backend service overview, local dev setup | Backend team |

---

## Quick links

* **Live status**: [status.uniops.io](https://status.uniops.io)
* **Grafana**: [grafana.uniops.io](https://grafana.uniops.io)
* **Sentry**: [uniops.sentry.io](https://uniops.sentry.io)
* **API reference (dev)**: `http://localhost:8000/docs`
* **Production API**: `https://api.uniops.io/docs`
* **PagerDuty**: `uniops-prod` schedule
* **Slack**: `#uniops-incidents` (active incidents), `#uniops-oncall` (non-urgent)

---

## Production deployment (one-page summary)

1. **Provision cluster** — EKS / GKE / AKS / self-hosted, k8s 1.27+
2. **Install prerequisites** — `metrics-server` (CPU/memory HPA), `cert-manager` (TLS), `ingress-nginx` (ingress), Prometheus + `prometheus-adapter` (custom metrics).
3. **Apply manifests**:
   ```bash
   kubectl apply -k infra/k8s/
   kubectl apply -k infra/k8s/overlays/production
   kubectl apply -k infra/k8s/backup
   kubectl apply -k infra/k8s/observability
   ```
4. **Run Alembic**:
   ```bash
   kubectl -n uniops exec -it deploy/uniops-api -- alembic upgrade head
   ```
5. **Verify health**:
   ```bash
   curl https://api.uniops.io/api/v1/health/live
   curl https://api.uniops.io/api/v1/health/ready
   curl https://api.uniops.io/api/v1/health/startup
   ```
6. **Configure DNS** — point `api.uniops.io` to the ingress.
7. **Configure alerting** — apply `prometheus-rules.yaml` in your Prometheus instance.

---

## Environments

| Environment | APP_ENV | Cluster | Database | Notes |
|---|---|---|---|---|
| Development | development | `uniops-dev` | SQLite or dev Postgres | Local docker-compose |
| CI | test | ephemeral | ephemeral Postgres | GitHub Actions matrix |
| Staging | staging | `uniops-staging` | staging RDS | Mirrors production topology |
| Production | production | `uniops-prod` | production RDS | See [`docs/RPO_RTO.md`](RPO_RTO.md) |

---

## Security posture

* All secrets stored in Kubernetes Secrets (encrypted at rest by the
  cloud provider) and mounted via `secretKeyRef`.
* TLS termination at the ingress; ACME-driven cert renewal via
  cert-manager.
* `APP_ENV=production` enforces:
  * `SECRET_KEY` must be ≥ 32 chars and not a known placeholder.
  * `CORS_ORIGINS` must be explicit (no `*`).
  * `DEBUG` must be `False`.
  * Migrations are exclusively Alembic — `Base.metadata.create_all()` is
    a no-op in production.
* Rate limiting (per tenant, per endpoint, burst + sustained) is enforced
  in `app/middleware/rate_limit.py`.  See `RATE_LIMIT_*` env vars.
* All secrets in CI are masked and never logged.

---

## Observability stack

| Layer | Tool | Path |
|---|---|---|
| Structured logging | structlog → JSON | `app/observability/logging.py` |
| Distributed tracing | OpenTelemetry | `app/observability/tracing.py` |
| Error tracking | Sentry | `app/observability/sentry.py` |
| Metrics | Prometheus (custom + auto) | `app/observability/metrics.py` |
| Dashboards | Grafana | `infra/k8s/observability/` |
| Alerts | PrometheusRule CRD | `infra/k8s/observability/prometheus-rules.yaml` |

Every log line carries: `timestamp`, `level`, `event`, `trace_id`,
`span_id`, `correlation_id`, `request_id`, `tenant_id`, `user_id`,
`module`, `service`, `environment`, `version`.

---

## Change management

* **Trunk-based** — `main` is always deployable.
* **Feature branches** — `sprint/<name>` or `feat/<name>`.
* **CI** — every push runs lint + typecheck + tests + coverage.
* **CD** — release tags (`v*`) trigger image build + push; Argo CD / Flux
  picks up the new tag and rolls out the cluster.
* **Rollback** — `kubectl rollout undo deploy/uniops-api`.  See
  [`docs/RUNBOOK.md`](RUNBOOK.md § 2.2).

---

## Contacts

* **Platform team** — `#uniops-platform`
* **Security** — `#uniops-security`
* **Manager on-call** — PagerDuty schedule `uniops-mgr`
* **Customer support** — `#uniops-support`