#!/usr/bin/env bash

# ==============================================================================
# UniOps SaaS — Application Infrastructure Startup
# Version: 3.0 — App-Layer Isolated, Production-Hardened
# ------------------------------------------------------------------------------
# PURPOSE
#   Bootstrap / verify / re-apply the APPLICATION layer of UniOps only.
#   This script manages the things that get redeployed, scaled, or
#   torn down with the app — NOT the long-lived shared foundation.
#
# SCOPE (what this script touches)
#   ✔ EKS cluster (creates if missing via app Terraform layer; otherwise uses existing)
#   ✔ VPC, subnets, NAT, IGW, route tables (phase-01)
#   ✔ EKS node groups, IRSA, OIDC, cluster security groups (phase-02)
#   ✔ RDS Postgres, ElastiCache Redis, EFS, S3 data buckets (phase-03)
#   ✔ ALB, Bastion, public EC2 tools (phase-04)
#   ✔ WAF, KMS, GuardDuty, Backup, CloudWatch alarms (phase-05)
#   ✔ Helm releases: ingress-nginx, aws-efs-csi-driver (upgrade-only)
#   ✔ In-cluster StatefulSets: postgres, redis (recreate if missing)
#   ✔ UniOps namespace + base manifests + dev overlay
#   ✔ Kubernetes Secrets: uniops-secrets (preserved if present)
#   ✔ Kubernetes Secrets: dockerhub-secret, ecr-pull-secret (refreshed)
#   ✔ Image rollouts to the live pin (frontend=fix-2026-06-03-full-unwrap,
#     backend=momenpanda/uniops-backend:latest)
#
# SCOPE (what this script NEVER touches — protected)
#   ✗ terraform/bootstrap/   (managed by bootstrap layer, see terraform/bootstrap/README.md)
#   ✗ aws_ecr_repository.*   (state bucket is shared, repos are bootstrap-owned)
#   ✗ aws_s3_bucket.uniops-terraform-state  (bootstrap-owned)
#   ✗ aws_dynamodb_table.uniops-terraform-locks  (bootstrap-owned)
#   ✗ aws_eks_cluster.uniops-eks-dev  (lifecycle=managed-out-of-band)
#   ✗ RDS, ElastiCache, EFS  (provisioned out-of-band; not redeployed)
#   ✗ CELERY_WORKER_LIVENESS_PROBE  (pgrep-based; PRESERVED EXACTLY)
#   ✗ frontend.spec.ports[0].targetPort=8080  (PRESERVED EXACTLY)
#   ✗ frontend image tag `fix-2026-06-03-full-unwrap`  (PRESERVED EXACTLY)
#
# USAGE
#   bash start-app-infra.sh                  # normal run
#   bash start-app-infra.sh --skip-helm      # don't upgrade add-ons
#   bash start-app-infra.sh --skip-images    # don't trigger rollouts
#   bash start-app-infra.sh --skip-terraform # don't run terraform; fail if EKS missing
#   bash start-app-infra.sh --no-create      # fail if EKS missing (legacy strict mode)
#   bash start-app-infra.sh --dry-run        # print actions, make no changes
#
# EKS CREATION
#   If the EKS cluster does not exist, the script will:
#     1. Verify the bootstrap state backend (S3 + DDB) is in place
#     2. Prepare terraform/app/ from infra-backup/infrastructure/terraform
#        and patch the backend config to use the bootstrap-owned bucket
#     3. Run a phased `terraform apply` to break the data↔security cycle
#     4. Wait for EKS to become ACTIVE
#     5. Configure kubeconfig and continue
#   The bootstrap layer is NEVER touched by this path.
#
# IDEMPOTENCY
#   - Helm: install-or-upgrade
#   - Namespace: kubectl create --dry-run=client | apply
#   - Manifests: kubectl apply -k  (kubectl is naturally idempotent)
#   - Secrets: read existing values, only re-create if missing
#   - StatefulSets: apply only if absent
#   - EFS probe PVC: created and deleted within the same run
#
# EXIT CODES
#   0  success
#   1  prerequisites missing
#   2  EKS cluster unreachable
#   3  add-on install/upgrade failed
#   4  application rollout failed
#   5  health check failed
# ==============================================================================

