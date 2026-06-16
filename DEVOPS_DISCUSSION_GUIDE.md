# UniOps Control Tower - DevOps Discussion Guide (30 min)

> A comprehensive, ready-to-use discussion guide covering the DevOps side of the UniOps Control Tower graduation project — from analysis to expected committee questions.

---

## 📑 Table of Contents

1. [Project Analysis](#1-project-analysis)
2. [End-to-End Flow](#2-end-to-end-flow-from-git-push-to-user)
3. [30-Minute Discussion Script](#3-30-minute-discussion-script)
4. [10 Expected Committee Questions & Answers](#4-10-expected-committee-questions--answers)
5. [Key Talking Points](#5-key-talking-points)
6. [Quick Reference Table](#6-quick-reference-table)

---

## 1. Project Analysis

**Project:** UniOps Control Tower — A SaaS platform that centralizes DevOps integrations (GitHub, GitLab, Stripe, Slack) into a single control plane.

**DevOps components discovered in the repository:**

| Component | Location | Purpose |
|---|---|---|
| **GitHub Actions** | `.github/workflows/main.yml` + `nightly-security.yml` | Primary CI/CD (7 stages) + nightly security scan |
| **Jenkinsfile** | `jenkins/Jenkinsfile` (10 stages) | Legacy / alternate CI pipeline |
| **Docker Compose** | `docker-compose.yml` | Local dev environment (6 services) |
| **Dockerfiles** | `backend/Dockerfile` + `artifacts/uniops/Dockerfile` | Multi-stage builds |
| **Terraform (AWS)** | `terraform/app/phase-01..05/` | 5 modules: networking, EKS, data, tools, security |
| **Helm Chart** | `infra-backup/helm/` (Chart + values-dev/prod) | Packaging for K8s |
| **Kustomize** | `k8s/base/` + `k8s/overlays/dev\|prod/` | Alternative / complement to Helm |
| **ArgoCD** | `k8s/argocd-apps/monitoring-app.yaml` | GitOps controller |
| **Monitoring** | `monitoring/prometheus.yml` + `k8s/monitoring/monitoring.yaml` | Prometheus + ServiceMonitor + PrometheusRule |
| **Ansible** | `infrastructure/ansible/site.yml` + `roles/` | Configuration management for bastion/nodes |

---

## 2. End-to-End Flow: From `git push` to User

### Stage 1 — Developer Push
```
git push origin main
   ↓
Webhook → GitHub repo (MomenLotfy/UniOps-SaaS-Product)
```

### Stage 2 — GitHub Actions CI/CD (7 stages, dependency graph)

```
Stage 1: 🔍 SonarCloud (SAST + code quality)        ─┐
Stage 2: 🛡️ OWASP Dependency Check                  ─┴── parallel
                                                ↓
Stage 3: 🔨 Build & Test (pnpm typecheck)           ← needs: 1, 2
                                                ↓
Stage 4: 🔒 Security Scan (Trivy + Semgrep)         ← needs: 3
                                                ↓
Stage 5: 🐳 Build & Push Images                     ← needs: 4   (main only)
   ├── Docker Hub: momenpanda/uniops-{frontend,backend}
   └── ECR:      663476173962.dkr.ecr.us-east-2.amazonaws.com/uniops-{frontend,backend}
                                                ↓
Stage 6: 📦 Update Helm values-prod.yaml            ← needs: 5   (main only)
   (sed update image tag + git commit + push)
                                                ↓
Stage 7: ✅ Pipeline Complete (status report)       ← needs: 5, 6
```

### Stage 3 — GitOps (ArgoCD)
```
ArgoCD watches GitHub repo (poll every 3 min)
   ↓
Detects change in infra-backup/helm/values-prod.yaml
   ↓
Pulls new Helm chart from Git
   ↓
Diffs Desired State (Git) vs Live State (Cluster)
   ↓
Applies to EKS cluster (uniops namespace)
   ├── PreSync  hook: Job uniops-migrate (DB migrations)
   ├── Sync:           Deployment backend / frontend / celery
   └── PostSync:       HPA + PDB + NetworkPolicy
```

### Stage 4 — Kubernetes Workloads (in EKS)
```
Ingress (nginx) → /api/*       → backend Service  → 3 pods
                → /            → frontend Service → 2 pods
                → /ws/*        → backend WebSocket
                → /webhooks/*  → backend (GitHub / Stripe / GitLab)

backend pods → RDS PostgreSQL (via IRSA)
              → ElastiCache Redis
              → S3 (backups / logs)
              → EFS (shared ML models)

celery-worker (3–8 pods) → Redis broker
celery-beat    (1 pod)   → scheduled tasks
```

### Stage 5 — Infrastructure (Terraform-managed)
```
AWS Account 663476173962 / us-east-2
├── VPC (10.0.0.0/16) + 2 public + 2 private subnets
├── EKS Cluster (uniops-eks-dev, K8s 1.30)
├── RDS PostgreSQL (db.t3.micro)
├── ElastiCache Redis (cache.t3.micro)
├── EFS (uniops-efs-dev)
├── S3 buckets (backups, logs, terraform-state)
├── KMS keys (8 keys) + IAM + IRSA
├── Bastion EC2 (t3.micro) + 2 worker nodes (m7i-flex.large)
└── WAF + GuardDuty (config ready, not yet active)
```

### Stage 6 — Observability
```
Prometheus (kube-prometheus-stack)
   ├── ServiceMonitor : scrape backend /metrics every 15s
   ├── PrometheusRule : 4 alert groups
   │     ├── Availability (Backend/Postgres/Redis down)
   │     ├── Error rates  (5xx > 5% warning, > 20% critical)
   │     ├── Latency     (p95 > 2s, p99 > 5s)
   │     └── K8s resources (CrashLoop, PVC full, HPA maxed)
   └── Alertmanager → Slack / PagerDuty (configured)
```

---

## 3. 30-Minute Discussion Script

### 🎙️ [00:00 – 02:00] Opening — Project Overview
> "UniOps Control Tower is a SaaS platform that unifies DevOps integrations (GitHub, GitLab, Stripe, Slack) into a single control plane. On the DevOps side, I focused on six pillars: **CI/CD with GitHub Actions, GitOps with ArgoCD, Infrastructure as Code with Terraform, Containerization with Docker, Monitoring with Prometheus, and Configuration Management with Ansible**."

### 🎙️ [02:00 – 07:00] CI/CD Pipeline (5 min)
> "I chose **GitHub Actions** because the project already lives on GitHub — no overhead for a self-hosted runner, and the marketplace has ready-made actions for everything I need (SonarCloud, Trivy, AWS ECR). I designed **7 stages** as a **dependency graph**, not a linear chain. SonarCloud and OWASP Dependency Check run **in parallel** before the build, which saves ~3 minutes per pipeline run.
>
> **Failure handling:** every security scan has `continue-on-error: true` so a false positive never blocks deployment. A `pipeline-complete` stage emits a final status report. The `update-helm` stage runs **only** if the build succeeded — we never push a bad tag to the Helm chart."

### 🎙️ [07:00 – 12:00] GitOps with ArgoCD (5 min)
> "I used **ArgoCD** as the GitOps controller because the **single source of truth must be Git**. The Helm chart lives in `infra-backup/helm/`, with values in `values-prod.yaml`. ArgoCD reconciles every 3 minutes.
>
> **Helm + Kustomize combo:** two layers. **Kustomize** in `k8s/base/` holds the raw manifests (Deployments, Services, PDB, NetworkPolicy) because Kustomize shines when the **same base** is reused across overlays (dev/prod). **Helm** handles packaging when you have templated charts.
>
> **Rollback — three levels:**
> 1. **ArgoCD UI** → History → Revert (fastest, < 30s)
> 2. **kubectl rollout undo deployment/backend** (uses revision history)
> 3. **Helm rollback** → `helm rollback uniops-prod 2`"

### 🎙️ [12:00 – 16:00] DevSecOps (4 min)
> "I implemented **shift-left security** with four tools in the main pipeline:
> 1. **SonarCloud** — SAST (static analysis) for TypeScript and Python
> 2. **OWASP Dependency-Check** — CVE scan on npm / pip dependencies
> 3. **Trivy** — filesystem scan on source + container scan on images
> 4. **Semgrep** — secret detection + pattern matching
>
> Everything also runs in a **nightly scan** (cron: `0 2 * * *`) so newly disclosed CVEs in dependencies are caught.
>
> **If a CRITICAL is found:** the build does not stop (`continue-on-error`), but **Prometheus alerts** + **Slack webhook** fire, and the team reviews before merging to main."

### 🎙️ [16:00 – 21:00] Infrastructure as Code (5 min)
> "The Terraform is split into **5 phases** under `terraform/app/`:
> 1. **phase-01-networking** — VPC, subnets (2 public + 2 private), IGW, NAT GW, Security Groups
> 2. **phase-02-eks** — EKS cluster + node groups + IRSA
> 3. **phase-03-data** — RDS PostgreSQL, ElastiCache Redis, EFS, S3 buckets
> 4. **phase-04-tools** — Bastion EC2, ALB, IAM roles
> 5. **phase-05-security** — KMS, WAF, GuardDuty, SNS alarms, VPC flow logs
>
> **Modules are composed** in `root.tf` — the `data` module consumes `vpc_id` from the `networking` module and `node_security_group_id` from the `eks` module. This pattern lets me `terraform destroy` a single phase without affecting the rest.
>
> **State** is stored in **S3** (`uniops-terraform-state`) with **DynamoDB locking** (`uniops-terraform-locks`) so concurrent applies never corrupt state."

### 🎙️ [21:00 – 24:00] Container Strategy (3 min)
> "I built **two images**, not one:
> - **uniops-frontend** — React (Node 22 build) → nginx 1.27 alpine (runtime)
> - **uniops-backend** — Python 3.12 alpine (deps + runtime); reused by the backend Deployment, celery-worker, celery-beat, and the migration Job (same image, different CMD).
>
> **Why two?** A monorepo image would weigh ~1.2 GB (node + python + nginx). Splitting them gives ~50 MB (frontend) and ~200 MB (backend). Bonus: independent scaling, faster pulls, smaller security blast radius.
>
> **Multi-stage build:**
> - Frontend: `node:22-alpine` (builder) → `nginx:1.27-alpine` (final, ~50 MB)
> - Backend:  `python:3.12-alpine3.20` (deps) → `python:3.12-alpine3.20` (production, no `build-base`)
>
> **Docker Hub + ECR — why both?** **Docker Hub** (`momenpanda`) gives public visibility and is useful for local experimentation. **ECR** is private, IAM-controlled, has built-in scanning, and is faster to pull from inside the AWS VPC."

### 🎙️ [24:00 – 27:00] Monitoring & Observability (3 min)
> **Pipeline monitoring:**
> - GitHub Actions UI → logs, duration, per-stage status
> - Slack notifications on `#uniops-ci` (success / failure)
> - Nightly security scan → SARIF uploaded to GitHub Security tab
>
> **Production monitoring:**
> - **Prometheus** (kube-prometheus-stack Helm chart) scrapes metrics every 15s
> - **ServiceMonitor** auto-discovers the backend via label `app.kubernetes.io/name: backend`
> - **4 alert groups**: Availability (down alerts), Errors (5xx rates), Latency (p95/p99), K8s resources (PVC, HPA, CrashLoop)
> - **HPA** scales 2→8 pods on CPU 70 % / memory 80 %, with **fast scale-up (60s)** and **slow scale-down (300s)** to avoid flapping
> - **NetworkPolicy** default-deny + explicit whitelists (Zero-Trust within the namespace)"

### 🎙️ [27:00 – 30:00] Wrap-up (3 min)
> "In one sentence: **Commit to main → GitHub Actions builds, tests, security-scans → pushes images to ECR + Docker Hub → updates Helm values in Git → ArgoCD picks up the change → applies to EKS → Prometheus watches it → if something breaks, rollback in < 30 seconds.** **Ansible** is there for bastion configuration management (SSH access, kubectl install, EBS CSI tooling) — Terraform is great at infra provisioning, not OS-level config.
>
> The whole stack delivers: **IaC 100 %** (Terraform + Ansible) + **GitOps** (ArgoCD) + **DevSecOps** (4 layers) + **Auto-scaling** (HPA) + **Zero-downtime deployments** (PDB + 3 replicas)."

---

## 4. 10 Expected Committee Questions & Answers

### ❓ Q1: Why GitHub Actions and not Jenkins?
> **A:** Because the project already lives on GitHub, GitHub Actions removes the overhead of a self-hosted Jenkins master + agent. We get managed runners (Ubuntu), a marketplace of trusted actions (SonarCloud, Trivy, AWS ECR, `docker/build-push`), and PR checks work out of the box without manual webhook wiring. Jenkins is a traditional **CI tool**; GitHub Actions is a **platform** natively integrated with the SCM.

### ❓ Q2: What is the difference between the 7 stages in `main.yml` and the 10 stages in `jenkins/Jenkinsfile`? Which one is active?
> **A:** The `Jenkinsfile` was the **initial CI/CD** written when the project was running on EC2 directly. After we moved to **EKS + GitOps**, `main.yml` became the **active pipeline** and the `Jenkinsfile` is kept as a **legacy reference**. The Jenkinsfile has a manual approval gate before the production deployment — we still need to add that to GitHub Actions via GitHub Environments.

### ❓ Q3: ArgoCD or Flux CD?
> **A:** I chose **ArgoCD** because its Web UI is much better for debugging. It also supports **multi-cluster**, **ApplicationSets**, and **Sync Waves** (the `PreSync` hook for the migration Job). It integrates with GitHub SSO. Flux is lighter and more Kubernetes-native, but ArgoCD wins on observability and rollback UX.

### ❓ Q4: Why two separate images (frontend + backend)? Why not a monorepo image?
> **A:** Four reasons:
> 1. **Image size** — a monorepo image would be ~1.2 GB (node + python + nginx). Splitting them is ~50 MB (frontend) + ~200 MB (backend).
> 2. **Pull speed** — K8s pulls faster on scale-up.
> 3. **Independent scaling** — the frontend may need to scale more than the backend.
> 4. **Blast radius** — if the frontend is compromised, the attacker has no Python runtime to abuse.

### ❓ Q5: What is the difference between Helm and Kustomize in this project, and where do I use each?
> **A:**
> - **Kustomize** in `k8s/base/` + `overlays/dev|prod/` holds the application manifests (Deployment, Service, Ingress). It is best when the **same base** is shared across environments.
> - **Helm** in `infra-backup/helm/` (`Chart.yaml` + `values-prod.yaml`) is best for **reusable, templated charts** deployable to many clusters.
> - **Integration:** ArgoCD reads the Helm chart and applies it with overrides from `values-prod.yaml`.

### ❓ Q6: If I deploy and there is a bug, how do I roll back, and how long does it take?
> **A:** Three options:
> 1. **ArgoCD UI** (fastest, < 30s) → Applications → uniops-monitoring → History → Revert to the last good revision.
> 2. **`kubectl rollout undo`** → `kubectl rollout undo deployment/backend -n uniops --to-revision=5` (2–3 min).
> 3. **Helm** → `helm rollback uniops-prod 1` (2–3 min).
> K8s keeps the last 10 revisions by default.

### ❓ Q7: Where is the Terraform state, and what if it gets lost?
> **A:** State is in an **S3 bucket** (`uniops-terraform-state`) with **versioning enabled**, and a **DynamoDB table** (`uniops-terraform-locks`) handles state locking. If the bucket is accidentally deleted, I can either `terraform import` every resource, or roll back to an older S3 object version.

### ❓ Q8: Do the security scans block the build if they find a vulnerability?
> **A:** **No** — every security scan has `continue-on-error: true` (Trivy, Semgrep, SonarCloud). I do not want a false positive to block deployment. Instead:
> - **Critical vulnerabilities** go to **Slack** + the **GitHub Security tab** (SARIF upload).
> - The **team reviews** before merge.
> - A future enhancement is a **Quality Gate** in SonarCloud that blocks merge if coverage < 80 % or code smells exceed a threshold.

### ❓ Q9: How do you monitor the pipeline itself (not just production)?
> **A:**
> - **GitHub Actions UI** → duration, success rate, per-stage logs.
> - **Slack notifications** on `#uniops-ci` (success / failure).
> - **GitHub API** → can be wired to **Grafana** via the GitHub datasource to build a pipeline-metrics dashboard (future work).
> - **Nightly security scan** runs at 02:00 and uploads SARIF to the GitHub Security tab.

### ❓ Q10: Why is the HPA scale-up faster than scale-down?
> **A:** To avoid **flapping** and to optimize **user experience**:
> - **Scale-up** — 60s stabilization, +2 pods/min — during a spike, users should never wait.
> - **Scale-down** — 300s (5 min) stabilization, -1 pod/min — when traffic drops, we do not kill pods too fast, so we never drop **in-flight requests**.
> - **Celery-worker** is the opposite: **scale-up in 30s** (tasks must not queue) and **scale-down in 600s** (a worker needs time to drain its current tasks). The `terminationGracePeriodSeconds: 60` on the worker pod supports this.

---

## 5. Key Talking Points

- **GitOps** — The single source of truth lives in Git. What is in Git is what is in Production.
- **Shift-Left Security** — Catch vulnerabilities before they reach Production.
- **Infrastructure as Code** — The entire production environment can be recreated with a single `terraform apply`.
- **Auto-scaling + Self-healing** — The cluster adapts to load with no human intervention.
- **Disaster Recovery** — Rollback in < 30 seconds + Terraform state versioning + EFS for ML models.

---

## 6. Quick Reference Table

| Topic | Tool / Service | One-line Justification |
|---|---|---|
| **CI/CD** | GitHub Actions (active) + Jenkinsfile (legacy) | Native to GitHub, marketplace, free |
| **Security** | SonarCloud + OWASP + Trivy + Semgrep | 4 layers: SAST, deps, container, secrets |
| **GitOps** | ArgoCD | Web UI, multi-cluster, sync waves |
| **IaC** | Terraform (5 phases) | Modular, state in S3 + DynamoDB |
| **Config Mgmt** | Ansible | Bastion config, kubectl install |
| **Containers** | Docker multi-stage | 2 images: frontend (nginx) + backend (python) |
| **Registries** | Docker Hub (public) + ECR (private) | Visibility + AWS-internal speed |
| **Orchestration** | EKS (K8s 1.30) + Kustomize + Helm | Base/overlays + chart packaging |
| **Monitoring** | Prometheus + Grafana + Alertmanager | ServiceMonitor + PrometheusRule |
| **Scaling** | HPA (CPU/memory) + PDB (HA) | Auto-scale + zero-downtime |
| **Network** | nginx Ingress + NetworkPolicy + ALB | Path routing + Zero-Trust |
| **Storage** | RDS + ElastiCache + EFS + S3 | The right storage for each workload |

---

## 🚀 Final Notes

- **Active pipeline:** `.github/workflows/main.yml` (7 stages)
- **Legacy pipeline:** `jenkins/Jenkinsfile` (kept for reference)
- **Default region:** `us-east-2`
- **ECR registry:** `663476173962.dkr.ecr.us-east-2.amazonaws.com`
- **EKS cluster:** `uniops-eks-dev` (K8s 1.30)
- **Default namespace:** `uniops`
- **Backup/legacy helm:** `infra-backup/helm/`

Good luck on your defense! 🎓
