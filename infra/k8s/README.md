# UniOps Production Kubernetes Deployment

This directory contains production-grade Kubernetes manifests for the
UniOps Control Tower. Every resource is fully specified — no placeholders,
no `<<` substitutions, no `latest:` tags, every container has
`resources.requests/limits`, every workload has probes + PDB + ServiceAccount.

## Layout

```
infra/k8s/
├── namespace.yaml            # uniops namespace + NetworkPolicy
├── configmap.yaml            # non-secret env
├── secret.example.yaml       # doc-only — real values via SealedSecrets
├── ingress.yaml              # nginx-ingress + cert-manager + TLS
├── api/                      # FastAPI backend
│   ├── deployment.yaml       # 3 replicas, rolling update
│   ├── service.yaml          # ClusterIP :8000
│   ├── serviceaccount.yaml   # + Role/RoleBinding
│   ├── hpa.yaml              # 3..20 replicas, CPU + custom metric
│   ├── pdb.yaml              # minAvailable: 2
│   ├── networkpolicy.yaml    # ingress from ingress-nginx only
│   └── probes.yaml           # split out for readability
├── celery-worker/
│   ├── deployment.yaml       # 2 replicas, single concurrency
│   ├── serviceaccount.yaml
│   └── pdb.yaml
├── celery-beat/
│   ├── deployment.yaml       # 1 replica (singleton leader)
│   ├── serviceaccount.yaml
│   └── pdb.yaml
└── overlays/
    ├── dev/kustomization.yaml
    ├── staging/kustomization.yaml
    └── production/kustomization.yaml
```

## Probes

Each deployment uses three probes:

| Probe       | Path                              | Failure threshold | Period |
|-------------|-----------------------------------|-------------------|--------|
| `startup`   | `/api/v1/health/startup`          | 30                | 5s     |
| `liveness`  | `/api/v1/health/live`             | 3                 | 10s    |
| `readiness` | `/api/v1/health/ready`            | 3                 | 5s     |

These are exposed by `backend/app/api/v1/endpoints/health.py` (R38).

## Secrets

`secret.example.yaml` documents the required secret keys but does NOT
contain real values.  In production, secrets are managed by:

1. **External Secrets Operator** (preferred) — pulls from AWS Secrets
   Manager / GCP Secret Manager / Vault and mounts as k8s Secret.
2. **Sealed Secrets** — encrypted at-rest; safe to commit.
3. **Manual** — create with `kubectl create secret generic`.

## Deployment

```bash
# Render (single overlay)
kustomize build infra/k8s/overlays/production | kubectl apply -f -

# Static validation
kustomize build infra/k8s/overlays/production > /tmp/render.yaml
grep -E '<<|REPLACE_ME|TODO|latest:' /tmp/render.yaml && echo "DIRTY" || echo "clean"
```

## Required Cluster Components

| Component                  | Purpose                                    |
|----------------------------|--------------------------------------------|
| `ingress-nginx`            | Ingress controller                         |
| `cert-manager`             | TLS certificate issuance                   |
| `metrics-server`           | HPA CPU/memory metrics                     |
| `prometheus-adapter` (opt) | HPA custom-metric support                  |
| `external-secrets` (opt)   | Secret sync                                |

## Resource Budget

| Component       | CPU (req/lim) | Memory (req/lim) |
|-----------------|---------------|------------------|
| api             | 250m / 1000m  | 512Mi / 1Gi      |
| celery-worker   | 250m / 2000m  | 512Mi / 2Gi      |
| celery-beat     | 50m / 200m    | 64Mi / 256Mi     |

## Zero-Downtime

Rolling update strategy on every Deployment:
- `maxUnavailable: 0` (never kill a pod before its replacement is ready)
- `maxSurge: 1`
- `terminationGracePeriodSeconds: 30` (matches preStop drain)