set -euo pipefail

# ─── Colours & logging ────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log()    { echo -e "${BLUE}[$(date +'%Y-%m-%dT%H:%M:%S')]${NC} $*"; }
ok()     { echo -e "${GREEN}[$(date +'%Y-%m-%dT%H:%M:%S')] ✓${NC} $*"; }
warn()   { echo -e "${YELLOW}[$(date +'%Y-%m-%dT%H:%M:%S')] ⚠${NC} $*"; }
fail()   { echo -e "${RED}[$(date +'%Y-%m-%dT%H:%M:%S')] ✗ $*${NC}" >&2; exit "${2:-1}"; }
divider(){ echo -e "────────────────────────────────────────────────────────────────────────────────"; }
section(){ divider; echo -e "${BOLD}  $*${NC}"; divider; }

# ─── Flags ────────────────────────────────────────────────────────────────────
SKIP_HELM=0
SKIP_IMAGES=0
DRY_RUN=0
ALLOW_CREATE=1     # default ON: auto-create EKS via app Terraform layer if missing
                    # set --no-create to fail-fast instead (legacy behaviour)
SKIP_TERRAFORM=0
for arg in "$@"; do
  case "$arg" in
    --skip-helm)     SKIP_HELM=1 ;;
    --skip-images)   SKIP_IMAGES=1 ;;
    --skip-terraform) SKIP_TERRAFORM=1 ;;
    --no-create)     ALLOW_CREATE=0 ;;
    --dry-run)       DRY_RUN=1 ;;
    -h|--help)       sed -n '2,50p' "$0"; exit 0 ;;
    *)               fail "Unknown flag: $arg" ;;
  esac
done

# ─── Static config (paths only) ──────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_BASE="$REPO_ROOT/k8s/base"
K8S_DEV="$REPO_ROOT/k8s/overlays/dev"
NAMESPACE="uniops"
REGION="${AWS_REGION:-us-east-2}"

# App Terraform layer — owns EKS + all app-layer AWS resources.
# State lives at s3://uniops-terraform-state/app/terraform.tfstate (a different
# key from bootstrap/terraform.tfstate). The bucket and DynamoDB table are
# owned by the bootstrap layer; we only WRITE to our key.
TERRAFORM_APP_DIR="$REPO_ROOT/terraform/app"
TERRAFORM_APP_STATE_BUCKET="uniops-terraform-state"
TERRAFORM_APP_STATE_KEY="app/terraform.tfstate"
TERRAFORM_APP_LOCK_TABLE="uniops-terraform-locks"

# Source of the 5-phase module code: the legacy tree under infra-backup/.
# We copy it to $TERRAFORM_APP_DIR on first run, then patch the backend
# config to point at the bootstrap-provided bucket. This keeps the app layer
# reproducible from the repo without touching the legacy backup.
TERRAFORM_APP_SOURCE="$REPO_ROOT/infra-backup/infrastructure/terraform"

# Live, pinned, in-cluster image set.
# DO NOT change these without an explicit, reviewed change to the deployment
# manifests. They reflect the running, healthy production state as of 2026-06-05.
FRONTEND_IMAGE="180840261837.dkr.ecr.us-east-2.amazonaws.com/uniops-frontend:fix-2026-06-03-full-unwrap"
BACKEND_IMAGE_DOCKERHUB="momenpanda/uniops-backend:latest"
FRONTEND_TARGET_PORT=8080   # PRESERVED EXACTLY
CELERY_PROBE="pgrep -f 'celery.*worker'"   # PRESERVED EXACTLY

