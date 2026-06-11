# UniOps Infrastructure Report

> **Generated:** 2026-06-06
> **Scope:** read-only audit of every infra file under `infra-backup/`, `terraform/`, `infrastructure/`, `k8s/`, plus the two lifecycle scripts at the repo root.
> **Source of truth precedence:** (1) live AWS API queries via `aws` CLI, (2) repo files actually in the live overlay (`k8s/base/` + `k8s/overlays/dev/`), (3) the legacy 5-phase tree at `infra-backup/infrastructure/terraform/` whose local state file is a 270 KB / 106-resource mirror of the live infra, (4) the bootstrap layer at `terraform/bootstrap/` whose state lives in S3 at `s3://uniops-terraform-state/bootstrap/terraform.tfstate`.

---

## 1. Directory Tree

```
/home/u1/Desktop/UniOps-SaaS-Product/
├── destroy-app-infra.sh                                  # Application-layer teardown script (v1.0, 772 lines)
├── start-app-infra.sh                                    # Application-layer startup script   (v3.0, 688 lines)
│
├── terraform/                                            # REAL bootstrap layer (committed, 7 resources)
│   └── bootstrap/
│       ├── backend.tf                                    # Backend: bucket=uniops-terraform-state, key=bootstrap/terraform.tfstate
│       ├── s3.tf                                         # aws_s3_bucket.terraform_state + version + SSE + PAB (prevent_destroy)
│       ├── dynamodb.tf                                   # aws_dynamodb_table.terraform_locks (PAY_PER_REQUEST, prevent_destroy)
│       ├── ecr.tf                                        # aws_ecr_repository.{backend,frontend} (MUTABLE, no scan-on-push)
│       ├── iam.tf                                        # Comments only (no IAM in bootstrap today)
│       ├── provider.tf                                   # AWS provider, us-east-2
│       ├── variables.tf                                  # aws_region, state_bucket_name, dynamodb_lock_table, ecr_repositories
│       └── outputs.tf                                    # state_bucket_*, dynamodb_lock_*, ecr_*_repository_{url,arn}
│
├── infra-backup/                                         # LEGACY 5-phase layout (used to build the live cluster)
│   └── infrastructure/
│       └── terraform/
│           ├── root.tf                                   # Module orchestrator (networking, eks, data, tools, security)
│           ├── locals.tf                                 # name = "${project}-${environment}"
│           ├── variables.tf                              # project_name=uniops-saas, environment=dev, cluster_version=1.30
│           ├── shared/
│           │   ├── backend.tf                            # backend s3 { key=app/terraform.tfstate }   (canonical form)
│           │   ├── provider.tf                           # backend s3 { key=terraform.tfstate }       (legacy, duplicate)
│           │   ├── locals.tf                             # common_tags
│           │   └── variables.tf                          # aws_region=us-east-2
│           ├── bootstrap/                                # Local-state bootstrap (NOT the real one)
│           │   └── main.tf                               # Bucket=uniops-terraform-state-8j3k9l (typo'd; doesn't exist)
│           ├── phase-01-networking/                      # VPC, public/private subnets, IGW, NAT, routes, bastion, internal SG
│           ├── phase-02-eks/                             # EKS cluster, node group, IAM (cluster+node+IRSA), OIDC, k8s namespace
│           ├── phase-03-data/                            # RDS postgres, ElastiCache redis, EFS, S3 backups+logs
│           ├── phase-04-tools/                           # ALB, public EC2, monitoring/sonarqube EC2, IAM for tools
│           └── phase-05-security/                        # KMS, WAF, AWS Config, GuardDuty (commented), VPC flow logs, SNS, CloudWatch alarms
│
├── infrastructure/                                       # ALTERNATE all-in-one layout (git-tracked; backend=prod/terraform.tfstate in us-east-1)
│   └── terraform/
│       ├── main.tf                                       # VPC + EKS + RDS + Redis + 2 ECR + S3 backups (terraform-aws-modules, ~287 lines)
│       ├── variables.tf                                  # region=us-east-1, env=dev, 3 private + 3 public subnets
│       └── outputs.tf                                    # vpc_id, eks_cluster_*, database_*, redis_*, ecr_*, backups_bucket
│
├── k8s/                                                  # LIVE K8s manifests (what the cluster actually runs)
│   ├── base/
│   │   ├── kustomization.yaml                            # Source of truth — namespace, SA, ConfigMap, secret template, postgres, redis, backend, celery, frontend, ingress, HPA, PDB, NetworkPolicy
│   │   ├── namespace.yaml                                # uniops + ResourceQuota (10 CPU, 20Gi mem) + LimitRange (500m default, 100m request)
│   │   ├── serviceaccount.yaml                           # uniops-backend, uniops-worker, uniops-frontend + Role uniops-k8s-reader + 2 RoleBindings
│   │   ├── configmap.yaml                                # APP_NAME, APP_ENV=production, DEBUG=false, DB pool, Celery settings, CORS
│   │   ├── secret.yaml                                   # Template only (REPLACE_WITH_*) — replaced by setup-secrets.sh
│   │   ├── postgres.yaml                                 # StatefulSet postgres:16-alpine, headless Service, PVC 20Gi, probes via pg_isready
│   │   ├── redis.yaml                                    # StatefulSet redis:7-alpine, headless Service, PVC 5Gi, AOF + auth
│   │   ├── backend.yaml                                  # migrate Job + backend Deployment (2 replicas, 2 uvicorn workers) + PVC models-pvc + Service :80→:8000
│   │   ├── celery.yaml                                   # celery-worker Deployment (2 replicas, pgrep liveness), celery-beat (1 replica, Recreate), PVC celerybeat-pvc
│   │   ├── frontend.yaml                                 # frontend Deployment (2 replicas, nginx:alpine, :80, tmpfs volumes, /health) + Service :80
│   │   ├── ingress.yaml                                  # Ingress uniops-ingress, host=uniops.local, paths /api, /ws, /webhooks → backend; / → frontend
│   │   ├── hpa.yaml                                      # HPA backend (2-8, CPU 70% / mem 80%), HPA celery-worker (2-6, CPU 75%)
│   │   ├── pdb.yaml                                      # PodDisruptionBudget backend (minAvailable=1)
│   │   ├── network-policy.yaml                           # allow-internal NetworkPolicy (ingress from pods + ingress-nginx, egress to pods/kube-dns/external 80,443)
│   │   └── cert-manager.yaml                             # ClusterIssuer letsencrypt-prod (ACME HTTP-01)
│   ├── overlays/
│   │   ├── dev/
│   │   │   ├── kustomization.yaml                        # Image tags backend=dev, frontend=dev, ConfigMap merge APP_ENV=development, DEBUG=true
│   │   │   └── namespace-dev.yaml                        # Namespace uniops-dev
│   │   └── prod/
│   │       └── kustomization.yaml                        # Pinned tags 1.0.0, 3 replicas, real domain, TLS via cert-manager, HPA 3-10 / 3-8
│   ├── monitoring/
│   │   ├── kustomization.yaml                            # kustomize root
│   │   └── monitoring.yaml                               # ServiceMonitor uniops-backend + PrometheusRule (availability/errors/latency/k8s)
│   └── scripts/
│       ├── bootstrap.sh                                  # Minikube zero-to-running bootstrap (625 lines)
│       ├── build-images.sh                               # buildx + push backend/frontend (123 lines)
│       └── setup-secrets.sh                              # Generates k8s Secret uniops-secrets with random values (182 lines)
│
├── monitoring/
│   ├── alerts.yml                                        # Standalone Prometheus rules (BackendDown, HighAPILatency, etc.)
│   └── prometheus.yml                                    # Standalone Prometheus scrape config (backend:8000, node_api:3001, flower:5555)
│
└── instructionsAndMemory/                                # Memory + report target (this file)
    └── INFRA-REPORT.md                                   # ← THIS FILE
```

---

## 2. AWS Architecture

Live resources in account **180840261837** / region **us-east-2** (verified 2026-06-06 via `aws` API).

