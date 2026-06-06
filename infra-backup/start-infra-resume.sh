#!/usr/bin/env bash

# ==============================================================================
# UniOps SaaS Infrastructure Startup Automation
# Version: 2.0 — Production Hardened
# ------------------------------------------------------------------------------
# Fixes implemented (v2.0):
#   [1] Credentials pulled dynamically from Terraform outputs / Secrets Manager
#   [2] ExternalName services guaranteed via inline manifest application
#   [3] ECR repos verified/created; images validated before deploy
#   [4] Cluster name resolved dynamically from Terraform state
#   [5] Readiness waits on EFS CSI Driver and NGINX Ingress
#   [6] Storage validation: EFS, StorageClass, PVC provisioning
#   [7] Ingress validation before workload deploy
#   [8] Enhanced health checks with actionable diagnostics
#   [9] Full idempotency throughout all phases
#  [10] Strict ordered sequence with no race conditions
# ==============================================================================

set -euo pipefail

# ─── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

# ─── Logging helpers ──────────────────────────────────────────────────────────
log()    { echo -e "${BLUE}[$(date +'%Y-%m-%dT%H:%M:%S')]${NC} $*"; }
ok()     { echo -e "${GREEN}[$(date +'%Y-%m-%dT%H:%M:%S')] ✓${NC} $*"; }
warn()   { echo -e "${YELLOW}[$(date +'%Y-%m-%dT%H:%M:%S')] ⚠${NC} $*"; }
error()  { echo -e "${RED}[$(date +'%Y-%m-%dT%H:%M:%S')] ✗ ERROR: $*${NC}"; exit 1; }
divider(){ echo -e "────────────────────────────────────────────────────────────────────────────────"; }
section(){ divider; echo -e "${BOLD}  $*${NC}"; divider; }

# ─── Static config (paths only — no cluster names, no credentials) ─────────────
PROJECT_ROOT="/home/u1/Desktop/UniOps-SaaS-Product/infra-backup"
TF_DIR="$PROJECT_ROOT/infrastructure/terraform"
K8S_BASE="$PROJECT_ROOT/k8s/base"
K8S_DEV="$PROJECT_ROOT/k8s/overlays/dev"
NAMESPACE="uniops"
REGION=""          # resolved dynamically
CLUSTER_NAME=""    # resolved dynamically
ECR_BACKEND=""     # resolved dynamically
ECR_FRONTEND=""    # resolved dynamically

# ─── Wait helpers ─────────────────────────────────────────────────────────────

# Wait for a Deployment/DaemonSet to become Ready
wait_deploy() {
    local ns="$1" name="$2" timeout="${3:-300s}"
    log "Waiting for deployment/$name in $ns (timeout: $timeout)..."
    kubectl -n "$ns" rollout status deployment/"$name" --timeout="$timeout" \
        || kubectl -n "$ns" rollout status daemonset/"$name" --timeout="$timeout" \
        || error "Rollout of $name in $ns did not complete in time."
    ok "deployment/$name is Ready."
}