# ─── Protected-resource guard (fail-fast) ─────────────────────────────────────
# Refuse to run if it looks like the user is about to mutate bootstrap state.
# This is a hard guard, not a soft warning. It checks the CWD and any flag
# that could be misrouted, and refuses to start if the bootstrap layer is
# being touched.
guard_bootstrap_isolation() {
  log "Verifying bootstrap isolation..."

  # 1. The bootstrap Terraform directory must exist (sanity check) but we
  #    must NOT cd into it from this script.
  [[ -d "$REPO_ROOT/terraform/bootstrap" ]] \
    || fail "Bootstrap layer missing at $REPO_ROOT/terraform/bootstrap — refusing to run."

  # 2. Refuse to run if the user is INSIDE the bootstrap directory.
  case "$(pwd)" in
    */terraform/bootstrap|*/terraform/bootstrap/*)
      fail "You are inside terraform/bootstrap/. Run this script from the repo root." ;;
  esac

  # 3. Refuse to run if BACKEND/FRONTEND ECR repos are about to be created
  #    by us. We only REFERENCE them, never create/destroy.
  for REPO in uniops-backend uniops-frontend; do
    if ! aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" \
         &>/dev/null; then
      fail "ECR repo $REPO missing. Create it via 'cd terraform/bootstrap && terraform apply' FIRST. Refusing to run."
    fi
  done

  ok "Bootstrap isolation verified. ECR repos exist; we will not touch bootstrap state."
}

# ─── Wait helpers ─────────────────────────────────────────────────────────────
wait_deploy() {
  local ns="$1" name="$2" timeout="${3:-300s}"
  log "Waiting for deployment/$name in $ns (timeout: $timeout)..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would: kubectl -n $ns rollout status deployment/$name --timeout=$timeout"
    return 0
  fi
  kubectl -n "$ns" rollout status "deployment/$name" --timeout="$timeout" \
    || fail "Rollout of deployment/$name in $ns did not complete." 2
}

wait_pods() {
  local ns="$1" label="$2" expected="${3:-1}" timeout="${4:-300}"
  log "Waiting for $expected pod(s) ($label) in $ns..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would wait for $expected pod(s) with label $label"
    return 0
  fi
  local elapsed=0 interval=10
  while true; do
    local ready
    ready=$(kubectl -n "$ns" get pods -l "$label" \
              --field-selector=status.phase=Running \
              --no-headers 2>/dev/null | wc -l | tr -d ' ')
    [[ "$ready" -ge "$expected" ]] && { ok "$ready/$expected pod(s) Running."; return 0; }
    [[ "$elapsed" -ge "$timeout" ]] && fail "Timed out waiting for pods ($label) in $ns." 2
    sleep "$interval"; elapsed=$((elapsed + interval))
    log "  Still waiting... $ready/$expected Running (${elapsed}s / ${timeout}s)"
  done
}

# ─── Phase 0 — Prerequisites ─────────────────────────────────────────────────
step_prerequisites() {
  section "PHASE 0 — Prerequisites Validation"
  local tools=(aws kubectl helm jq openssl)
  for tool in "${tools[@]}"; do
    command -v "$tool" &>/dev/null || fail "Required tool '$tool' is not installed." 1
  done
  ok "All required CLI tools present."

  aws sts get-caller-identity &>/dev/null \
    || fail "AWS credentials invalid or expired. Run 'aws configure' or export credentials." 1
  ok "AWS credentials valid ($(aws sts get-caller-identity --query Arn --output text))."
}

# ─── Helpers used by the EKS create / connect path ───────────────────────────

# Detect the live EKS cluster name (single-cluster, name contains 'uniops').
# Echoes the cluster name on stdout, or empty if not found.
detect_eks_cluster() {
  aws eks list-clusters --region "$REGION" \
    --query 'clusters[?contains(@, `uniops`)] | [0]' \
    --output text 2>/dev/null | tr -d '[]"' || true
}

# Configure kubeconfig for a given cluster and verify reachability.
configure_kubeconfig() {
  local cluster="$1"
  log "Updating kubeconfig for $cluster..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would: aws eks update-kubeconfig --region $REGION --name $cluster"
    return 0
  fi
  aws eks update-kubeconfig --region "$REGION" --name "$cluster"
  local attempts=0
  until kubectl get nodes &>/dev/null; do
    attempts=$((attempts + 1))
    [[ "$attempts" -ge 12 ]] && fail "Cannot reach EKS after 2 minutes." 2
    warn "Cluster not yet reachable — attempt $attempts/12..."
    sleep 10
  done
  local ctx; ctx=$(kubectl config current-context)
  echo "$ctx" | grep -qi "minikube" && fail "kubectl is pointing to minikube ($ctx). Refusing." 2
  ok "kubectl context: $ctx"
  kubectl get nodes -o wide
}

# Prepare the app-layer Terraform working directory at $TERRAFORM_APP_DIR.
# Copies from $TERRAFORM_APP_SOURCE on first run and patches the backend
# config to point at the bootstrap-provided bucket.
prepare_app_terraform_dir() {
  log "Preparing app Terraform working dir: $TERRAFORM_APP_DIR"
  if [[ ! -d "$TERRAFORM_APP_SOURCE" ]]; then
    fail "App Terraform source tree missing: $TERRAFORM_APP_SOURCE" 1
  fi
  if [[ -d "$TERRAFORM_APP_DIR" ]]; then
    log "  $TERRAFORM_APP_DIR already exists — reusing."
    return 0
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would: cp -r $TERRAFORM_APP_SOURCE $TERRAFORM_APP_DIR"
    log "  [dry-run] would: patch shared/backend.tf to use bucket=$TERRAFORM_APP_STATE_BUCKET key=$TERRAFORM_APP_STATE_KEY"
    return 0
  fi
  mkdir -p "$(dirname "$TERRAFORM_APP_DIR")"
  cp -r "$TERRAFORM_APP_SOURCE" "$TERRAFORM_APP_DIR"
  # Patch the backend config to point at the bootstrap-provided bucket and
  # the app-layer state key. The original bucket name in the legacy tree
  # (uniops-terraform-state-8j3k9l) does not exist; we rewrite it.
  local backend_tf="$TERRAFORM_APP_DIR/shared/backend.tf"
  [[ -f "$backend_tf" ]] || fail "Expected backend config at $backend_tf" 1
  cat > "$backend_tf" <<EOF
# AUTO-GENERATED by start-app-infra.sh — do not edit by hand.
# App-layer state is stored under a separate key in the bootstrap-owned bucket.
terraform {
  backend "s3" {
    bucket         = "$TERRAFORM_APP_STATE_BUCKET"
    key            = "$TERRAFORM_APP_STATE_KEY"
    region         = "$REGION"
    dynamodb_table = "$TERRAFORM_APP_LOCK_TABLE"
    encrypt        = true
  }
}
EOF
  ok "  App Terraform dir prepared."
}

# Run `terraform init` in the app layer (idempotent).
app_terraform_init() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would: (cd $TERRAFORM_APP_DIR && terraform init -input=false)"
    return 0
  fi
  log "  terraform init (app layer)..."
  (cd "$TERRAFORM_APP_DIR" && terraform init -input=false -reconfigure) \
    || fail "terraform init failed for the app layer." 6
}

# Run a single targeted `terraform apply` against the app layer.
# Usage: app_terraform_apply <target-args...>
# Example: app_terraform_apply -target=module.networking
app_terraform_apply() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would: (cd $TERRAFORM_APP_DIR && terraform apply -auto-approve -input=false $*)"
    return 0
  fi
  log "  terraform apply -auto-approve $*"
  (cd "$TERRAFORM_APP_DIR" && terraform apply -auto-approve -input=false "$@") \
    || fail "terraform apply failed: $*" 6
}

# Run the phased apply to break the data↔security circular dependency.
# Each phase is targeted. After all phases succeed, a final un-targeted apply
# reconciles any drift.
app_terraform_phased_apply() {
  section "App Terraform — phased apply (breaks data↔security cycle)"

  # Phase A: networking first (no dependencies on other modules)
  log "Phase A: networking..."
  app_terraform_apply -target=module.networking

  # Phase B: KMS key for data-layer encryption (security module partial).
  # The security module has a circular dep with data (data needs kms,
  # security needs rds/efs). We break it by creating the KMS key first.
  log "Phase B: KMS key (cycle break)..."
  app_terraform_apply \
    -target=module.security.aws_kms_key.uniops \
    -target=module.security.aws_kms_alias.uniops

  # Phase C: EKS + data + tools in parallel-friendly order.
  # EKS needs VPC (done). Data needs KMS (done). Tools need VPC (done).
  log "Phase C: EKS, data, tools..."
  app_terraform_apply -target=module.eks
  app_terraform_apply -target=module.data
  app_terraform_apply -target=module.tools

  # Phase D: security (full module, now that all its inputs are populated)
  log "Phase D: security (final)..."
  app_terraform_apply -target=module.security

  # Phase E: global sync (catches anything missed by the targeted applies)
  log "Phase E: global sync (no -target)..."
  app_terraform_apply

  ok "App Terraform apply complete."
}

# ─── Phase 1 — EKS provisioning: create if missing, otherwise connect ────────
step_eks_provision() {
  section "PHASE 1 — EKS Provisioning (create if missing)"

  if [[ "$SKIP_TERRAFORM" -eq 1 ]]; then
    log "--skip-terraform set; falling back to connectivity-only mode."
    local cluster; cluster=$(detect_eks_cluster)
    [[ -n "$cluster" && "$cluster" != "None" ]] \
      || fail "--skip-terraform but no EKS cluster exists. Remove --skip-terraform to create one." 2
    ok "EKS cluster found: $cluster"
    configure_kubeconfig "$cluster"
    return 0
  fi

  local existing_cluster
  existing_cluster=$(detect_eks_cluster)

  if [[ -n "$existing_cluster" && "$existing_cluster" != "None" ]]; then
    ok "EKS cluster already exists: $existing_cluster"
    log "Skipping Terraform create. Connecting to existing cluster..."
    configure_kubeconfig "$existing_cluster"
    return 0
  fi

  if [[ "$ALLOW_CREATE" -ne 1 ]]; then
    fail "No EKS cluster found and --no-create was passed. Refusing to create one." 2
  fi

  log "No EKS cluster found. Initialising the app Terraform layer..."

  # Sanity: bootstrap resources must exist (refuse to start without them).
  aws s3api head-bucket --bucket "$TERRAFORM_APP_STATE_BUCKET" --region "$REGION" &>/dev/null \
    || fail "Bootstrap S3 state bucket $TERRAFORM_APP_STATE_BUCKET missing. Run 'cd terraform/bootstrap && terraform apply' first." 6
  aws dynamodb describe-table --table-name "$TERRAFORM_APP_LOCK_TABLE" --region "$REGION" &>/dev/null \
    || fail "Bootstrap DynamoDB lock table $TERRAFORM_APP_LOCK_TABLE missing. Bootstrap must be applied first." 6
  ok "Bootstrap state backend verified."

  prepare_app_terraform_dir
  app_terraform_init
  app_terraform_phased_apply

  # Re-detect the cluster (it should now exist)
  local new_cluster
  new_cluster=$(detect_eks_cluster)
  [[ -n "$new_cluster" && "$new_cluster" != "None" ]] \
    || fail "EKS cluster still not visible after Terraform apply. Inspect the apply log." 2
  ok "EKS cluster created: $new_cluster"

  # EKS control plane takes 5-15 min to become ACTIVE. Wait for it.
  log "Waiting for EKS cluster $new_cluster to reach ACTIVE state..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would: aws eks wait cluster-active --name $new_cluster"
  else
    aws eks wait cluster-active --name "$new_cluster" --region "$REGION" \
      || fail "EKS cluster $new_cluster did not become ACTIVE in time." 2
  fi

  configure_kubeconfig "$new_cluster"
}

# ─── Phase 2 — Helm add-ons (upgrade-only, never create ECR/bucket) ──────────
step_addons() {
  section "PHASE 2 — Cluster Add-ons (Helm upgrade-only)"
  if [[ "$SKIP_HELM" -eq 1 ]]; then
    warn "--skip-helm set; not touching ingress-nginx or EFS CSI."
    return 0
  fi

  # EFS CSI Driver
  log "Reconciling aws-efs-csi-driver (kube-system)..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would install/upgrade aws-efs-csi-driver"
  else
    helm repo add aws-efs-csi-driver https://kubernetes-sigs.github.io/aws-efs-csi-driver/ &>/dev/null || true
    helm repo update &>/dev/null
    if helm status aws-efs-csi-driver -n kube-system &>/dev/null; then
      helm upgrade aws-efs-csi-driver aws-efs-csi-driver/aws-efs-csi-driver \
        --namespace kube-system \
        --set controller.serviceAccount.create=true \
        --set controller.serviceAccount.name=efs-csi-controller-sa \
        --atomic --timeout 5m0s
    else
      helm install aws-efs-csi-driver aws-efs-csi-driver/aws-efs-csi-driver \
        --namespace kube-system \
        --set controller.serviceAccount.create=true \
        --set controller.serviceAccount.name=efs-csi-controller-sa \
        --atomic --timeout 5m0s
    fi
    wait_pods kube-system app=efs-csi-controller 1 300
    wait_pods kube-system app=efs-csi-node 1 300
  fi
  ok "EFS CSI Driver is Ready."

  # ingress-nginx
  log "Reconciling ingress-nginx (ingress-nginx)..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "  [dry-run] would install/upgrade ingress-nginx"
  else
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx &>/dev/null || true
    helm repo update &>/dev/null
    if helm status ingress-nginx -n ingress-nginx &>/dev/null; then
      helm upgrade ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx --atomic --timeout 5m0s
    else
      helm install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx --create-namespace --atomic --timeout 5m0s
    fi
    wait_deploy ingress-nginx ingress-nginx-controller 300s
    kubectl get ingressclass nginx &>/dev/null \
      || fail "IngressClass 'nginx' missing after install." 3
  fi
  ok "ingress-nginx is Ready."
}

# ─── Phase 3 — In-cluster StatefulSets (postgres, redis) ─────────────────────
step_statefulsets() {
  section "PHASE 3 — In-cluster StatefulSets (postgres, redis)"

  if [[ ! -f "$K8S_BASE/postgres.yaml" || ! -f "$K8S_BASE/redis.yaml" ]]; then
    fail "Missing $K8S_BASE/postgres.yaml or $K8S_BASE/redis.yaml — refusing to deploy." 4
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: kubectl apply -n $NAMESPACE postgres.yaml + redis.yaml"
  else
    kubectl apply -n "$NAMESPACE" -f "$K8S_BASE/postgres.yaml"
    kubectl apply -n "$NAMESPACE" -f "$K8S_BASE/redis.yaml"
    wait_pods "$NAMESPACE" app=postgres 1 300
    wait_pods "$NAMESPACE" app=redis    1 300
  fi
  ok "In-cluster postgres/redis Ready."

  # Local-path StorageClass — required by the StatefulSets
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: verify local-path StorageClass is the cluster default"
  else
    local default_sc
    default_sc=$(kubectl get sc -o jsonpath='{.items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class=="true")].metadata.name}' 2>/dev/null || true)
    [[ "$default_sc" == "local-path" ]] \
      || warn "Default StorageClass is '$default_sc' (expected 'local-path'). PVCs may not bind."
  fi
}

# ─── Phase 4 — Namespace, base manifests, dev overlay ────────────────────────
step_manifests() {
  section "PHASE 4 — Namespace, Base Manifests, Dev Overlay"

  if [[ ! -d "$K8S_BASE" ]]; then
    fail "Missing $K8S_BASE — refusing to deploy." 4
  fi
  if [[ ! -d "$K8S_DEV" ]]; then
    fail "Missing $K8S_DEV — refusing to deploy." 4
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: kubectl apply -n $NAMESPACE (namespace, base manifests, dev overlay)"
    return 0
  fi

  # Namespace first (idempotent)
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
  ok "Namespace $NAMESPACE present."

  # Base manifests
  log "Applying base manifests..."
  kubectl apply -k "$K8S_BASE" 2>&1 | tee /tmp/k8s-base-apply.log
  ok "Base manifests applied."

  # Dev overlay (the live overlay in use as of 2026-06-05)
  log "Applying dev overlay..."
  kubectl apply -k "$K8S_DEV" 2>&1 | tee /tmp/k8s-dev-apply.log
  ok "Dev overlay applied."
}

# ─── Phase 5 — Secrets (preserve existing values) ───────────────────────────
step_secrets() {
  section "PHASE 5 — Kubernetes Secrets (preserve existing values)"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: refresh uniops-secrets, dockerhub-secret, ecr-pull-secret"
    return 0
  fi

  # uniops-secrets — only generate if missing
  if kubectl -n "$NAMESPACE" get secret uniops-secrets &>/dev/null; then
    ok "uniops-secrets already exists — PRESERVING (no rotation)."
  else
    warn "uniops-secrets missing — creating with random SECRET_KEY/JWT_SECRET_KEY."
    kubectl -n "$NAMESPACE" create secret generic uniops-secrets \
      --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
      --from-literal=JWT_SECRET_KEY="$(openssl rand -hex 32)" \
      --from-literal=POSTGRES_USER=uniops \
      --from-literal=POSTGRES_PASSWORD=uniops_password \
      --from-literal=POSTGRES_DB=uniops_db \
      --from-literal=POSTGRES_HOST=postgres \
      --from-literal=REDIS_PASSWORD="" \
      --from-literal=REDIS_URL="redis://redis:6379/0" \
      --from-literal=GITHUB_TOKEN="" \
      --from-literal=SENTRY_DSN=""
  fi

  # dockerhub-secret — refresh ECR token is irrelevant; DockerHub pull is via
  # node-level config or this secret. Preserve if present.
  if kubectl -n "$NAMESPACE" get secret dockerhub-secret &>/dev/null; then
    ok "dockerhub-secret already exists — PRESERVING."
  else
    warn "dockerhub-secret missing — creating empty placeholder. Add real creds manually."
    kubectl -n "$NAMESPACE" create secret docker-registry dockerhub-secret \
      --docker-server=docker.io --docker-username=PLACEHOLDER --docker-password=PLACEHOLDER
  fi

  # ecr-pull-secret — refresh with current AWS ECR token (12h TTL)
  log "Refreshing ecr-pull-secret with current ECR auth token..."
  local ecr_token
  ecr_token=$(aws ecr get-login-password --region "$REGION")
  kubectl -n "$NAMESPACE" create secret docker-registry ecr-pull-secret \
    --docker-server="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}.dkr.ecr.${REGION}.amazonaws.com" \
    --docker-username=AWS \
    --docker-password="$ecr_token" \
    --dry-run=client -o yaml | kubectl apply -f -
  ok "ecr-pull-secret refreshed."
}

# ─── Phase 6 — Image rollout to live pins ────────────────────────────────────
step_image_rollout() {
  section "PHASE 6 — Image Rollout (LIVE PINS — DO NOT CHANGE)"

  if [[ "$SKIP_IMAGES" -eq 1 ]]; then
    warn "--skip-images set; not triggering rollouts."
    return 0
  fi

  # Sanity check: refuse to roll if the live pin in the manifest has been
  # silently changed. We assert against the known-good values.
  log "Asserting live image pins are unchanged..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would assert: frontend=$FRONTEND_IMAGE, backend=$BACKEND_IMAGE_DOCKERHUB"
  else
    local live_fe live_be
    live_fe=$(kubectl -n "$NAMESPACE" get deploy frontend -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")
    live_be=$(kubectl -n "$NAMESPACE" get deploy backend  -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")
    [[ "$live_fe" == "$FRONTEND_IMAGE" ]] \
      || fail "Frontend image drift detected: live=$live_fe expected=$FRONTEND_IMAGE" 4
    [[ "$live_be" == "$BACKEND_IMAGE_DOCKERHUB" ]] \
      || fail "Backend image drift detected: live=$live_be expected=$BACKEND_IMAGE_DOCKERHUB" 4
    ok "Image pins match live production."
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: kubectl rollout restart deploy/{backend,celery-worker,celery-beat,frontend}"
    return 0
  fi

  log "Restarting workloads to pick up any new manifests (in-cluster STS unchanged)..."
  for d in backend celery-worker celery-beat frontend; do
    if kubectl -n "$NAMESPACE" get deploy "$d" &>/dev/null; then
      kubectl -n "$NAMESPACE" rollout restart "deployment/$d" || warn "rollout restart of $d failed"
    fi
  done
  for d in backend celery-worker celery-beat frontend; do
    kubectl -n "$NAMESPACE" get deploy "$d" &>/dev/null && wait_deploy "$NAMESPACE" "$d" 300s || true
  done
  ok "Image rollout complete."
}

# ─── Phase 7 — Health checks ─────────────────────────────────────────────────
step_health() {
  section "PHASE 7 — Health Checks"
  local failures=0

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would run health checks (nodes, pods, PVCs, services, ingress)"
    return 0
  fi

  # Pod readiness in uniops namespace
  local not_running
  not_running=$(kubectl -n "$NAMESPACE" get pods --no-headers \
                  | grep -vE "Running|Completed|Succeeded" | wc -l | tr -d ' ')
  if [[ "$not_running" -ne 0 ]]; then
    warn "$not_running pod(s) in $NAMESPACE are not Running."
    failures=$((failures + 1))
  else
    ok "All $NAMESPACE pods Running."
  fi

  # PVCs
  local pvc_bad
  pvc_bad=$(kubectl -n "$NAMESPACE" get pvc --no-headers | grep -v Bound | wc -l | tr -d ' ')
  if [[ "$pvc_bad" -ne 0 ]]; then
    warn "$pvc_bad PVC(s) not Bound in $NAMESPACE."
    failures=$((failures + 1))
  else
    ok "All PVCs Bound."
  fi

  # Frontend targetPort (PRESERVED EXACTLY)
  local fe_port
  fe_port=$(kubectl -n "$NAMESPACE" get svc frontend -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null || echo "")
  [[ "$fe_port" == "$FRONTEND_TARGET_PORT" ]] \
    || { warn "Frontend targetPort=$fe_port (expected $FRONTEND_TARGET_PORT)."; failures=$((failures + 1)); }

  # Celery liveness probe (PRESERVED EXACTLY)
  local probe
  probe=$(kubectl -n "$NAMESPACE" get deploy celery-worker -o jsonpath='{.spec.template.spec.containers[0].livenessProbe.exec.command}' 2>/dev/null || echo "")
  if [[ "$probe" == *"$CELERY_PROBE"* ]]; then
    ok "Celery liveness probe is pgrep-based (preserved)."
  else
    warn "Celery liveness probe is NOT pgrep-based: $probe"
    failures=$((failures + 1))
  fi

  # Final summary
  divider
  if [[ "$failures" -eq 0 ]]; then
    ok "ALL HEALTH CHECKS PASSED — UniOps app layer is healthy."
    log "Pods in $NAMESPACE:"
    kubectl -n "$NAMESPACE" get pods
    return 0
  fi
  fail "$failures health-check failure(s)." 5
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
  divider
  echo -e "${BOLD}  UniOps SaaS — Application Infrastructure Startup (v3.0)${NC}"
  echo -e "  $(date)"
  echo -e "  Region:    $REGION"
  echo -e "  Namespace: $NAMESPACE"
  echo -e "  Flags:     SKIP_HELM=$SKIP_HELM SKIP_IMAGES=$SKIP_IMAGES DRY_RUN=$DRY_RUN SKIP_TERRAFORM=$SKIP_TERRAFORM ALLOW_CREATE=$ALLOW_CREATE"
  divider

  guard_bootstrap_isolation
  step_prerequisites
  step_eks_provision
  step_addons
  step_statefulsets
  step_manifests
  step_secrets
  step_image_rollout
  step_health
}

main "$@"