| Resource | Name | Module | Purpose |
|----------|------|--------|---------|
| **VPC** | `vpc-0a0073d556bd28a55` (`uniops-saas-dev-vpc`, CIDR `10.0.0.0/16`) | phase-01-networking | Container for all live infra |
| **Public subnets** | `subnet-05320c4c512884360` (10.0.1.0/24 us-east-2a), `subnet-0f7050d87d38ff446` (10.0.2.0/24 us-east-2b) | phase-01-networking | ALB, NAT Gateway, Bastion, public EC2 |
| **Private subnets** | `subnet-0bf53bbc9eb9a6a21` (10.0.3.0/24 us-east-2a), `subnet-01f39508548a5e1d4` (10.0.4.0/24 us-east-2b) | phase-01-networking | EKS node group, RDS, Redis, EFS mount targets |
| **Internet Gateway** | `uniops-igw` | phase-01-networking | Egress for public subnets |
| **NAT Gateway** | `uniops-nat-gw` (in us-east-2a public subnet) + EIP `uniops-nat-eip` | phase-01-networking | Egress for private subnets |
| **EKS Cluster** | `uniops-eks-dev` (K8s 1.30, ACTIVE, created 2026-06-03T18:06:18) | phase-02-eks | Managed Kubernetes, public+private endpoint, OIDC enabled |
| **EKS Node Group** | `uniops-workers` (m7i-flex.large, ON_DEMAND, min=2/desired=2/max=3, AMI `AL2_x86_64`) | phase-02-eks | All K8s workloads run here |
| **EKS IAM role** | `uniops-eks-cluster-role` | phase-02-eks | Cluster service role (AmazonEKSClusterPolicy) |
| **EKS Node IAM role** | `uniops-eks-node-role` | phase-02-eks | Node IAM (WorkerNode + CNI + ECRReadOnly) |
| **IRSA role** | `uniops-irsa-role-dev` | phase-02-eks | Federated with EKS OIDC; trusts SA `system:serviceaccount:uniops:uniops-sa`; AmazonS3ReadOnly + SecretsManagerReadWrite |
| **OIDC provider** | EKS OIDC issuer | phase-02-eks | Enables IRSA |
| **RDS Postgres** | `uniops-postgres-dev` (postgres 15.17, db.t3.micro, 20GB gp2 encrypted, KMS key 7bd084cd-050d-40f8-9929-3ed18be1536a, endpoint `uniops-postgres-dev.czow22y627dw.us-east-2.rds.amazonaws.com:5432`) | phase-03-data | Database for backend + Celery result backend (in-cluster StatefulSet `postgres` is the live consumer, not this RDS — see §6) |
| **ElastiCache Redis** | `uniops-redis-dev` (redis 7.1, cache.t3.micro, transit+at-rest encryption, KMS, primary endpoint `master.uniops-redis-dev.wenqsd.use2.cache.amazonaws.com`) | phase-03-data | (Provisioned; not used at runtime — K8s in-cluster Redis serves) |
| **EFS** | `fs-0f6567c976ebd2349` (`uniops-efs-dev`, encrypted, KMS) + access point `uniops-efs-ap` | phase-03-data | NFS shared storage; two mount targets (one per private subnet) |
| **ALB** | `uniops-alb-dev` (Application, internet-facing, in both public subnets, SG `alb-sg`) | phase-04-tools | Entry point; HTTP listener on :80 → `uniops-alb-tg-dev`; placeholder ML target group `uniops-ml-tg-dev:8080` |
| **Bastion** | `uniops-bastion` (t3.micro, public IP, Amazon Linux 2) | phase-01-networking | SSH jump host; SSH key `uniops-key` (RSA 4096 generated by Terraform) |
| **Public EC2 ×2** | `uniops-public-1-dev`, `uniops-public-2-dev` (t3.micro) | phase-04-tools | Run `nginx` via Docker user_data |
| **Monitoring EC2** | `uniops-monitoring-dev` (t3.micro, private, 20GB gp3 root, Docker + docker-compose) | phase-04-tools | Prometheus + Grafana host |
| **SonarQube EC2** | `uniops-sonarqube-dev` (t3.micro, private, 30GB gp3 root) | phase-04-tools | Code quality |
| **ECR backend** | `uniops-backend` (MUTABLE tags, scan-on-push=false) | terraform/bootstrap | Docker image registry |
| **ECR frontend** | `uniops-frontend` (MUTABLE tags, scan-on-push=false) | terraform/bootstrap | Docker image registry |
| **S3 state bucket** | `uniops-terraform-state` (versioning, AES256, all PAB=true, prevent_destroy) | terraform/bootstrap | Terraform state backend — only contains `bootstrap/terraform.tfstate` |
| **S3 app backups** | `uniops-backups-dev-v22t87` (random 6-char suffix, KMS, versioned, PAB, 90d→GLACIER, 365d expire) | phase-03-data | RDS/EBS snapshots region |
| **S3 logs** | `uniops-logs-dev-storage` (KMS, PAB, 30d→IA, 180d expire) | phase-03-data | Application logs |
| **DynamoDB locks** | `uniops-terraform-locks` (PAY_PER_REQUEST, hash_key LockID, prevent_destroy) | terraform/bootstrap | Terraform state lock table |
| **KMS key** | `alias/uniops-dev-key` (key rotation enabled, 7-day deletion window) | phase-05-security | Encrypts RDS, EFS, S3 backups, S3 logs, WAF logs (custom IAM policy) |
| **WAFv2 Web ACL** | `uniops-waf-dev` (REGIONAL) + association to ALB | phase-05-security | 3 rules: AWSManagedRulesCommonRuleSet (priority 1), RateLimit 2000/IP (priority 2), GeoBlock (allow EG+US only) (priority 3) |
| **CloudWatch Log Group** | `aws-waf-logs-uniops` (30d retention) | phase-05-security | WAF request logs |
| **CloudWatch Log Group** | `uniops-vpc-flow-logs-dev` (30d retention) | phase-05-security | VPC flow logs destination |
| **SNS alerts** | `uniops-alerts-dev` + email subscription `devops-team@example.com` | phase-05-security | CloudWatch alarm target |
| **CloudWatch Alarms ×3** | `uniops-high-cpu-eks` (EKS CPU > 80%), `uniops-alb-5xx-errors` (5XX > 10 in 5min), `uniops-rds-free-storage` (<5GB) | phase-05-security | All fire to SNS alerts |
| **VPC Flow Log** | to `uniops-vpc-flow-logs-dev` (ALL traffic, IAM role `uniops-vpc-flow-log-role`) | phase-05-security | Network audit |
| **AWS Config** | `uniops-config-recorder` + rules (S3 public-read, restricted SSH, RDS encrypted, EBS encrypted) — **gated by `enable_aws_config` variable, default `false`** | phase-05-security | Compliance (NOT live; disabled by default) |
| **Backup Vault** | `uniops-backup-vault-dev` (KMS) + plan `uniops-backup-plan-dev` (daily 5AM UTC, 35d retain) + selection on RDS + EFS | phase-05-security | Managed backup |
| **AWS Backup IAM** | `uniops-backup-role` | phase-05-security | Backup service role |
| **GuardDuty** | **DISABLED** (the entire `aws_guardduty_detector` + 2 feature resources are commented out) | phase-05-security | Threat detection — present in HCL but not active |
| **IAM Role `config`** | `uniops-config-role` (only if `enable_aws_config=true`) | phase-05-security | AWS Config recorder service role |
| **IAM Role `monitoring`** | `uniops-monitoring-role` (CloudWatchAgentServerPolicy + AmazonEC2ReadOnlyAccess) | phase-04-tools | Monitoring instance role |
| **IAM Role `sonarqube`** | `uniops-sonarqube-role` | phase-04-tools | SonarQube instance role |
| **IAM Role `public_ec2`** | `uniops-public-ec2-role` | phase-04-tools | Public EC2 instance role |
| **Secrets Manager ×2** | `uniops/db-credentials-dev` (RDS), `uniops/redis-credentials-dev` (Redis) | phase-03-data | RDS + Redis credentials (KMS-encrypted) |
| **Security Groups** | `bastion-sg` (SSH 22 from 0.0.0.0/0), `vpc-internal` (all from VPC CIDR), `eks-cluster-sg` (egress all), `eks-worker-sg` (egress all + intra-SG + 1025-65535 from cluster SG + 443 from cluster), `rds-sg` (5432 from eks-worker-sg + VPC CIDR), `redis-sg` (6379 from eks-worker-sg + VPC CIDR), `efs-sg` (2049 from eks-worker-sg + VPC CIDR), `alb-sg` (80+443 from 0.0.0.0/0), `public-ec2-sg` (80+443 from alb-sg, 22 from bastion-sg), `monitoring-sg` (9090+3000 from VPC, 22 from bastion-sg), `sonarqube-sg` (9000 from VPC, 22 from bastion-sg) | various | Defense in depth |

---

## 3. Terraform Module Map

There are **5 candidate Terraform roots** in the repo, but the one that mirrors the live infra is `infra-backup/infrastructure/terraform/`. The bootstrap is the only one with a working S3 backend.

### 3.1 `terraform/bootstrap` (REAL, 7 resources)

| Resource | Purpose | Notes |
|---|---|---|
| `aws_s3_bucket.terraform_state` | State backend | `uniops-terraform-state`, versioning, AES-256 SSE, PAB all true, `prevent_destroy` |
| `aws_s3_bucket_versioning.terraform_state` | Versioning enabled | |
| `aws_s3_bucket_server_side_encryption_configuration.terraform_state` | AES256 | |
| `aws_s3_bucket_public_access_block.terraform_state` | All four blocks true | |
| `aws_dynamodb_table.terraform_locks` | State lock | `uniops-terraform-locks`, PAY_PER_REQUEST, `prevent_destroy` |
| `aws_ecr_repository.backend` | Backend image registry | `uniops-backend`, MUTABLE, scan-on-push=false |
| `aws_ecr_repository.frontend` | Frontend image registry | `uniops-frontend`, MUTABLE, scan-on-push=false |

**Inputs:** `aws_region=us-east-2`, `state_bucket_name=uniops-terraform-state`, `dynamodb_lock_table=uniops-terraform-locks`, `ecr_repositories=[uniops-backend, uniops-frontend]`.
**Outputs:** 9 outputs (state bucket name/arn/versioning, DDB table name/arn, both ECR repo URLs and ARNs).
**Backend:** S3 `uniops-terraform-state` / key `bootstrap/terraform.tfstate` / us-east-2 / DDB `uniops-terraform-locks`.
**Live state:** S3 `s3://uniops-terraform-state/bootstrap/terraform.tfstate` (12,227 bytes, last modified 2026-06-05T15:02:36Z). Local file at `terraform/bootstrap/terraform.tfstate` is 0 bytes; `.tfstate.backup` has 12,228 bytes.
**Verification:** `terraform plan -detailed-exitcode` from this directory returns **0 (no changes, infrastructure matches configuration)**. The real S3 state, not the local one, is authoritative.

### 3.2 `infra-backup/infrastructure/terraform` (LEGACY 5-phase, mirror of live infra)

#### Module `networking` (phase-01) — 17 resources

| Inputs | Outputs | Resources created |
|---|---|---|
| `aws_region=us-east-2`, `project_name=uniops-saas`, `environment=dev`, `vpc_cidr=10.0.0.0/16`, `public_subnets={us-east-2a:10.0.1.0/24, us-east-2b:10.0.2.0/24}`, `private_subnets={us-east-2a:10.0.3.0/24, us-east-2b:10.0.4.0/24}`, `bastion_instance_type=t3.micro`, `key_name=uniops-key` | `vpc_id`, `vpc_cidr`, `public_subnet_ids`, `private_subnet_ids`, `nat_gateway_ip`, `bastion_public_ip`, `bastion_sg_id` | `aws_vpc.main`, `aws_subnet.public` ×2, `aws_subnet.private` ×2, `aws_internet_gateway.main`, `aws_eip.nat`, `aws_nat_gateway.main`, `aws_route_table.public`, `aws_route_table.private`, `aws_route_table_association.public` ×2, `aws_route_table_association.private` ×2, `aws_security_group.internal`, `aws_security_group.bastion`, `aws_instance.bastion`, `tls_private_key.bastion_key`, `aws_key_pair.bastion`, `local_file.bastion_key` |

#### Module `eks` (phase-02) — 13 resources

| Inputs | Outputs | Resources created |
|---|---|---|
| `cluster_version=1.29` (HCL default; live cluster runs 1.30), `vpc_id`, `private_subnets` | `cluster_endpoint`, `cluster_ca_certificate`, `cluster_name`, `node_group_arn`, `oidc_provider_arn`, `node_security_group_id` | `aws_iam_role.cluster` (`uniops-eks-cluster-role`), `aws_iam_role_policy_attachment.cluster_AmazonEKSClusterPolicy`, `aws_iam_role.node` (`uniops-eks-node-role`), 3 node role policy attachments, `aws_security_group.eks_cluster` + 3 SG rules, `aws_eks_cluster.main` (name `uniops-eks-dev`), `data.tls_certificate.eks`, `aws_iam_openid_connect_provider.eks`, `aws_eks_node_group.main` (name `uniops-workers`, m7i-flex.large, min=2/desired=2/max=3, ON_DEMAND), `aws_iam_role.irsa` (`uniops-irsa-role-dev`), 2 IRSA policy attachments, `kubernetes_namespace_v1.uniops` |

#### Module `data` (phase-03) — 16 resources