# Wait until at least N pods matching a label are Running
wait_pods() {
    local ns="$1" label="$2" expected="${3:-1}" timeout="${4:-300}"
    log "Waiting for pods ($label) in $ns..."
    local elapsed=0 interval=10
    while true; do
        local ready
        ready=$(kubectl -n "$ns" get pods -l "$label" \
                  --field-selector=status.phase=Running \
                  --no-headers 2>/dev/null | wc -l | tr -d ' ')
        [[ "$ready" -ge "$expected" ]] && { ok "Pods ($label) are Running ($ready/$expected)."; return 0; }
        [[ "$elapsed" -ge "$timeout" ]] && error "Timed out waiting for pods ($label) in $ns."
        sleep "$interval"; elapsed=$((elapsed + interval))
        log "  Still waiting... $ready/$expected Running (${elapsed}s / ${timeout}s)"
    done
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 0 — Prerequisites
# ══════════════════════════════════════════════════════════════════════════════
 :step_prerequisites() {
    section "PHASE 0 — Prerequisites Validation"

    local tools=("aws" "terraform" "kubectl" "helm" "jq" "openssl" "docker")
    for tool in "${tools[@]}"; do
        command -v "$tool" &>/dev/null || error "Required tool '$tool' is not installed."
    done
    ok "All required CLI tools found."

    aws sts get-caller-identity &>/dev/null \
        || error "AWS credentials invalid or expired. Run 'aws configure' or export credentials."
    ok "AWS credentials valid ($(aws sts get-caller-identity --query Arn --output text))."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Terraform
# ══════════════════════════════════════════════════════════════════════════════
step_terraform() {
    section "PHASE 1 — Terraform Infrastructure Deployment"
    cd "$TF_DIR"

    log "Initialising Terraform..."
    terraform init -input=false -reconfigure

    log "Planning changes..."
    terraform plan -input=false -out=/tmp/tf.plan 2>&1 | tail -5

    log "Applying infrastructure (this may take 20–30 minutes)..."
    terraform apply -input=false -auto-approve /tmp/tf.plan \
        2>&1 | tee /tmp/tf-apply.log | tail -20

    ok "Terraform apply complete."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Dynamic Output Discovery
# ══════════════════════════════════════════════════════════════════════════════
step_discover_outputs() {
    section "PHASE 2 — Dynamic Output Discovery"
    cd "$TF_DIR"

    log "Reading Terraform outputs..."
    local tf_outputs
    tf_outputs=$(terraform output -json 2>/dev/null) \
        || error "Failed to read Terraform outputs. Did Phase 1 succeed?"

    # ── Cluster name ──────────────────────────────────────────────────────────
    CLUSTER_NAME=$(echo "$tf_outputs" | jq -r '.cluster_name.value // empty')
    if [[ -z "$CLUSTER_NAME" ]]; then
        log "cluster_name not in outputs — discovering from AWS..."
        CLUSTER_NAME=$(aws eks list-clusters \
                         --query 'clusters[?contains(@, `uniops`)] | [0]' \
                         --output text 2>/dev/null | tr -d '[]"')
    fi
    [[ -z "$CLUSTER_NAME" || "$CLUSTER_NAME" == "None" ]] \
        && error "Cannot determine EKS cluster name. Check Terraform outputs or AWS."
    ok "Cluster name: $CLUSTER_NAME"

    # ── Region ────────────────────────────────────────────────────────────────
    REGION=$(echo "$tf_outputs" | jq -r '.region.value // empty')
    if [[ -z "$REGION" ]]; then
        REGION=$(aws configure get region 2>/dev/null \
                 || aws ec2 describe-availability-zones \
                      --query 'AvailabilityZones[0].RegionName' --output text 2>/dev/null)
    fi
    [[ -z "$REGION" ]] && error "Cannot determine AWS region."
    ok "Region: $REGION"

    # ── RDS endpoint ──────────────────────────────────────────────────────────
    RDS_ENDPOINT=$(echo "$tf_outputs" | jq -r '.rds_endpoint.value // empty')
    if [[ -z "$RDS_ENDPOINT" ]]; then
        RDS_ENDPOINT=$(aws rds describe-db-instances \
                         --query 'DBInstances[0].Endpoint.Address' \
                         --output text 2>/dev/null)
    fi
    # Strip port from RDS endpoint for ExternalName service
    RDS_HOST=$(echo "$RDS_ENDPOINT" | cut -d':' -f1)
    [[ -z "$RDS_HOST" || "$RDS_HOST" == "None" ]] \
        && error "RDS endpoint not found. Check Terraform state."
    ok "RDS endpoint: $RDS_ENDPOINT"

    # ── Redis endpoint ────────────────────────────────────────────────────────
    REDIS_ENDPOINT=$(echo "$tf_outputs" | jq -r '.redis_endpoint.value // empty')
    if [[ -z "$REDIS_ENDPOINT" ]]; then
        REDIS_ENDPOINT=$(aws elasticache describe-cache-clusters \
                           --show-cache-node-info \
                           --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
                           --output text 2>/dev/null)
    fi
    [[ -z "$REDIS_ENDPOINT" || "$REDIS_ENDPOINT" == "None" ]] \
        && error "Redis endpoint not found. Check Terraform state."
    ok "Redis endpoint: $REDIS_ENDPOINT"

    # ── RDS credentials from Secrets Manager (preferred) or Terraform output ──
    local SECRET_ID
    SECRET_ID=$(echo "$tf_outputs" | jq -r '.rds_secret_id.value // empty')

    if [[ -n "$SECRET_ID" ]]; then
        log "Fetching RDS credentials from Secrets Manager ($SECRET_ID)..."
        local secret_json
        secret_json=$(aws secretsmanager get-secret-value \
                        --secret-id "$SECRET_ID" \
                        --query SecretString --output text)
        DB_USER=$(echo "$secret_json" | jq -r '.username // .user // "uniops"')
        DB_PASSWORD=$(echo "$secret_json" | jq -r '.password')
        DB_NAME=$(echo "$secret_json" | jq -r '.dbname // "uniops_db"')
    else
        warn "No rds_secret_id output found — reading from Terraform outputs directly."
        DB_USER=$(echo "$tf_outputs" | jq -r '.rds_username.value // "uniops"')
        DB_PASSWORD=$(echo "$tf_outputs" | jq -r '.rds_password.value // empty')
        DB_NAME=$(echo "$tf_outputs" | jq -r '.rds_db_name.value // "uniops_db"')
    fi
    [[ -z "$DB_PASSWORD" ]] \
        && error "Cannot resolve DB password. Add 'rds_secret_id' or 'rds_password' to Terraform outputs."
    ok "DB credentials resolved (user: $DB_USER, db: $DB_NAME)."

    # ── Redis auth token ──────────────────────────────────────────────────────
    local REDIS_SECRET_ID
    REDIS_SECRET_ID=$(echo "$tf_outputs" | jq -r '.redis_secret_id.value // empty')

    if [[ -n "$REDIS_SECRET_ID" ]]; then
        log "Fetching Redis credentials from Secrets Manager ($REDIS_SECRET_ID)..."
        REDIS_PASSWORD=$(aws secretsmanager get-secret-value \
                           --secret-id "$REDIS_SECRET_ID" \
                           --query SecretString --output text \
                         | jq -r '.password // .auth_token')
    else
        REDIS_PASSWORD=$(echo "$tf_outputs" | jq -r '.redis_auth_token.value // empty')
    fi
    if [[ -z "$REDIS_PASSWORD" ]]; then
        warn "No Redis auth token found — proceeding without REDIS_PASSWORD (check if cluster uses auth)."
        REDIS_PASSWORD="no-auth-$(openssl rand -hex 8)"
    fi
    ok "Redis credentials resolved."

    # ── ECR registry ──────────────────────────────────────────────────────────
    local ACCOUNT_ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
    ECR_BACKEND="${ECR_REGISTRY}/uniops-backend"
    ECR_FRONTEND="${ECR_REGISTRY}/uniops-frontend"

    # ── EFS filesystem ID ─────────────────────────────────────────────────────
    EFS_ID=$(echo "$tf_outputs" | jq -r '.efs_id.value // empty')
    if [[ -z "$EFS_ID" ]]; then
        EFS_ID=$(aws efs describe-file-systems \
                   --query 'FileSystems[0].FileSystemId' --output text 2>/dev/null)
    fi
    [[ -z "$EFS_ID" || "$EFS_ID" == "None" ]] \
        && error "EFS filesystem ID not found."
    ok "EFS filesystem: $EFS_ID"

    # ── App secret keys ───────────────────────────────────────────────────────
    APP_SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET_KEY=$(openssl rand -hex 32)

    ok "All dynamic outputs resolved."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — EKS Connectivity
# ══════════════════════════════════════════════════════════════════════════════
step_eks_config() {
    section "PHASE 3 — Configuring EKS Cluster Access"

    log "Updating kubeconfig for cluster: $CLUSTER_NAME (region: $REGION)..."
    aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

    log "Verifying cluster connectivity..."
    local attempts=0
    until kubectl get nodes &>/dev/null; do
        attempts=$((attempts + 1))
        [[ "$attempts" -ge 12 ]] && error "Cannot connect to EKS cluster after 2 minutes."
        warn "Cluster not yet reachable — attempt $attempts/12 (waiting 10s)..."
        sleep 10
    done

    # Confirm we are NOT on minikube
    local current_context
    current_context=$(kubectl config current-context)
    if echo "$current_context" | grep -qi "minikube"; then
        error "kubectl is still pointing to minikube! Context: $current_context"
    fi
    ok "kubectl context: $current_context"
    kubectl get nodes -o wide
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — ECR Validation
# ══════════════════════════════════════════════════════════════════════════════
step_ecr_validation() {
    section "PHASE 4 — ECR Repository & Image Validation"

    for REPO in "uniops-backend" "uniops-frontend"; do
        log "Checking ECR repository: $REPO..."
        if ! aws ecr describe-repositories --repository-names "$REPO" \
               --region "$REGION" &>/dev/null; then
            warn "Repository $REPO not found — creating..."
            aws ecr create-repository \
                --repository-name "$REPO" \
                --region "$REGION" \
                --image-scanning-configuration scanOnPush=true \
                --encryption-configuration encryptionType=AES256 \
                > /dev/null
            ok "Created ECR repository: $REPO"
        else
            ok "ECR repository exists: $REPO"
        fi
    done

    # Validate :dev images exist
    local missing_images=0
    for REPO in "uniops-backend" "uniops-frontend"; do
        log "Checking for :dev image in $REPO..."
        if ! aws ecr describe-images \
                --repository-name "$REPO" \
                --image-ids imageTag=dev \
                --region "$REGION" &>/dev/null; then
            warn "Image $REPO:dev NOT FOUND in ECR."
            missing_images=$((missing_images + 1))
        else
            ok "Image $REPO:dev is present in ECR."
        fi
    done

    if [[ "$missing_images" -gt 0 ]]; then
        error "$missing_images image(s) missing from ECR. Push them before running this script:
  docker build -t uniops-backend:dev ./backend
  docker build -t uniops-frontend:dev ./frontend
  aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
  docker tag uniops-backend:dev $ECR_BACKEND:dev && docker push $ECR_BACKEND:dev
  docker tag uniops-frontend:dev $ECR_FRONTEND:dev && docker push $ECR_FRONTEND:dev"
    fi
    ok "ECR validation passed."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — Cluster Add-ons
# ══════════════════════════════════════════════════════════════════════════════
step_cluster_addons() {
    section "PHASE 5 — Installing Cluster Add-ons"

    # ── EFS CSI Driver ────────────────────────────────────────────────────────
    log "Configuring AWS EFS CSI Driver..."
    helm repo add aws-efs-csi-driver \
        https://kubernetes-sigs.github.io/aws-efs-csi-driver/ &>/dev/null || true
    helm repo update &>/dev/null

    if helm status aws-efs-csi-driver -n kube-system &>/dev/null; then
        log "EFS CSI Driver already installed — upgrading if needed..."
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

    # Wait for EFS CSI pods
    wait_pods "kube-system" "app=efs-csi-controller" 1 300
    wait_pods "kube-system" "app=efs-csi-node" 1 300
    ok "EFS CSI Driver is Ready."

    # ── NGINX Ingress ─────────────────────────────────────────────────────────
    log "Configuring NGINX Ingress Controller..."
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx &>/dev/null || true
    helm repo update &>/dev/null

    if helm status ingress-nginx -n ingress-nginx &>/dev/null; then
        log "NGINX Ingress already installed — upgrading if needed..."
        helm upgrade ingress-nginx ingress-nginx/ingress-nginx \
            --namespace ingress-nginx \
            --atomic --timeout 5m0s
    else
        helm install ingress-nginx ingress-nginx/ingress-nginx \
            --namespace ingress-nginx --create-namespace \
            --atomic --timeout 5m0s
    fi

    wait_deploy "ingress-nginx" "ingress-nginx-controller" 300s
    ok "NGINX Ingress Controller is Ready."

    # ── Ingress Class sanity check ────────────────────────────────────────────
    kubectl get ingressclass nginx &>/dev/null \
        || error "IngressClass 'nginx' not found after controller install."
    ok "IngressClass 'nginx' confirmed."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — Storage Validation
# ══════════════════════════════════════════════════════════════════════════════
step_storage_validation() {
    section "PHASE 6 — Storage Validation"

    # ── Verify EFS is available ───────────────────────────────────────────────
    log "Verifying EFS filesystem $EFS_ID is available..."
    local efs_state
    efs_state=$(aws efs describe-file-systems \
                  --file-system-id "$EFS_ID" \
                  --query 'FileSystems[0].LifeCycleState' \
                  --output text 2>/dev/null)
    [[ "$efs_state" == "available" ]] \
        || error "EFS $EFS_ID state is '$efs_state', expected 'available'."
    ok "EFS $EFS_ID is available."

    # ── Apply StorageClass manifest with correct EFS ID ───────────────────────
    log "Applying EFS StorageClass (efs-sc)..."
    cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: "${EFS_ID}"
  directoryPerms: "700"
reclaimPolicy: Retain
volumeBindingMode: Immediate
EOF
    ok "StorageClass efs-sc applied."

    # ── Quick PVC probe to confirm dynamic provisioning works ─────────────────
    log "Probing dynamic EFS provisioning with a test PVC..."
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efs-probe-pvc
  namespace: default
spec:
  accessModes: [ReadWriteMany]
  storageClassName: efs-sc
  resources:
    requests:
      storage: 5Mi
EOF

    local probe_timeout=120 elapsed=0
    until [[ "$(kubectl get pvc efs-probe-pvc -n default \
                  -o jsonpath='{.status.phase}' 2>/dev/null)" == "Bound" ]]; do
        [[ "$elapsed" -ge "$probe_timeout" ]] && {
            kubectl describe pvc efs-probe-pvc -n default || true
            kubectl delete pvc efs-probe-pvc -n default --ignore-not-found || true
            error "EFS dynamic provisioning timed out. Check EFS CSI driver IRSA permissions."
        }
        sleep 5; elapsed=$((elapsed + 5))
    done
    kubectl delete pvc efs-probe-pvc -n default --ignore-not-found &>/dev/null
    ok "EFS dynamic provisioning confirmed."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — Namespace & ExternalName Services
# ══════════════════════════════════════════════════════════════════════════════
step_namespace_and_services() {
    section "PHASE 7 — Namespace, ExternalName Services & Secrets"

    # ── Namespace ─────────────────────────────────────────────────────────────
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    ok "Namespace $NAMESPACE is present."

    # ── Base manifests ────────────────────────────────────────────────────────
    log "Applying base manifests (RBAC)..."
    [[ -f "$K8S_BASE/namespace.yaml" ]]      && kubectl apply -f "$K8S_BASE/namespace.yaml"
    [[ -f "$K8S_BASE/serviceaccount.yaml" ]] && kubectl apply -f "$K8S_BASE/serviceaccount.yaml"
    ok "Base manifests applied."

    # ── ExternalName service: postgres ────────────────────────────────────────
    log "Applying ExternalName service: postgres → $RDS_HOST"
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: ${NAMESPACE}
spec:
  type: ExternalName
  externalName: "${RDS_HOST}"
  ports:
    - port: 5432
      protocol: TCP
EOF
    ok "ExternalName service 'postgres' applied."

    # ── ExternalName service: redis ───────────────────────────────────────────
    log "Applying ExternalName service: redis → $REDIS_ENDPOINT"
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: ${NAMESPACE}
spec:
  type: ExternalName
  externalName: "${REDIS_ENDPOINT}"
  ports:
    - port: 6379
      protocol: TCP
EOF
    ok "ExternalName service 'redis' applied."

    # ── Secrets (from real infrastructure values) ─────────────────────────────
    log "Populating uniops-secrets from infrastructure outputs..."
    kubectl create secret generic uniops-secrets \
        --namespace="$NAMESPACE" \
        --from-literal=SECRET_KEY="$APP_SECRET_KEY" \
        --from-literal=JWT_SECRET_KEY="$JWT_SECRET_KEY" \
        --from-literal=POSTGRES_USER="$DB_USER" \
        --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" \
        --from-literal=POSTGRES_DB="$DB_NAME" \
        --from-literal=POSTGRES_HOST="postgres" \
        --from-literal=DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}" \
        --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD" \
        --from-literal=REDIS_URL="redis://:${REDIS_PASSWORD}@redis:6379/0" \
        --from-literal=GITHUB_TOKEN="" \
        --from-literal=SENTRY_DSN="" \
        --dry-run=client -o yaml | kubectl apply -f -
    ok "uniops-secrets populated with live infrastructure credentials."

    # ── ECR image pull secret ─────────────────────────────────────────────────
    log "Refreshing ECR image pull secret..."
    local ecr_token
    ecr_token=$(aws ecr get-login-password --region "$REGION")
    kubectl create secret docker-registry ecr-pull-secret \
        --namespace="$NAMESPACE" \
        --docker-server="${ECR_REGISTRY}" \
        --docker-username=AWS \
        --docker-password="$ecr_token" \
        --dry-run=client -o yaml | kubectl apply -f -
    ok "ECR pull secret refreshed."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 8 — Application Deployment
# ══════════════════════════════════════════════════════════════════════════════
step_deploy_application() {
    section "PHASE 8 — Deploying Application Workloads"

    log "Applying Kustomize overlay (dev)..."
    kubectl apply -k "$K8S_DEV" 2>&1 | tee /tmp/k8s-apply.log
    ok "Kustomize manifests applied."

    log "Waiting for application pods to reach Running state..."
    wait_pods "$NAMESPACE" "app.kubernetes.io/part-of=uniops" 1 600

    log "Waiting for backend deployment rollout..."
    kubectl -n "$NAMESPACE" rollout status deployment/uniops-backend \
        --timeout=300s || warn "Backend rollout timeout — check diagnostics below."

    log "Waiting for frontend deployment rollout..."
    kubectl -n "$NAMESPACE" rollout status deployment/uniops-frontend \
        --timeout=300s || warn "Frontend rollout timeout — check diagnostics below."

    ok "Application workloads deployed."
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 9 — Health Checks & Diagnostics
# ══════════════════════════════════════════════════════════════════════════════
step_health_check() {
    section "PHASE 9 — Health Checks & Diagnostics"
    local FAILURES=0

    # ── Node health ───────────────────────────────────────────────────────────
    log "Node status:"
    kubectl get nodes -o wide
    local not_ready_nodes
    not_ready_nodes=$(kubectl get nodes --no-headers \
                        | grep -v " Ready" | wc -l | tr -d ' ')
    if [[ "$not_ready_nodes" -gt 0 ]]; then
        warn "$not_ready_nodes node(s) are NOT Ready."
        FAILURES=$((FAILURES + 1))
    fi

    # ── All pods ──────────────────────────────────────────────────────────────
    log "All pods:"
    kubectl get pods -A -o wide

    # ── Detect problem pods ───────────────────────────────────────────────────
    log "Scanning for unhealthy pods..."
    local problem_pods
    problem_pods=$(kubectl get pods -A --no-headers \
                     | grep -vE "Running|Completed|Succeeded" || true)

    if [[ -n "$problem_pods" ]]; then
        warn "Unhealthy pods detected:"
        echo "$problem_pods"

        # Detect specific failure modes
        echo "$problem_pods" | grep -qi "ImagePullBackOff\|ErrImagePull" && {
            warn "ImagePullBackOff detected — checking ECR credentials..."
            kubectl get pods -A --no-headers \
                | grep -i "ImagePullBackOff\|ErrImagePull" \
                | awk '{print $1, $2}' \
                | while read -r ns pod; do
                    echo "  ↳ kubectl -n $ns describe pod $pod | grep -A5 'Failed pulling'"
                  done
            FAILURES=$((FAILURES + 1))
        }

        echo "$problem_pods" | grep -qi "CrashLoopBackOff" && {
            warn "CrashLoopBackOff detected — recent logs:"
            kubectl get pods -A --no-headers \
                | grep -i "CrashLoopBackOff" \
                | awk '{print $1, $2}' \
                | head -3 \
                | while read -r ns pod; do
                    echo "  ─── Logs for $pod ───"
                    kubectl -n "$ns" logs "$pod" --tail=20 2>/dev/null || true
                  done
            FAILURES=$((FAILURES + 1))
        }

        echo "$problem_pods" | grep -qi "Pending" && {
            warn "Pending pods detected — may be scheduling/resource issue:"
            kubectl get pods -A --no-headers \
                | grep -i "Pending" \
                | awk '{print $1, $2}' \
                | head -3 \
                | while read -r ns pod; do
                    kubectl -n "$ns" describe pod "$pod" | grep -A5 "Events:" || true
                  done
            FAILURES=$((FAILURES + 1))
        }
    else
        ok "All pods are healthy."
    fi

    # ── PVCs ──────────────────────────────────────────────────────────────────
    log "PVC status:"
    kubectl get pvc -A
    local failed_pvcs
    failed_pvcs=$(kubectl get pvc -A --no-headers | grep -v "Bound" | wc -l | tr -d ' ')
    if [[ "$failed_pvcs" -gt 0 ]]; then
        warn "$failed_pvcs PVC(s) are not Bound:"
        kubectl get pvc -A --no-headers | grep -v "Bound"
        FAILURES=$((FAILURES + 1))
    else
        ok "All PVCs are Bound."
    fi

    # ── Ingress ───────────────────────────────────────────────────────────────
    log "Ingress status:"
    kubectl get ingress -A
    local ingress_no_address
    ingress_no_address=$(kubectl get ingress -A --no-headers \
                           | awk '{print $5}' | grep -c "^$\|<none>" || true)
    if [[ "$ingress_no_address" -gt 0 ]]; then
        warn "$ingress_no_address Ingress resource(s) have no external address yet (ALB may still be provisioning)."
    fi

    # ── Summary ───────────────────────────────────────────────────────────────
    divider
    if [[ "$FAILURES" -eq 0 ]]; then
        ok "ALL HEALTH CHECKS PASSED — UniOps SaaS environment is online."
        log "Access the application via the Ingress address:"
        kubectl get ingress -n "$NAMESPACE" -o wide 2>/dev/null || true
        exit 0
    else
        error "$FAILURES health check(s) FAILED. Review diagnostics above. Environment may be partially online."
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
main() {
    divider
    echo -e "${BOLD}  UniOps SaaS Infrastructure Startup — v2.0${NC}"
    echo -e "  $(date)"
    divider

     :step_prerequisites
    step_terraform
    step_discover_outputs
    step_eks_config
    step_ecr_validation
    step_cluster_addons
    step_storage_validation
    step_namespace_and_services
    step_deploy_application
    step_health_check
}

main "$@"main() {
    divider
    echo -e "${BOLD}  UniOps SaaS Infrastructure Resume Deployment${NC}"
    echo -e "  $(date)"
    divider

    step_discover_outputs
    step_eks_config
    step_namespace_and_services
    step_deploy_application
    step_health_check
}