| Inputs | Outputs | Resources created |
|---|---|---|
| `vpc_id`, `vpc_cidr`, `private_subnets`, `eks_nodes_sg_id`, `kms_key_arn` | `rds_endpoint`, `rds_username`, `db_password` (sensitive), `db_name`, `rds_instance_id`, `rds_instance_arn`, `redis_endpoint`, `redis_auth_token` (sensitive), `redis_secrets_arn`, `efs_id`, `efs_dns_name`, `efs_arn`, `efs_access_point_id`, `backup_bucket_name`, `logs_bucket_name` | `aws_security_group.rds`, `aws_db_subnet_group.main` (`uniops-rds-subnet-group`), `random_password.db_password` (length 16), `aws_db_instance.main` (`uniops-postgres-dev`, postgres 15, db.t3.micro, 20GB, encrypted, KMS), `aws_secretsmanager_secret.db_credentials` + version, `aws_security_group.redis`, `aws_elasticache_subnet_group.main`, `aws_elasticache_parameter_group.main` (redis7 + maxmemory-policy=allkeys-lru), `random_password.redis_token` (length 32, no specials), `aws_elasticache_replication_group.main` (`uniops-redis-dev`, cache.t3.micro, redis 7.1, transit+at-rest encryption), `aws_secretsmanager_secret.redis_credentials` + version, `aws_security_group.efs`, `aws_efs_file_system.main` (`uniops-efs-dev`, encrypted, KMS, 30d→IA), `aws_efs_mount_target.main` ×2, `aws_efs_access_point.main`, `random_string.suffix` (6 chars), `aws_s3_bucket.backups` + version + KMS-SSE + PAB + lifecycle, `aws_s3_bucket.logs` + KMS-SSE + PAB + lifecycle |

#### Module `tools` (phase-04) — 10 resources

| Inputs | Outputs | Resources created |
|---|---|---|
| `vpc_id`, `vpc_cidr`, `public_subnets`, `private_subnets`, `bastion_sg_id`, `key_name=uniops-key` | `monitoring_private_ip`, `sonarqube_private_ip`, `public_instance_1_ip`, `public_instance_2_ip`, `alb_dns_name`, `alb_target_group_arn`, `alb_arn` | `aws_security_group.alb`, `aws_lb.main` (`uniops-alb-dev`, internet-facing ALB), `aws_lb_target_group.main` (HTTP /health), `aws_lb_listener.http` (port 80), `aws_lb_target_group.ml` (port 8080, placeholder), `aws_security_group.public_ec2`, `aws_instance.public_1` + `aws_instance.public_2`, `aws_iam_role.monitoring` + 2 attachments + instance profile, `aws_instance.monitoring` (private), `aws_security_group.sonarqube` + role + instance profile, `aws_instance.sonarqube` (private), `data.aws_ami.amazon_linux_2` (×2) |

#### Module `security` (phase-05) — 17 resources (most are gated by `enable_aws_config=false`)

| Inputs | Outputs | Resources created |
|---|---|---|
| `vpc_id`, `alb_arn`, `eks_cluster_name`, `rds_instance_id`, `rds_instance_arn`, `efs_id`, `efs_arn`, `enable_aws_config=false` | `kms_key_arn`, `waf_web_acl_arn` | `data.aws_caller_identity.current`, `data.aws_iam_policy_document.kms`, `aws_kms_key.uniops` (alias `uniops-dev-key`, rotation on, 7d deletion), `aws_kms_alias.uniops`, `aws_wafv2_web_acl.main` (`uniops-waf-dev`, REGIONAL, 3 rules), `aws_wafv2_web_acl_association.main`, `aws_cloudwatch_log_group.waf`, `aws_backup_vault.main` + plan + selection + role + 2 attachments, `aws_sns_topic.alerts` + email subscription, 3 `aws_cloudwatch_metric_alarm`, `aws_flow_log.main` + log group + role + attachment, **9 AWS Config resources gated on `enable_aws_config`** (recorder, status, delivery channel, role, 4 rules, S3 bucket + SSE) — NOT LIVE, `aws_guardduty_detector.main` + 2 detector features — **COMMENTED OUT in HCL** |

#### Module dependency graph

```
networking ──► eks ──► data ◄── security (KMS)
        └─► tools ───► security (ALB)
        └────────────► data (VPC/subnets) ──► security (RDS/EFS)
                              ↑
                              └─ (circular with security; resolved by phased apply)
```

The `data → kms_key_arn` and `security → rds_instance_arn` create a cycle. The start script's `app_terraform_phased_apply` (start-app-infra.sh:311-342) breaks it by creating `aws_kms_key.uniops` + `aws_kms_alias.uniops` standalone before any module that consumes them.

### 3.3 `infrastructure/terraform` (git-tracked alternate, backend = `prod/terraform.tfstate` in `us-east-1`)

Single-file layout using community modules `terraform-aws-modules/vpc/aws ~> 5.0`, `terraform-aws-modules/eks/aws ~> 20.0`, `terraform-aws-modules/rds/aws ~> 6.0`. Provisions: VPC, EKS, RDS postgres 16, ElastiCache redis, 2 ECR repos, S3 backups bucket, 2 CloudWatch log groups, 2 SGs. Backend points to `prod/terraform.tfstate` in `us-east-1` — **does not match live infra** (which is `us-east-2`).

### 3.4 `infra-backup/infrastructure/terraform/bootstrap` (legacy local-state bootstrap)

`main.tf` provisions the SAME `uniops-terraform-state` bucket but the **bucket name in HCL is `uniops-terraform-state-8j3k9l` (typo'd, does not exist)**. Local state file `terraform.tfstate` (7,882 bytes) is orphan; the real bootstrap state is in S3.

### 3.5 `infra-backup/infrastructure/terraform/shared` (backend config files, not a module)

Three files duplicate backend declarations: `backend.tf` says `key=app/terraform.tfstate`; `provider.tf` says `key=terraform.tfstate`. This is a latent bug in the legacy tree.

---

## 4. Kubernetes Workloads

All in namespace `uniops` (prod overlay) or `uniops-dev` (dev overlay). Live pin: dev overlay.

| Kind | Name | Namespace | Image | Ports | Key Config |
|------|------|-----------|-------|-------|-----------|
| **Deployment** | `backend` | uniops | `momenpanda/uniops-backend:latest` (DockerHub) | 8000 | replicas=2, RollingUpdate maxSurge=1/maxUnavailable=0, serviceAccount `uniops-backend`, initContainers wait-for-postgres + wait-for-redis (busybox:1.36, runAsNonRoot, cap drop ALL), uvicorn `--workers 2`, envFrom configMap+secret, REDIS_URL/CELERY_BROKER_URL/CELERY_RESULT_BACKEND override with `redis://:PWD@redis:6379/{0,1,2}`, DATABASE_URL `postgresql+asyncpg://...@postgres:5432/uniops_db`, startupProbe `/api/v1/health` 18×5s, readiness/liveness same path, volumeMounts models-storage (RWX PVC) + logs-storage (emptyDir), resource req 250m/512Mi lim 1000m/1Gi, prometheus scrape :8000/metrics |
| **Deployment** | `celery-worker` | uniops | `momenpanda/uniops-backend:latest` | none | replicas=2, serviceAccount `uniops-worker`, initContainers wait-for-redis+postgres, `celery -A app.tasks.worker worker --pool=prefork --concurrency=4 --max-tasks-per-child=1 -Q default,scans --without-heartbeat --without-gossip`, **liveness probe `pgrep -f 'celery.*worker'`** (PRESERVED EXACTLY per start script), volumes models-pvc + emptyDir, req 500m/512Mi lim 2000m/2Gi, terminationGracePeriodSeconds=60 |
| **Deployment** | `celery-beat` | uniops | `momenpanda/uniops-backend:latest` | none | replicas=1, strategy=Recreate (single instance), `celery -A app.tasks.worker beat --scheduler celery.beat.PersistentScheduler --schedule /app/celerybeat-schedule/celerybeat-schedule`, volumeMounts beat-schedule (PVC 100Mi RWO) + beat-tmp (emptyDir) |
| **Deployment** | `frontend` | uniops | `momenpanda/uniops-frontend:latest` (DockerHub — not the ECR-pinned `fix-2026-06-03-full-unwrap` the start script asserts) | 80 | replicas=2, RollingUpdate maxSurge=1/maxUnavailable=0, serviceAccount `uniops-frontend` (token not automounted), securityContext runAsUser/Group=101 (nginx alpine), nginx on :80, cap drop ALL + add NET_BIND_SERVICE, readOnlyRootFilesystem=true, tmpfs volumes nginx-cache/nginx-run/nginx-tmp, startupProbe+readiness+liveness `/health` |
| **StatefulSet** | `postgres` | uniops | `postgres:16-alpine` | 5432 | replicas=1, headless Service `postgres`, securityContext runAsUser/Group=999 (postgres alpine), env POSTGRES_USER/PASSWORD/DB from `uniops-secrets`, PGDATA=/var/lib/postgresql/data/pgdata, probes `pg_isready` (startup 12×5s=60s, readiness 6, liveness 3), volumeClaimTemplate 20Gi RWO, resource req 250m/256Mi lim 1000m/1Gi, terminationGracePeriodSeconds=60 |
| **StatefulSet** | `redis` | uniops | `redis:7-alpine` | 6379 | replicas=1, headless Service `redis`, securityContext runAsUser/Group=999, `--requirepass $REDIS_PASSWORD --appendonly yes --appendfsync everysec --maxmemory 256mb --maxmemory-policy allkeys-lru --save 60 1000 --save 300 10 --bind 0.0.0.0 --protected-mode no --loglevel notice`, probes `redis-cli -a $REDIS_PASSWORD ping`, volumeClaimTemplate 5Gi RWO, resource req 100m/128Mi lim 500m/512Mi |
| **Job** | `uniops-migrate` | uniops | `momenpanda/uniops-backend:latest` | none | ArgoCD PreSync hook, backoffLimit=3, ttlSecondsAfterFinished=300, initContainer `wait-for-postgres` (busybox), command `alembic upgrade head`, envFrom configMap+secret, DATABASE_URL `postgresql+asyncpg://...@postgres:5432/uniops_db` |
| **Service** | `backend` | uniops | — | 80→8000 | ClusterIP, name=http, selector app=backend |
| **Service** | `frontend` | uniops | — | 80→80 | ClusterIP, name=http, selector app=frontend |
| **Service** | `postgres` | uniops | — | 5432 | headless (clusterIP=None), selector app=postgres |
| **Service** | `redis` | uniops | — | 6379 | headless (clusterIP=None), selector app=redis |
| **Ingress** | `uniops-ingress` | uniops | nginx-ingress class | — | host=uniops.local, paths `/api` `/ws` `/webhooks` → backend:80, `/` → frontend:80, annotations: proxy-read-timeout=3600, proxy-send-timeout=3600, proxy-body-size=50m, http-version=1.1, **no TLS** (TLS added by prod overlay) |
| **HPA** | `backend-hpa` | uniops | — | — | min=2, max=8, CPU 70% + mem 80%, scaleUp 60s+2pods/60s Max, scaleDown 300s+1pod/60s |
| **HPA** | `celery-worker-hpa` | uniops | — | — | min=2, max=6, CPU 75%, scaleUp 30s+2pods/30s Max, scaleDown 600s+1pod/60s |
| **PDB** | `backend-pdb` | uniops | — | — | minAvailable=1, selector app=backend |
| **ConfigMap** | `uniops-config` | uniops | — | — | APP_NAME=UniOps, APP_ENV=production (overridden to development in dev overlay), DEBUG=false, LOG_LEVEL=INFO, CORS_ORIGINS=`["https://uniops.example.com"]` (overridden), FRONTEND_URL=https://uniops.example.com, DATABASE_POOL_SIZE=10, CELERY_*, PYTHONUNBUFFERED=1, EMAIL_FROM=noreply@uniops.io |
| **Secret** | `uniops-secrets` | uniops | — | — | Template (REPLACE_WITH_*) — populated by setup-secrets.sh with random `SECRET_KEY`/`JWT_SECRET_KEY` (hex 32) + `POSTGRES_PASSWORD` (32) + `REDIS_PASSWORD` (32), plus optional integration tokens |
| **ServiceAccount** | `uniops-backend` | uniops | — | — | automount token, RoleBinding to `uniops-k8s-reader` (read pods/logs/services/endpoints/configmaps/events/deployments/rs/sts/ds/jobs/cronjobs/hpa/ingresses) |
| **ServiceAccount** | `uniops-worker` | uniops | — | — | automount token, RoleBinding to `uniops-k8s-reader` |
| **ServiceAccount** | `uniops-frontend` | uniops | — | — | no automount, no K8s access |
| **Role + 2 RoleBindings** | `uniops-k8s-reader` | uniops | — | — | Namespace-scoped read-only |
| **NetworkPolicy** | `allow-internal` | uniops | — | — | Default-deny NOT set (this is allow-only for pods + ingress-nginx); egress: pods, kube-dns 53, external 80+443 (excluding RFC1918) |
| **PersistentVolumeClaim** | `models-pvc` | uniops | — | — | ReadWriteMany, 2Gi, no StorageClass set in base (overlay-specific) |
| **PersistentVolumeClaim** | `celerybeat-pvc` | uniops | — | — | ReadWriteOnce, 100Mi |
| **ResourceQuota** | `uniops-quota` | uniops | — | — | requests.cpu=10, requests.memory=20Gi, limits.cpu=20, limits.memory=40Gi |
| **LimitRange** | `uniops-limits` | uniops | — | — | Container default 500m/256Mi, defaultRequest 100m/128Mi |
| **Namespace** | `uniops` | — | — | — | Labels: app.kubernetes.io/name=uniops, managed-by=kustomize |
| **Namespace** | `uniops-dev` | — | — | — | dev overlay (not prod) |
| **ClusterIssuer** | `letsencrypt-prod` | — | — | — | cert-manager, ACME HTTP-01, server `https://acme-v02.api.letsencrypt.org/directory`, email `ops@yourdomain.com` (prod only) |
| **ServiceMonitor** | `uniops-backend` | monitoring | — | — | Selector `app.kubernetes.io/name: backend` in `uniops` ns, port=http, /metrics, 15s interval |
| **PrometheusRule** | `uniops-alerts` | monitoring | — | — | 4 groups: availability (BackendDown/PostgresDown/RedisDown/CeleryWorkerDown), errors (>5% 5xx / >20% 5xx), latency (p95>2s / p99>5s), k8s (crashloop/PVC>85%/HPA-maxed) |

### Dev overlay (the live overlay)
Image tags overridden to `:dev`; ConfigMap merged with `APP_ENV=development, DEBUG=true, LOG_LEVEL=DEBUG, CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","http://uniops.local"], FRONTEND_URL=http://uniops.local`. Namespace overridden to `uniops-dev`.

### Prod overlay
Image tags pinned to `1.0.0` (`ghcr.io/your-org/uniops-backend` / `…-frontend` — different registry!). Backend replicas=3 (req 500m/1Gi lim 2/2Gi), Celery worker replicas=3 (req 500m/1Gi lim 2/2Gi), HPA backend 3-10, HPA worker 3-8, TLS via cert-manager on `uniops.yourdomain.com`, force-ssl-redirect, server-snippet adds HSTS, configuration-snippet adds `Upgrade`/`Connection: upgrade` headers for WebSockets.

---

## 5. Network & Security Architecture

### 5.1 VPC layout

| Subnet | AZ | CIDR | Type | Used by |
|---|---|---|---|---|
| `subnet-05320c4c512884360` | us-east-2a | 10.0.1.0/24 | public | ALB, NAT Gateway, public-1 EC2 |
| `subnet-0f7050d87d38ff446` | us-east-2b | 10.0.2.0/24 | public | ALB, public-2 EC2 |
| `subnet-0bf53bbc9eb9a6a21` | us-east-2a | 10.0.3.0/24 | private | EKS node group, RDS, Redis, EFS mount target, monitoring+sonarqube EC2 |
| `subnet-01f39508548a5e1d4` | us-east-2b | 10.0.4.0/24 | private | EKS node group, EFS mount target |

VPC `vpc-0a0073d556bd28a55` (`uniops-saas-dev-vpc`), CIDR `10.0.0.0/16`, DNS hostnames + DNS support enabled, main route table `rtb-0e81e0d6fc0b8e1c9`, default NACL `acl-0f9b5bd894844948b`.

### 5.2 Routing

- **Public subnets** → `aws_route_table.public` (route `0.0.0.0/0` → IGW `uniops-igw`)
- **Private subnets** → `aws_route_table.private` (route `0.0.0.0/0` → NAT Gateway `uniops-nat-gw` in us-east-2a public subnet)

### 5.3 Security Group rules

| SG | Ingress | Egress |
|---|---|---|
| `bastion-sg` | TCP 22 from `0.0.0.0/0` | all to `0.0.0.0/0` |
| `vpc-internal` | all from VPC CIDR `10.0.0.0/16` | all to `0.0.0.0/0` |
| `eks-cluster-sg` | (none in HCL) | all to `0.0.0.0/0` |
| `eks-worker-sg` | all from same SG (intra-node), TCP 1025-65535 from `eks-cluster-sg` | all to `0.0.0.0/0` |
| `rds-sg` | TCP 5432 from `eks-worker-sg` AND from VPC CIDR | all to `0.0.0.0/0` |
| `redis-sg` | TCP 6379 from `eks-worker-sg` AND from VPC CIDR | all to `0.0.0.0/0` |
| `efs-sg` | TCP 2049 from `eks-worker-sg` AND from VPC CIDR | all to `0.0.0.0/0` |
| `alb-sg` | TCP 80+443 from `0.0.0.0/0` | all to VPC CIDR |
| `public-ec2-sg` | TCP 80+443 from `alb-sg`, TCP 22 from `bastion-sg` | all to `0.0.0.0/0` |
| `monitoring-sg` | TCP 9090 (Prometheus) + TCP 3000 (Grafana) from VPC CIDR, TCP 22 from `bastion-sg` | all to `0.0.0.0/0` |
| `sonarqube-sg` | TCP 9000 from VPC CIDR, TCP 22 from `bastion-sg` | all to `0.0.0.0/0` |
| `eks-cluster-sg` (cluster control plane direction) | TCP 443 from `eks-worker-sg` (separate rule on cluster SG) | — |

### 5.4 IAM roles

| Role | Trust | Managed policies | Purpose |
|---|---|---|---|
| `uniops-eks-cluster-role` | `eks.amazonaws.com` | `AmazonEKSClusterPolicy` | EKS control plane |
| `uniops-eks-node-role` | `ec2.amazonaws.com` | `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly` | EKS workers |
| `uniops-irsa-role-dev` | EKS OIDC federated; condition: `sub = system:serviceaccount:uniops:uniops-sa` | `AmazonS3ReadOnlyAccess`, `SecretsManagerReadWrite` | Pod-to-AWS via IRSA |
| `uniops-monitoring-role` | `ec2.amazonaws.com` | `CloudWatchAgentServerPolicy`, `AmazonEC2ReadOnlyAccess` | Monitoring EC2 |
| `uniops-sonarqube-role` | `ec2.amazonaws.com` | (none) | SonarQube EC2 |
| `uniops-public-ec2-role` | `ec2.amazonaws.com` | (none) | Public EC2 |
| `uniops-backup-role` | `backup.amazonaws.com` | `AWSBackupServiceRolePolicyForBackup`, `…ForRestores` | AWS Backup |
| `uniops-vpc-flow-log-role` | `vpc-flow-logs.amazonaws.com` | `CloudWatchLogsFullAccess` | VPC flow log delivery |
| `uniops-config-role` (gated on `enable_aws_config=true`) | `config.amazonaws.com` | `service-role/AWSConfigRole` | AWS Config recorder (NOT LIVE) |

### 5.5 KMS usage

- Master key: `alias/uniops-dev-key`, rotation enabled, 7-day deletion window.
- Custom IAM policy grants `kms:*` to account root and `kms:Encrypt/Decrypt/ReEncrypt*/GenerateDataKey*/DescribeKey` to: `eks.amazonaws.com`, `rds.amazonaws.com`, `ec2.amazonaws.com`.
- Consumers: `aws_db_instance.main`, `aws_efs_file_system.main`, `aws_s3_bucket.backups` SSE, `aws_s3_bucket.logs` SSE, `aws_secretsmanager_secret.db_credentials`, `aws_backup_vault.main`.

### 5.6 WAF rules

Web ACL `uniops-waf-dev` (REGIONAL, attached to ALB):

| Priority | Name | Type | Action | Detail |
|---|---|---|---|---|
| (default) | — | Default | Allow | |
| 1 | `AWSManagedRulesCommonRuleSet` | Managed | (override_action: none, the managed rule decides) | AWS Common Rule Set (OWASP top 10) |
| 2 | `RateLimit` | Rate-based | Block | 2000 requests / 5 min per IP |
| 3 | `GeoBlock` | Not(Geo) | Block | Allow only EG, US; everything else is implicitly blocked |

WAF logs flow to CloudWatch Log Group `aws-waf-logs-uniops` (30d retention).

### 5.7 Network flow

```
Internet → [0.0.0.0/0]
  ↓
WAFv2 WebACL (uniops-waf-dev, attached to ALB)
  ↓ (80/443)
Application Load Balancer (uniops-alb-dev, in 2 public subnets)
  ↓ HTTP target group uniops-alb-tg-dev
Kubernetes NodePort → Service :80 (backend/frontend)
  ↓ (port 8000 for backend, port 80 for frontend)
Pod (Backend FastAPI on 0.0.0.0:8000 OR Frontend nginx on 0.0.0.0:80)
  ↓
Backend → RDS (in-cluster postgres:5432 OR aws RDS on 5432 — both are reachable)
Backend → ElastiCache Redis (in-cluster redis:6379 OR aws Redis on 6379)
Backend → EFS (models-pvc, RWX, via EFS CSI driver)
  ↓
NAT Gateway (for egress to internet: 80/443)
```

K8s network flow is more accurate for what's actually running:

```
Internet → ALB (uniops-alb-dev) on :80
  ↓
nginx-ingress-controller (pod in ingress-nginx namespace, k8s Service type=LoadBalancer)
  ↓ matches Ingress uniops-ingress
  ├── /api/*   → Service backend:80 (port name http) → Pod backend:8000
  ├── /ws/*    → Service backend:80 → Pod backend:8000
  ├── /webhooks/* → Service backend:80 → Pod backend:8000
  └── /*       → Service frontend:80 → Pod frontend:80
                                    │
                                    ├── initContainer wait-for-postgres (busybox nc -z postgres 5432)
                                    ├── initContainer wait-for-redis (busybox nc -z redis 6379)
                                    └── Backend reads ConfigMap uniops-config + Secret uniops-secrets
                                                  ├── DATABASE_URL=postgresql+asyncpg://uniops:PWD@postgres:5432/uniops_db
                                                  ├── REDIS_URL=redis://:PWD@redis:6379/0
                                                  ├── CELERY_BROKER_URL=redis://:PWD@redis:6379/1
                                                  └── CELERY_RESULT_BACKEND=redis://:PWD@redis:6379/2
```

---

## 6. Data Flow

### 6.1 Application → PostgreSQL

**Live: in-cluster StatefulSet, NOT RDS.**
- The K8s StatefulSet `postgres` (image `postgres:16-alpine`, PVC 20Gi) listens on `postgres.uniops.svc.cluster.local:5432` (headless Service).
- Backend connects via `DATABASE_URL=postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres:5432/$(POSTGRES_DB)`.
- The `aws_db_instance.uniops-postgres-dev` exists in AWS (RDS postgres 15.17, endpoint `uniops-postgres-dev.czow22y627dw.us-east-2.rds.amazonaws.com:5432`) but is **NOT the live consumer** — the in-cluster StatefulSet serves all traffic. The RDS is provisioned by the legacy 5-phase Terraform and is reachable but unused by the running backend.
- Credentials source: `Secret uniops-secrets` → `POSTGRES_USER=uniops`, `POSTGRES_PASSWORD` (random 32-char), `POSTGRES_DB=uniops_db` (setup-secrets.sh generates with `openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32`).
- The RDS instance has its OWN credentials stored in AWS Secrets Manager (`uniops/db-credentials-dev`) generated by Terraform `random_password.db_password` (length 16, special chars `!#$%&*()-_=+[]{}<>:?`).

### 6.2 Application → Redis

**Live: in-cluster StatefulSet, NOT ElastiCache.**
- The K8s StatefulSet `redis` (image `redis:7-alpine`, PVC 5Gi, AOF persistence) listens on `redis.uniops.svc.cluster.local:6379` (headless Service).
- 3 logical DBs: DB 0 = app cache (`REDIS_URL=redis://:PWD@redis:6379/0`), DB 1 = Celery broker (`CELERY_BROKER_URL=redis://:PWD@redis:6379/1`), DB 2 = Celery results (`CELERY_RESULT_BACKEND=redis://:PWD@redis:6379/2`).
- Redis auth via `--requirepass $REDIS_PASSWORD` (env from Secret).
- The `aws_elasticache_replication_group.uniops-redis-dev` exists (cache.t3.micro, redis 7.1, transit+at-rest encryption, KMS) at `master.uniops-redis-dev.wenqsd.use2.cache.amazonaws.com:6379` but is **NOT the live consumer**.
- ElastiCache auth token is in AWS Secrets Manager `uniops/redis-credentials-dev`, generated by `random_password.redis_token` (length 32, no specials — Redis constraint).

### 6.3 Application → EFS

- EFS filesystem `fs-0f6567c976ebd2349` (`uniops-efs-dev`) with one access point `uniops-efs-ap` (POSIX uid/gid 1000, root `/data`).
- The `models-pvc` in `k8s/base/backend.yaml` is the request point: 2Gi, RWX. The K8s manifests **comment out** the StorageClass in base (`# storageClassName: efs-sc # AWS EKS`); the prod overlay also comments it out. In practice the in-cluster StatefulSets use the **cluster-default StorageClass (`local-path`)** for their data PVCs — `models-pvc` is intended to bind via EFS CSI driver in prod, but as-shipped it has no StorageClass set.
- EFS CSI driver: installed/managed by start-app-infra.sh Phase 2 (`aws-efs-csi-driver` Helm chart, service account `efs-csi-controller-sa`).
- Mount targets: one per private subnet.

### 6.4 Secrets flow

```
Operator runs: bash k8s/scripts/setup-secrets.sh dev
  ↓
Generates random values via openssl
  ↓
kubectl create secret generic uniops-secrets --from-literal=... --dry-run=client -o yaml | kubectl apply -f -
  ↓
Secret uniops-secrets in namespace uniops-dev
  ↓
Pod references via env.valueFrom.secretKeyRef (e.g. POSTGRES_PASSWORD, REDIS_PASSWORD, SECRET_KEY, JWT_SECRET_KEY)
```

The infra-backup HCL planned a different path via **AWS Secrets Manager + IRSA**: Pod SA `uniops:uniops-sa` would assume `uniops-irsa-role-dev` (federated with EKS OIDC) and call `secretsmanager:GetSecretValue` to fetch RDS/Redis credentials. This is wired in HCL but the K8s manifests do NOT use service account `uniops-sa`; they read K8s Secrets directly. The IRSA role exists in AWS but is not consumed by any live workload.

### 6.5 ConfigMap / ConfigMap override

`ConfigMap uniops-config` is the central non-sensitive config. Kustomize `configMapGenerator` in dev overlay **merges** (not replaces) so both `APP_ENV=production` (from base) and `APP_ENV=development` (from dev) end up in the same ConfigMap, with the overlay's value winning per the merge strategy (last write wins for duplicates).

---

## 7. Lifecycle Scripts

### 7.1 `start-app-infra.sh` (688 lines, v3.0)

**Purpose:** App-layer isolated startup. Re-apply, verify, or re-create the application layer of UniOps without touching the bootstrap layer.

**Phases:**

| # | Phase | What it does | Safety checks |
|---|---|---|---|
| 0 | Prerequisites | Verifies `aws`, `kubectl`, `helm`, `jq`, `openssl` are installed; verifies AWS credentials with `aws sts get-caller-identity` | Fails (exit 1) on missing tools / invalid creds |
| — | Bootstrap isolation guard | Refuses to run if `cwd` is inside `terraform/bootstrap/`, requires both ECR repos to exist, verifies bootstrap dir exists | Hard fail |
| App Terraform phased apply | Only when EKS is missing. Copies `infra-backup/infrastructure/terraform` → `terraform/app/`, patches `shared/backend.tf` to point at `uniops-terraform-state` / `app/terraform.tfstate`, runs `terraform init` then phased `apply`: networking → KMS key (cycle break) → EKS → data → tools → security → global sync | Verifies bootstrap S3 + DDB exist before starting |
| 1 | EKS Provisioning | Detects cluster via `aws eks list-clusters` filtered on `uniops`. If found, just configures kubeconfig. If missing and `--no-create` not set, runs the phased Terraform apply above. After apply, waits for `cluster-active` and configures kubeconfig (12×10s attempts). | Refuses to create if `--no-create` is set |
| 2 | Cluster add-ons (Helm) | `helm repo add` + `helm install|upgrade` for `aws-efs-csi-driver` (kube-system) and `ingress-nginx` (ingress-nginx namespace). Waits for `efs-csi-controller` + `efs-csi-node` pods and `ingress-nginx-controller` deploy. Verifies `IngressClass nginx` exists. | `--skip-helm` skips. Fails (exit 3) on timeout. |
| 3 | In-cluster StatefulSets | `kubectl apply -f k8s/base/postgres.yaml` + `redis.yaml`. Waits for `app=postgres` and `app=redis` pods to be Running. Asserts default StorageClass is `local-path` (warns otherwise). | Fails (exit 4) on missing manifest files |
| 4 | Namespace + manifests | `kubectl create namespace uniops --dry-run=client -o yaml | kubectl apply -f -`, then `kubectl apply -k k8s/base`, then `kubectl apply -k k8s/overlays/dev` | `--dry-run` skips; Fails (exit 4) on missing dirs |
| 5 | Secrets | Refreshing strategy: if `uniops-secrets` exists, **PRESERVE** (no rotation). If missing, create with random SECRET_KEY/JWT_SECRET_KEY via `openssl rand -hex 32`. If `dockerhub-secret` exists, PRESERVE; else create placeholder. Always refresh `ecr-pull-secret` with current `aws ecr get-login-password` (12h TTL). | Existing secret wins |
| 6 | Image rollout | Asserts live deployment images match the pinned values: frontend = `180840261837.dkr.ecr.us-east-2.amazonaws.com/uniops-frontend:fix-2026-06-03-full-unwrap`, backend = `momenpanda/uniops-backend:latest`. Then `kubectl rollout restart deployment/{backend,celery-worker,celery-beat,frontend}` and waits for each (300s timeout). | Fails (exit 4) on image drift |
| 7 | Health checks | Pod readiness, PVCs Bound, frontend Service targetPort=8080, celery-worker liveness probe contains `pgrep -f 'celery.*worker'`. Final summary of any failures. | Fails (exit 5) on any health check failure |

**Flags:**

| Flag | Effect |
|---|---|
| `--skip-helm` | Skip Phase 2 (don't upgrade EFS CSI / ingress-nginx) |
| `--skip-images` | Skip Phase 6 (don't trigger rollouts) |
| `--skip-terraform` | Skip the phased `terraform apply`; fall back to connectivity-only mode (fails if no EKS cluster exists) |
| `--no-create` | Fail if EKS cluster doesn't exist (legacy strict mode, default is auto-create) |
| `--dry-run` | Print all actions, make no changes |
| `-h`, `--help` | Show header (lines 2-50) and exit |

**Exit codes:** 0=success, 1=prereq missing, 2=EKS unreachable, 3=add-on fail, 4=rollout fail, 5=health fail.

**Static config (in-script constants):**
- `TERRAFORM_APP_DIR=$REPO_ROOT/terraform/app` (does NOT exist yet — will be created by Phase 1)
- `TERRAFORM_APP_STATE_BUCKET=uniops-terraform-state`
- `TERRAFORM_APP_STATE_KEY=app/terraform.tfstate`
- `TERRAFORM_APP_LOCK_TABLE=uniops-terraform-locks`
- `TERRAFORM_APP_SOURCE=$REPO_ROOT/infra-backup/infrastructure/terraform`
- `FRONTEND_IMAGE=180840261837.dkr.ecr.us-east-2.amazonaws.com/uniops-frontend:fix-2026-06-03-full-unwrap` ← **NOT what k8s/base/frontend.yaml actually uses** (which is `momenpanda/uniops-frontend:latest`)
- `BACKEND_IMAGE_DOCKERHUB=momenpanda/uniops-backend:latest` ← matches k8s/base/backend.yaml
- `FRONTEND_TARGET_PORT=8080` ← **NOT** what k8s/base/frontend.yaml declares (`containerPort: 80`)
- `CELERY_PROBE="pgrep -f 'celery.*worker'"` ← matches k8s/base/celery.yaml

### 7.2 `destroy-app-infra.sh` (772 lines, v1.0)

**Purpose:** App-layer teardown. Removes in-cluster K8s resources, optionally runs `terraform destroy` against the app-layer state. Never touches the bootstrap layer.

**Phases:**

| # | Phase | What it does | Safety checks |
|---|---|---|---|
| 0 | Prerequisites | Verifies `aws`, `kubectl`, `helm`, `jq`, `openssl`, `terraform` | Fails (exit 1) on missing tools |
| — | Bootstrap isolation guard | Refuses if cwd is in `terraform/bootstrap/`. Refuses if `TERRAFORM_APP_STATE_KEY == bootstrap/*`. Pre-flights the app-layer state file for any bootstrap resource addresses. Asserts negative: ECR repos exist, state bucket exists, bootstrap state keys exist, DDB lock table exists, EKS cluster exists, RDS exists, Redis cluster exists, EFS exists. | Hard fail (exit 1 or 5) |
| 1 | Destruction confirmation | Unless `--yes`, prompts for typed phrase `destroy-app-infra` | Aborts (exit 2) on mismatch |
| 2 | Helm uninstall | `helm uninstall ingress-nginx` and `helm uninstall aws-efs-csi-driver` (`--skip-helm` not applicable; this is destroy not start) | Fails (exit 3) on helm error |
| 3 | StatefulSets | `kubectl delete statefulset postgres redis -n uniops --ignore-not-found` (waits for them to be gone) | |
| 4 | PVCs | `kubectl delete pvc -n uniops --all` unless `--keep-pvcs` | |
| 5 | Secrets | `kubectl delete secret uniops-secrets -n uniops` unless `--keep-secrets` (always deletes dockerhub-secret and ecr-pull-secret) | |
| 6 | Delete namespace | `kubectl delete namespace uniops --ignore-not-found` and wait | Fails (exit 4) on timeout |
| 6.5 | App Terraform destroy | `discover_app_terraform_dir` finds the app layer (excludes `terraform/bootstrap`). Pre-flight grep of `terraform.tfstate` for any of the 7 `BOOTSTRAP_RESOURCE_TYPES`. Refuses to run if found. Then `terraform init -reconfigure`, `terraform plan -destroy` (preview, `tee /tmp/tf-destroy-plan.txt`), `terraform destroy -auto-approve`. | Fails (exit 1) on state-key/region/bucket mismatch, Fails (exit 6) on init/destroy error |
| 7a | Verify protected | Asserts ECR repos still exist, state bucket still exists, bootstrap state key still exists, DDB lock table still exists. | Fails (exit 1) on any negative |
| 7b | Verify app destroyed | `aws eks describe-cluster --name uniops-eks-dev` → should fail (SUCCESS). RDS / Redis / EFS are *not* in scope; if they still exist they're noted as out-of-band. | Red FAILURE panel if EKS still present |

**Flags:**

| Flag | Effect |
|---|---|
| `--yes` | Skip interactive confirmation |
| `--dry-run` | Print all actions, make no changes |
| `--keep-pvcs` | Skip Phase 4 (preserve PVCs / data) |
| `--keep-secrets` | Skip Phase 5 uniops-secrets delete |
| `--skip-terraform` | Skip Phase 6.5 (only delete k8s resources, NOT EKS / app AWS) |
| `--keep-terraform-state` | After `terraform destroy`, do not delete the state file from S3 |

**Exit codes:** 0=success, 1=prereq/safety, 2=user aborted, 3=helm fail, 4=namespace fail, 5=protected-resource check fail, 6=terraform fail.

**Static config (in-script constants):**
- Same `TERRAFORM_APP_DIR`, `TERRAFORM_APP_STATE_BUCKET`, `TERRAFORM_APP_STATE_KEY`, `TERRAFORM_APP_LOCK_TABLE` as start-app-infra.sh.
- `BOOTSTRAP_RESOURCE_TYPES=("aws_s3_bucket.terraform_state" "aws_s3_bucket_versioning.terraform_state" "aws_s3_bucket_server_side_encryption_configuration.terraform_state" "aws_s3_bucket_public_access_block.terraform_state" "aws_dynamodb_table.terraform_locks" "aws_ecr_repository.backend" "aws_ecr_repository.frontend")` — scanned in app-layer state for any contamination.
- `PROTECTED_ECR_REPOS=("uniops-backend" "uniops-frontend")`
- `PROTECTED_S3_BUCKET=uniops-terraform-state`
- `PROTECTED_DDB_TABLE=uniops-terraform-locks`
- `PROTECTED_EKS_CLUSTER_PREFIX=uniops`
- `PROTECTED_RDS_ID=uniops-postgres-dev`
- `PROTECTED_REDIS_CLUSTER=uniops-redis-dev`
- `PROTECTED_EFS_PREFIX=fs-`

---

## 8. Mermaid Diagram — Full Architecture

```mermaid
graph TD
  %% ── External ─────────────────────────────────────────────────
  Internet((Internet)):::external
  Operator[DevOps Operator]:::external

  %% ── AWS account 180840261837 / us-east-2 ──────────────────────
  subgraph AWS["AWS Account 180840261837 — us-east-2"]
    WAF["WAFv2 Web ACL<br/>uniops-waf-dev<br/>(Common + RateLimit + Geo)"]:::security
    ALB["Application Load Balancer<br/>uniops-alb-dev<br/>:80 :443 (ALB-SG)"]:::network

    subgraph VPC["VPC uniops-saas-dev-vpc (10.0.0.0/16)"]
      IGW["Internet Gateway<br/>uniops-igw"]:::network
      NAT["NAT Gateway<br/>uniops-nat-gw + EIP"]:::network
      subgraph Public["Public subnets"]
        PubA["subnet-05320c4c512884360<br/>us-east-2a 10.0.1.0/24"]:::subnet
        PubB["subnet-0f7050d87d38ff446<br/>us-east-2b 10.0.2.0/24"]:::subnet
        Bastion["Bastion EC2<br/>uniops-bastion (t3.micro)"]:::ec2
        PubEC2_1["public-1 EC2 (nginx)"]:::ec2
        PubEC2_2["public-2 EC2 (nginx)"]:::ec2
      end
      subgraph Private["Private subnets"]
        PrivA["subnet-0bf53bbc9eb9a6a21<br/>us-east-2a 10.0.3.0/24"]:::subnet
        PrivB["subnet-01f39508548a5e1d4<br/>us-east-2b 10.0.4.0/24"]:::subnet
        subgraph EKS["EKS Cluster uniops-eks-dev (K8s 1.30)"]
          NG["Node Group uniops-workers<br/>(m7i-flex.large ×2-3)"]:::compute
          subgraph NSUniops["Namespace uniops"]
            BE[Deployment backend ×2]:::pod
            CW[Deployment celery-worker ×2]:::pod
            CB[Deployment celery-beat ×1]:::pod
            FE[Deployment frontend ×2]:::pod
            PG[StatefulSet postgres<br/>postgres:16-alpine]:::data
            RD[StatefulSet redis<br/>redis:7-alpine]:::data
            MJ[Job uniops-migrate]:::pod
            Ing["Ingress uniops-ingress<br/>(host=uniops.local)"]:::k8s
            SvcBE[Service backend:80]:::k8s
            SvcFE[Service frontend:80]:::k8s
            SvcPG[Service postgres:5432 headless]:::k8s
            SvcRD[Service redis:6379 headless]:::k8s
            PVC1[PVC models-pvc 2Gi RWX]:::storage
            PVC2[PVC postgres-data 20Gi]:::storage
            PVC3[PVC redis-data 5Gi]:::storage
            PVC4[PVC celerybeat-pvc 100Mi]:::storage
            SA1[SA uniops-backend]:::rbac
            SA2[SA uniops-worker]:::rbac
            SA3[SA uniops-frontend]:::rbac
            HPA1[HPA backend-hpa 2-8]:::k8s
            HPA2[HPA celery-worker-hpa 2-6]:::k8s
            PDB1[PDB backend-pdb minAvail=1]:::k8s
            NP1[NetworkPolicy allow-internal]:::k8s
            CM[ConfigMap uniops-config]:::k8s
            SEC[Secret uniops-secrets]:::k8s
          end
          subgraph NSIngress["Namespace ingress-nginx"]
            NIC[Deployment ingress-nginx-controller]:::pod
          end
          subgraph NSKubeSystem["Namespace kube-system"]
            EFSD[aws-efs-csi-driver]:::pod
          end
        end
        RDS["RDS uniops-postgres-dev<br/>postgres 15.17 db.t3.micro"]:::data
        ECache["ElastiCache uniops-redis-dev<br/>redis 7.1 cache.t3.micro"]:::data
        EFS["EFS fs-0f6567c976ebd2349<br/>uniops-efs-dev (KMS)"]:::data
        MonEC2["EC2 uniops-monitoring-dev"]:::ec2
        SonarEC2["EC2 uniops-sonarqube-dev"]:::ec2
      end
    end

    KMS["KMS alias/uniops-dev-key<br/>(rotation on)"]:::security
    S3State["S3 uniops-terraform-state<br/>(versioned, AES256)"]:::s3
    S3Back["S3 uniops-backups-dev-v22t87"]:::s3
    S3Logs["S3 uniops-logs-dev-storage"]:::s3
    DDB["DynamoDB uniops-terraform-locks"]:::security
    ECR_B["ECR uniops-backend"]:::s3
    ECR_F["ECR uniops-frontend"]:::s3
    SMDB["Secrets Manager<br/>uniops/db-credentials-dev"]:::security
    SMR["Secrets Manager<br/>uniops/redis-credentials-dev"]:::security
    Backup["AWS Backup<br/>uniops-backup-plan-dev (daily 5AM)"]:::security
    SNS["SNS uniops-alerts-dev"]:::security
    CWAlarms["CloudWatch Alarms ×3<br/>(EKS CPU / ALB 5XX / RDS storage)"]:::security
    FlowLog["VPC Flow Log → CW<br/>uniops-vpc-flow-logs-dev"]:::security
    WAFLog["CW Log Group<br/>aws-waf-logs-uniops"]:::security
  end

  Internet --> WAF --> ALB
  ALB -.->|target type=ip<br/>NGINX ingress-nginx| NIC
  NIC --> Ing
  Ing -- /api, /ws, /webhooks --> SvcBE --> BE
  Ing -- / --> SvcFE --> FE
  BE --> CM
  BE --> SEC
  BE --> SvcPG --> PG
  BE --> SvcRD --> RD
  BE --> PVC1
  PG --> PVC2
  RD --> PVC3
  CB --> PVC4
  CW --> SvcRD
  CW --> SvcPG
  BE --> MJ
  BE -- IRSA SA:uniops-backend --> KMS
  BE -- IRSA SA:uniops-backend --> SMDB
  NG -- mount --> EFS
  PubEC2_1 -.->|via ALB| ALB
  PubEC2_2 -.->|via ALB| ALB
  Bastion -.->|SSH jump| PubEC2_1
  Bastion -.->|SSH jump| MonEC2
  Bastion -.->|SSH jump| SonarEC2
  NAT --> IGW
  Internet --> NAT
  Internet --> IGW
  ALB -.-> ALB_SG[Security Groups]
  RDS -.->|5432| RDS_SG
  ECache -.->|6379| ECache_SG
  EFS -.->|2049| EFS_SG
  ECR_B -- images --> NG
  ECR_F -- images --> NG
  RDS --> KMS
  ECache --> KMS
  EFS --> KMS
  S3Back --> KMS
  S3Logs --> KMS
  DDB --> S3State
  Backup --> RDS
  Backup --> EFS
  CWAlarms --> SNS
  FlowLog --> VPC
  WAFLog --> WAF
  SMDB --> RDS
  SMR --> ECache
  S3State -.->|s3://uniops-terraform-state/bootstrap/terraform.tfstate| BootstrapState[("Bootstrap state<br/>(7 resources)")]:::s3
  Operator -->|start-app-infra.sh<br/>destroy-app-infra.sh| ECR_B

  classDef external fill:#f5f5f5,stroke:#666,stroke-width:1px,color:#000
  classDef network fill:#dae8fc,stroke:#6c8ebf,color:#000
  classDef subnet fill:#e8f1ff,stroke:#6c8ebf,color:#000
  classDef compute fill:#d5e8d4,stroke:#82b366,color:#000
  classDef ec2 fill:#d5e8d4,stroke:#82b366,color:#000
  classDef data fill:#ffe6cc,stroke:#d79b00,color:#000
  classDef storage fill:#fff2cc,stroke:#d6b656,color:#000
  classDef pod fill:#e1d5e7,stroke:#9673a6,color:#000
  classDef k8s fill:#f8cecc,stroke:#b85450,color:#000
  classDef rbac fill:#e1d5e7,stroke:#9673a6,color:#000
  classDef security fill:#f8cecc,stroke:#b85450,color:#000
  classDef s3 fill:#fff2cc,stroke:#d6b656,color:#000
```

---

## 9. Mermaid Diagram — Terraform Module Dependencies

```mermaid
graph LR
  Bootstrap["terraform/bootstrap<br/>(S3 + DDB + 2 ECR)"]:::bootstrap

  subgraph AppLayer["infra-backup/infrastructure/terraform (5-phase)"]
    Networking["phase-01-networking<br/>VPC + subnets + IGW + NAT<br/>+ Bastion + 2 SGs"]:::module
    EKS["phase-02-eks<br/>cluster + node group<br/>+ IAM + OIDC + IRSA + k8s ns"]:::module
    Data["phase-03-data<br/>RDS + Redis + EFS<br/>+ S3 backups/logs + SM"]:::module
    Tools["phase-04-tools<br/>ALB + 5 EC2<br/>+ 4 IAM roles"]:::module
    Security["phase-05-security<br/>KMS + WAF + Backup<br/>+ CloudWatch + flow log + SNS"]:::module
  end

  Networking -- vpc_id, public_subnets, private_subnets, bastion_sg_id --> EKS
  Networking -- vpc_id, vpc_cidr, public_subnets, private_subnets, bastion_sg_id --> Data
  Networking -- vpc_id, vpc_cidr, public_subnets, private_subnets, bastion_sg_id --> Tools
  EKS -- node_security_group_id --> Data
  EKS -- cluster_name --> Security
  Data -- rds_instance_id, rds_instance_arn, efs_id, efs_arn --> Security
  Tools -- alb_arn --> Security
  Security -.->|kms_key_arn (cycle!)| Data

  Bootstrap -.->|s3 bucket + DDB table<br/>(shared state backend)| AppLayer
  Bootstrap -.->|ECR repos for images| EKS

  classDef bootstrap fill:#dae8fc,stroke:#6c8ebf,color:#000
  classDef module fill:#d5e8d4,stroke:#82b366,color:#000
```

**Cycle break (start-app-infra.sh, phased apply):**
1. **Phase A:** `-target=module.networking` (VPC only, no inter-module deps)
2. **Phase B:** `-target=module.security.aws_kms_key.uniops -target=module.security.aws_kms_alias.uniops` (standalone KMS, no inputs)
3. **Phase C:** `-target=module.eks` then `-target=module.data` (Data now finds KMS) then `-target=module.tools`
4. **Phase D:** `-target=module.security` (now that ALB/RDS/EFS exist)
5. **Phase E:** untargeted global apply (catches any drift)

---

## 10. Mermaid Diagram — Kubernetes Workload Map

```mermaid
graph TD
  subgraph NSUniops["Namespace uniops"]
    PG[StatefulSet postgres]:::data
    RD[StatefulSet redis]:::data
    BE[Deployment backend]:::compute
    CW[Deployment celery-worker]:::compute
    CB[Deployment celery-beat]:::compute
    FE[Deployment frontend]:::compute
    MJ[Job uniops-migrate]:::job
    SvcPG[Service postgres headless]:::svc
    SvcRD[Service redis headless]:::svc
    SvcBE[Service backend :80]:::svc
    SvcFE[Service frontend :80]:::svc
    Ing["Ingress uniops-ingress<br/>host=uniops.local"]:::ing
    PVC1[PVC models-pvc 2Gi RWX]:::storage
    PVC2[PVC postgres-data 20Gi RWO]:::storage
    PVC3[PVC redis-data 5Gi RWO]:::storage
    PVC4[PVC celerybeat-pvc 100Mi RWO]:::storage
    SA1[SA uniops-backend]:::rbac
    SA2[SA uniops-worker]:::rbac
    SA3[SA uniops-frontend]:::rbac
    HPA1[HPA backend-hpa 2-8 CPU70% mem80%]:::k8s
    HPA2[HPA celery-worker-hpa 2-6 CPU75%]:::k8s
    PDB1[PDB backend-pdb minAvail=1]:::k8s
    NP1[NetworkPolicy allow-internal]:::k8s
    CM[ConfigMap uniops-config]:::config
    SEC[Secret uniops-secrets]:::config
  end

  PG --- SvcPG
  RD --- SvcRD
  BE --- SvcBE
  FE --- SvcFE

  BE -->|mounts| PVC1
  PG -->|mounts| PVC2
  RD -->|mounts| PVC3
  CB -->|mounts| PVC4

  SvcBE --> Ing
  SvcFE --> Ing

  BE -->|envFrom| CM
  BE -->|envFrom| SEC
  CW -->|envFrom| CM
  CW -->|envFrom| SEC
  CB -->|envFrom| CM
  CB -->|envFrom| SEC
  MJ -->|envFrom| CM
  MJ -->|envFrom| SEC
  PG -->|env POSTGRES_USER/PASSWORD/DB| SEC
  RD -->|env REDIS_PASSWORD| SEC

  BE -->|asyncpg @5432| SvcPG
  CW -->|asyncpg @5432| SvcPG
  BE -->|redis @6379/0| SvcRD
  CW -->|redis @6379/1,2| SvcRD

  BE -.->|serviceAccount| SA1
  CW -.->|serviceAccount| SA2
  CB -.->|serviceAccount| SA2
  FE -.->|serviceAccount| SA3

  HPA1 -.->|scales| BE
  HPA2 -.->|scales| CW
  PDB1 -.->|protects| BE
  NP1 -.->|default-allow<br/>ingress-nginx + pods| NSUniops

  classDef data fill:#ffe6cc,stroke:#d79b00,color:#000
  classDef compute fill:#d5e8d4,stroke:#82b366,color:#000
  classDef job fill:#fad7ac,stroke:#b46504,color:#000
  classDef svc fill:#f8cecc,stroke:#b85450,color:#000
  classDef ing fill:#dae8fc,stroke:#6c8ebf,color:#000
  classDef storage fill:#fff2cc,stroke:#d6b656,color:#000
  classDef rbac fill:#e1d5e7,stroke:#9673a6,color:#000
  classDef k8s fill:#f8cecc,stroke:#b85450,color:#000
  classDef config fill:#e1d5e7,stroke:#9673a6,color:#000
```

---

## 11. Cost Breakdown

**Region:** us-east-2, on-demand pricing as of 2026-06. USD per day. All values are rough; the AWS pricing calculator is the source of truth.

| Resource | Type | $/day (running) | $/day (destroyed) | Notes |
|----------|------|------------------|--------------------|-------|
| EKS cluster | Control plane | ~$7.30 ($0.10/hr) | $0 | Always-billed when ACTIVE |
| EKS node group `uniops-workers` | 2× m7i-flex.large ON_DEMAND (24/7) | ~$5.18 ($0.108/hr × 2 × 24) | $0 | HPA min=2 keeps 2 running 24/7 |
| RDS `uniops-postgres-dev` | db.t3.micro postgres 20GB gp2 | ~$0.18 ($0.018/hr) | $0 | single-AZ, no Multi-AZ |
| ElastiCache `uniops-redis-dev` | cache.t3.micro | ~$0.20 ($0.017/hr) | $0 | |
| EFS `fs-0f6567c976ebd2349` | Standard storage (no data cost shown) | ~$0.10 (1 GB) | $0.10 | Storage persists after destroy unless deleted |
| EFS access point | $0.03/million requests | ~$0.00 | $0.00 | |
| ALB `uniops-alb-dev` | Application LB + LCU | ~$0.80 ($0.0225/hr base) | $0 | |
| Bastion `uniops-bastion` | t3.micro | ~$0.21 ($0.0104/hr) | $0 | |
| Public-1 EC2 | t3.micro | ~$0.21 | $0 | |
| Public-2 EC2 | t3.micro | ~$0.21 | $0 | |
| Monitoring EC2 | t3.micro (private) | ~$0.21 | $0 | |
| SonarQube EC2 | t3.micro (private) | ~$0.21 | $0 | |
| EBS volumes on EC2 (5× instances × 20-30 GB gp3) | ~85 GB | ~$0.20 | $0 (unless retained) | |
| NAT Gateway | 1× | ~$1.08 ($0.045/hr) | $0 | 24/7 |
| NAT Gateway data processing | 1 GB/day | ~$0.045 | $0 | |
| Elastic IP attached to NAT | 1× in-use | $0 | $0 | |
| ECR `uniops-backend` | storage + scan | ~$0.05 (5 GB images) | $0.05 (storage persists) | |
| ECR `uniops-frontend` | storage + scan | ~$0.05 (5 GB images) | $0.05 (storage persists) | |
| S3 `uniops-terraform-state` | versioning, minimal | ~$0.01 | $0.01 | `prevent_destroy`; persists |
| S3 `uniops-backups-dev-v22t87` | backups (variable) | ~$0.05 (5 GB) | $0.05 | Lifecycle → GLACIER after 90d |
| S3 `uniops-logs-dev-storage` | logs | ~$0.02 (2 GB) | $0.02 | 30d→IA, 180d expire |
| DynamoDB `uniops-terraform-locks` | PAY_PER_REQUEST | ~$0.001 | $0.001 | `prevent_destroy`; persists |
| KMS | $1/key/month | ~$0.033 | $0.033 | Single CMK |
| Secrets Manager | 2 secrets | ~$0.10 ($0.40/secret/month) | $0.10 | Persist |
| CloudWatch Logs `aws-waf-logs-uniops` | 30d retention | ~$0.05 | $0 (deleted with destroy) | |
| CloudWatch Logs `uniops-vpc-flow-logs-dev` | 30d retention | ~$0.05 | $0 | |
| CloudWatch Alarms ×3 | metric alarms | ~$0.03 ($0.10/alarm/month) | $0 | |
| SNS `uniops-alerts-dev` | topic | ~$0.001 | $0 | |
| WAFv2 Web ACL | $5/month + $1/rule/month | ~$0.27 | $0.27 | WAF pricing is per ACL + per rule |
| WAFv2 request charges | 1M req/month | ~$0.60 | $0.60 | |
| Data transfer (EKS↔AWS, minimal) | | ~$0.05 | $0 | |
| **TOTAL when running** | | **~$17.5/day (~$525/month)** | | |
| **TOTAL when destroyed** | | | **~$1.4/day (~$42/month)** | S3 state bucket, KMS, ECR images, Secrets Manager, WAF ACL, EFS data, DynamoDB table — all `prevent_destroy` or otherwise persistent |

*Notes:*
- EFS `prevent_destroy` is NOT set; the script will delete the EFS filesystem if you `terraform destroy` the 5-phase tree. But the destroy script as written doesn't actually invoke `terraform destroy` successfully (see §12).
- ECR repos have `lifecycle { prevent_destroy = true }` on the bootstrap layer; they survive any destroy.
- The `S3 state bucket` and `DynamoDB lock table` are bootstrap-owned and `prevent_destroy = true`; they survive any app-layer destroy.

---

## 12. Key Variables & Configuration

| Variable | Default | Used by | Purpose |
|----------|---------|---------|---------|
| `aws_region` | `us-east-2` (bootstrap), `us-east-1` (infrastructure/terraform), `us-east-2` (infra-backup phases) | every module | AWS region for resource creation |
| `project_name` | `uniops-saas` (infra-backup), `uniops` (infra-backup shared), `UniOps` (infrastructure) | root | Used in resource `Name` tags and `local.name` |
| `environment` | `dev` | root | Used in `local.name` and dev-only choices (Multi-AZ off, single NAT, etc.) |
| `vpc_cidr` | `10.0.0.0/16` | networking | VPC IPv4 CIDR |
| `public_subnets` | `{us-east-2a:10.0.1.0/24, us-east-2b:10.0.2.0/24}` | networking | Map of AZ → CIDR |
| `private_subnets` | `{us-east-2a:10.0.3.0/24, us-east-2b:10.0.4.0/24}` | networking | Map of AZ → CIDR |
| `bastion_instance_type` | `t3.micro` | networking | Bastion EC2 type |
| `key_name` | `uniops-key` | networking, tools | EC2 SSH key pair name (generated as RSA 4096 by Terraform) |
| `cluster_version` | `1.29` (infra-backup HCL), `1.30` (live cluster, HCL default overridden), `1.29` (infrastructure/terraform) | EKS | Kubernetes control plane version |
| `enable_aws_config` | `false` | phase-05-security | Toggles AWS Config recorder + 4 rules + S3 bucket (9 resources total). **NOT LIVE.** |
| `state_bucket_name` | `uniops-terraform-state` | bootstrap | S3 bucket for Terraform state |
| `dynamodb_lock_table` | `uniops-terraform-locks` | bootstrap | DynamoDB table for state locking |
| `ecr_repositories` | `[uniops-backend, uniops-frontend]` | bootstrap | ECR repo names |
| `node_instance_type` | `t3.medium` (infrastructure/terraform), `t3.small` (envs/dev.tfvars) | infrastructure/terraform EKS module | Worker node type |
| `db_instance_class` | `db.t3.micro` | infrastructure/terraform RDS module | RDS instance type |
| `redis_node_type` | `cache.t3.micro` | infrastructure/terraform redis | ElastiCache node type |
| `frontend` (image) | `momenpanda/uniops-frontend:latest` (k8s/base) / `180840261837.dkr.ecr.us-east-2.amazonaws.com/uniops-frontend:fix-2026-06-03-full-unwrap` (start-app-infra.sh assertion) | frontend Deployment | Container image |
| `backend` (image) | `momenpanda/uniops-backend:latest` | backend + celery + migrate | Container image |
| `frontend.targetPort` | `80` (k8s/base) / `8080` (start-app-infra.sh assertion) | frontend Service | What port the Service proxies to |
| `celery liveness probe` | `pgrep -f 'celery.*worker'` | celery-worker Deployment | The "live fix" preserved by start-app-infra.sh |
| `CORS_ORIGINS` | `["https://uniops.example.com"]` (base) / `["http://localhost:5173","http://localhost:3000","http://uniops.local"]` (dev) / `["https://uniops.yourdomain.com"]` (prod) | ConfigMap uniops-config | CORS allowed origins |
| `FRONTEND_URL` | `https://uniops.example.com` (base) / `http://uniops.local` (dev) / `https://uniops.yourdomain.com` (prod) | ConfigMap | Used for OAuth, email links, etc. |
| `DATABASE_POOL_SIZE` | `10` (base) / `10` (prod) | ConfigMap | SQLAlchemy pool size |
| `DATABASE_MAX_OVERFLOW` | `5` (base) / `20` (prod) | ConfigMap | SQLAlchemy overflow |
| `RATE_LIMIT_PER_MINUTE` | (not in base) `60` (prod) | ConfigMap | API rate limit |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | (not in base) `60` (prod) | ConfigMap | JWT TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | (not in base) `7` (prod) | ConfigMap | Refresh token TTL |
| `APP_ENV` | `production` (base) / `development` (dev) / `production` (prod) | ConfigMap | Switches app behavior |
| `DEBUG` | `false` (base) / `true` (dev) / `false` (prod) | ConfigMap | Verbose errors |
| `LOG_LEVEL` | `INFO` (base) / `DEBUG` (dev) / `WARNING` (prod) | ConfigMap | Python logging level |
| `CELERY_WORKER_MAX_TASKS_PER_CHILD` | `1` | ConfigMap | Worker recycling |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | ConfigMap | Task batching |
| `backend replicas` | `2` (base+dev) / `3` (prod) | backend Deployment | Pod count |
| `frontend replicas` | `2` (base+dev+prod) | frontend Deployment | Pod count |
| `celery-worker replicas` | `2` (base+dev) / `3` (prod) | celery-worker Deployment | Pod count |
| `celery-beat replicas` | `1` (everywhere, Recreate) | celery-beat Deployment | Single scheduler |
| `HPA backend min/max` | `2/8` (base+dev) / `3/10` (prod) | backend HPA | Scale range |
| `HPA celery min/max` | `2/6` (base+dev) / `3/8` (prod) | celery-worker HPA | Scale range |
| `FRONTEND_TARGET_PORT` (start-app-infra.sh) | `8080` | assertion | **Live fix, NOT in k8s/base (which has `targetPort: 80`)** |
| `TERRAFORM_APP_DIR` (start-app-infra.sh) | `$REPO_ROOT/terraform/app` | static config | **Does not exist; created on first EKS create run** |
| `TERRAFORM_APP_STATE_KEY` (start-app-infra.sh) | `app/terraform.tfstate` | static config | The S3 state key the destroy script expects; **no such key exists in the real S3 bucket** |

---

## 13. Important Discrepancies (Read-Only Findings)

These are not bugs in the infra — they're the actual state of the repo vs. what the live cluster runs.

1. **Frontend image drift between k8s/base and start-app-infra.sh assertion.**
   - `k8s/base/frontend.yaml:43` uses `momenpanda/uniops-frontend:latest`.
   - `start-app-infra.sh:130` asserts `180840261837.dkr.ecr.us-east-2.amazonaws.com/uniops-frontend:fix-2026-06-03-full-unwrap`.
   - The two will disagree on a fresh apply of base. The start script's Phase 6 will fail with `Frontend image drift detected`.

2. **Frontend Service targetPort drift between k8s/base and start-app-infra.sh assertion.**
   - `k8s/base/frontend.yaml:124` uses `targetPort: 80`.
   - `start-app-infra.sh:132` asserts `FRONTEND_TARGET_PORT=8080`.
   - The start script's Phase 7 will warn (not fail) that the live targetPort is 80, not 8080.

3. **Three Terraform roots, none of which can run `terraform plan -destroy` against the live `uniops-eks-dev` cluster as-shipped.**
   - `terraform/bootstrap/` — correct backend (`bootstrap/terraform.tfstate`), but its state owns only the 7 bootstrap resources, not the EKS cluster.
   - `infrastructure/terraform/` — backend `prod/terraform.tfstate` in `us-east-1`. Different region, different cluster name prefix.
   - `infra-backup/infrastructure/terraform/` — has a 270 KB / 106-resource local state that *exactly* mirrors the live infra, but the backend in `shared/provider.tf` and `shared/backend.tf` is broken (two different `backend "s3"` declarations; the original bucket `uniops-terraform-state-8j3k9l` does not exist; the local state never made it to S3).
   - There is **no `terraform/app/` directory** at the repo root, which is what `start-app-infra.sh` and `destroy-app-infra.sh` both reference.

4. **No `s3://uniops-terraform-state/app/terraform.tfstate` key exists.** Only `bootstrap/terraform.tfstate` is present.

5. **Local bootstrap state file is 0 bytes; the `.tfstate.backup` is 12,228 bytes.** The authoritative state is the S3 one (12,227 bytes), last modified 2026-06-05T15:02:36Z.

6. **IRSA role `uniops-irsa-role-dev` exists in AWS but is not consumed by any live workload.** The K8s manifests do not declare a `uniops-sa` service account.

7. **AWS Config resources are not live.** `enable_aws_config` defaults to `false` in the HCL; the 9 `count`-gated resources are absent from the live state.

8. **GuardDuty resources are commented out in HCL** (`phase-05-security/guardduty.tf`). The detector is not enabled.

9. **In-cluster StatefulSets (postgres, redis) shadow the AWS RDS and ElastiCache** that the 5-phase tree provisioned. Both are reachable, but the K8s workloads connect to `postgres:5432` and `redis:6379` in-cluster, not to the RDS endpoint or ElastiCache primary endpoint.

10. **The destroy script's `discover_app_terraform_dir()` will fall through to a search branch and return `/infra-backup/infrastructure/terraform`** (the first match in `sort -u` order), not `terraform/app/` (which doesn't exist). It will then run `terraform init -reconfigure` against `s3://uniops-terraform-state-8j3k9l` which does not exist, and exit with code 6 at `fail "terraform init failed for the app layer."`. The cluster will not be destroyed. (See prior bug reports in this conversation's history for full detail.)

11. **models-pvc in `k8s/base/backend.yaml` has no `storageClassName`** (all 3 cloud options are commented out). In dev, the start script asserts the default StorageClass is `local-path` and warns otherwise. The `models-pvc` will bind to whatever default the cluster has — in a `minikube` or `k3d` cluster, that's typically `local-path` (RWO, not RWX as requested by the PVC). In a real EKS cluster, the default is typically `gp2` (also RWO, also not RWX). The PVC's `ReadWriteMany` access mode is therefore unsatisfiable in practice until an `efs-sc` or equivalent StorageClass is uncommented in the prod overlay.

12. **`migrate_job.yaml` and `ingress.yaml` exist at the repo root** (top-level files) and contain the same migration Job and Ingress as `k8s/base/`. They are NOT referenced by the `k8s/base/kustomization.yaml`; they are duplicates left over from an earlier layout.

---

*End of report.*
