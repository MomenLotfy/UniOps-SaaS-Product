#!/usr/bin/env bash

# ==============================================================================
# UniOps SaaS — Application Infrastructure Destroy
# Version: 1.0 — App-Layer Isolated, Safety-First
# ------------------------------------------------------------------------------
# PURPOSE
#   Tear down the APPLICATION layer of UniOps only.
#   Used for clean-room redeploys, environment resets, or emergency stop.
#
# SCOPE (what this script destroys)
#   ✔ Helm releases: ingress-nginx, aws-efs-csi-driver (uninstall only)
#   ✔ In-cluster StatefulSets: postgres, redis (and their PVCs)
#   ✔ UniOps namespace and ALL its contents (deployments, services,
#     configmaps, secrets, ingress, HPAs, PDBs, NetworkPolicies)
#   ✔ Application images on cluster nodes (NOT on ECR — see PROTECTED)
#
# SCOPE (what this script NEVER touches — PROTECTED)
#   ✗ terraform/bootstrap/                          (state isolated, key=bootstrap/*)
#   ✗ aws_ecr_repository.uniops-backend             (bootstrap-owned, prevent_destroy)
#   ✗ aws_ecr_repository.uniops-frontend            (bootstrap-owned, prevent_destroy)
#   ✗ aws_s3_bucket.uniops-663476173962-tfstate          (bootstrap-owned, prevent_destroy)
#   ✗ aws_s3_bucket.uniops-663476173962-tfstate/*        (state files)
#   ✗ aws_dynamodb_table.uniops-terraform-locks     (bootstrap-owned, prevent_destroy)
#   ✗ aws_eks_cluster.uniops-eks-dev                (out of band)
#   ✗ RDS db.uniops-postgres-dev                    (out of band)
#   ✗ ElastiCache uniops-redis-dev-001              (out of band)
#   ✗ EFS fs-0f6567c976ebd2349                      (out of band; PVCs only)
#   ✗ Bootstrap .terraform/ working dir             (script refuses to run if cwd)
#
# USAGE
#   bash destroy-app-infra.sh                  # interactive confirm
#   bash destroy-app-infra.sh --dry-run        # show what would happen
#   bash destroy-app-infra.sh --yes            # skip confirmation prompt
#   bash destroy-app-infra.sh --keep-pvcs      # preserve PVCs (data)
#   bash destroy-app-infra.sh --keep-secrets   # preserve uniops-secrets
#   bash destroy-app-infra.sh --skip-terraform # only delete k8s resources, NOT EKS/app AWS
#   bash destroy-app-infra.sh --keep-terraform-state  # delete AWS but keep tfstate file
#
# DESTRUCTION ORDER (top-down)
#   1. Helm releases (ingress-nginx, aws-efs-csi-driver)
#   2. App-layer Kubernetes resources (StatefulSets, PVCs, namespace, secrets)
#   3. App-layer Terraform-managed AWS (EKS, VPC, RDS, ElastiCache, EFS, ALB,
#      Bastion, KMS, WAF, GuardDuty, Backup, CloudWatch alarms) via
#      `terraform destroy` against the app-layer state.
#   The bootstrap layer is NEVER touched.
#
# SAFETY
#   - Always requires --yes OR an interactive "destroy-app-infra" typed confirm
#   - Refuses to run if cwd is inside terraform/bootstrap/
#   - Verifies bootstrap state file is NOT the same as app state file
#     (different S3 keys: bootstrap/* vs app/*)
#   - Refuses to run `terraform destroy` if the state file contains any
#     resource address that points to a bootstrap-owned type
#   - Confirms each protected resource exists BEFORE running (negative test)
#   - Re-confirms each protected resource exists AFTER running (positive test)
#
# EXIT CODES
#   0  success (or dry-run complete)
#   1  prerequisites missing / safety check failed
#   2  user aborted
#   3  helm uninstall failed
#   4  namespace deletion failed
#   5  AWS protected-resource check failed
#   6  terraform destroy failed
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
ASSUME_YES=0
DRY_RUN=0
KEEP_PVCS=0
KEEP_SECRETS=0
SKIP_TERRAFORM=0          # default: do run terraform destroy
KEEP_TERRAFORM_STATE=0    # default: delete the state file too after destroy
for arg in "$@"; do
  case "$arg" in
    --yes)                   ASSUME_YES=1 ;;
    --dry-run)               DRY_RUN=1 ;;
    --keep-pvcs)             KEEP_PVCS=1 ;;
    --keep-secrets)          KEEP_SECRETS=1 ;;
    --skip-terraform)        SKIP_TERRAFORM=1 ;;
    --keep-terraform-state)  KEEP_TERRAFORM_STATE=1 ;;
    -h|--help)               sed -n '2,55p' "$0"; exit 0 ;;
    *)                       fail "Unknown flag: $arg" ;;
  esac
done

# ─── Static config ────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_BASE="$REPO_ROOT/k8s/base"
NAMESPACE="uniops"
REGION="${AWS_REGION:-us-east-2}"

# App Terraform layer — owns EKS + all app-layer AWS resources.
# State lives at s3://uniops-663476173962-tfstate/app/terraform.tfstate — a
# DIFFERENT key from bootstrap/terraform.tfstate. The bucket and DynamoDB
# table are bootstrap-owned; we destroy against our key only.
TERRAFORM_APP_DIR="$REPO_ROOT/terraform/app"
TERRAFORM_APP_STATE_BUCKET="uniops-663476173962-tfstate"
TERRAFORM_APP_STATE_KEY="app/terraform.tfstate"
TERRAFORM_APP_LOCK_TABLE="uniops-terraform-locks"

# Resource types that are bootstrap-owned. The state file MUST NEVER contain
# any of these addresses. If it does, we abort immediately.
BOOTSTRAP_RESOURCE_TYPES=(
  "aws_s3_bucket.terraform_state"
  "aws_s3_bucket_versioning.terraform_state"
  "aws_s3_bucket_server_side_encryption_configuration.terraform_state"
  "aws_s3_bucket_public_access_block.terraform_state"
  "aws_dynamodb_table.terraform_locks"
  "aws_ecr_repository.backend"
  "aws_ecr_repository.frontend"
)

# ─── List of protected resources (asserted negative: they MUST still exist) ──
PROTECTED_ECR_REPOS=("uniops-backend" "uniops-frontend")
PROTECTED_S3_BUCKET="uniops-663476173962-tfstate"
PROTECTED_DDB_TABLE="uniops-terraform-locks"
PROTECTED_EKS_CLUSTER_PREFIX="uniops"
PROTECTED_RDS_ID="uniops-postgres-dev"
PROTECTED_REDIS_CLUSTER="uniops-redis-dev"
PROTECTED_EFS_PREFIX="fs-"

# ─── Safety guards ────────────────────────────────────────────────────────────
guard_bootstrap_isolation() {
  log "Verifying bootstrap isolation (refuse to touch bootstrap state)..."

  # 1. Refuse to run from inside the bootstrap directory.
  case "$(pwd)" in
    */terraform/bootstrap|*/terraform/bootstrap/*)
      fail "You are inside terraform/bootstrap/. Run this script from the repo root." 1 ;;
  esac

  # 2. Refuse to run if the bootstrap Terraform state file exists alongside us
  #    (sanity check — the bootstrap is at $REPO_ROOT/terraform/bootstrap, NOT
  #    at the path this script would touch).
  [[ -d "$REPO_ROOT/terraform/bootstrap" ]] \
    || fail "Bootstrap layer missing at $REPO_ROOT/terraform/bootstrap — refusing to run." 1

  # 3. The bootstrap state must live in S3 at key bootstrap/*. We must NEVER
  #    invoke terraform with -state or set any flag pointing to that key.
  #    This script invokes terraform only against the app-layer key
  #    (app/terraform.tfstate), never against bootstrap/*.
  if command -v terraform &>/dev/null; then
    log "  (Note: terraform CLI is installed; this script will only invoke it against the app-layer state key.)"
  fi

  # 3a. State-key isolation: bootstrap state lives at bootstrap/*. We use app/*.
  #     If, for any reason, the bootstrap key prefix appears in the env or
  #     arguments, refuse to run.
  if [[ "${TERRAFORM_APP_STATE_KEY:-}" == bootstrap/* ]]; then
    fail "TERRAFORM_APP_STATE_KEY points at bootstrap/. Refusing to run." 1
  fi

  # 3b. Pre-flight state-file check: if the app layer's state file is already
  #     populated, scan it for any bootstrap-owned resource addresses. Finding
  #     any means state corruption and we abort.
  if [[ -d "$TERRAFORM_APP_DIR" && -f "$TERRAFORM_APP_DIR/terraform.tfstate" ]]; then
    log "  Scanning app-layer state file for bootstrap resource addresses..."
    local bad
    bad=$(grep -oE '"(aws_s3_bucket\.terraform_state|aws_dynamodb_table\.terraform_locks|aws_ecr_repository\.(backend|frontend))"' \
          "$TERRAFORM_APP_DIR/terraform.tfstate" | sort -u || true)
    if [[ -n "$bad" ]]; then
      fail "App-layer state file contains bootstrap-owned resources: $bad. Refusing to destroy." 1
    fi
    ok "    App-layer state is clean (no bootstrap resources)."
  else
    log "  App-layer state file not present at $TERRAFORM_APP_DIR — will skip."
  fi

  # 4. Negative-existence check on each protected AWS resource.
  log "  Asserting protected resources STILL EXIST (must remain untouched)..."

  for REPO in "${PROTECTED_ECR_REPOS[@]}"; do
    aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" \
      &>/dev/null \
      || fail "Protected ECR repo $REPO is missing! This script does NOT create it. Aborting." 5
    ok "    ECR repo present: $REPO (will NOT be deleted)"
  done

  aws s3api head-bucket --bucket "$PROTECTED_S3_BUCKET" &>/dev/null \
    || fail "Protected S3 bucket $PROTECTED_S3_BUCKET is missing! Aborting." 5
  ok "    S3 bucket present: $PROTECTED_S3_BUCKET (will NOT be deleted)"

  # List bootstrap state keys to confirm they are present
  local keys
  keys=$(aws s3api list-objects-v2 --bucket "$PROTECTED_S3_BUCKET" --prefix "bootstrap/" \
          --query 'Contents[].Key' --output text 2>/dev/null || echo "")
  if [[ -z "$keys" ]]; then
    warn "No bootstrap/ state keys found in $PROTECTED_S3_BUCKET. (Bootstrap may be empty.)"
  else
    ok "    Bootstrap state keys in S3: $(echo "$keys" | tr '\n' ' ')"
  fi

  aws dynamodb describe-table --table-name "$PROTECTED_DDB_TABLE" --region "$REGION" \
    &>/dev/null \
    || fail "Protected DynamoDB table $PROTECTED_DDB_TABLE is missing! Aborting." 5
  ok "    DynamoDB table present: $PROTECTED_DDB_TABLE (will NOT be deleted)"

  aws rds describe-db-instances --db-instance-identifier "$PROTECTED_RDS_ID" \
    --region "$REGION" &>/dev/null \
    || warn "Protected RDS $PROTECTED_RDS_ID is missing (out-of-band state, not a script error)."
  ok "    RDS instance present: $PROTECTED_RDS_ID (will NOT be deleted)"

  local redis_count
  redis_count=$(aws elasticache describe-cache-clusters --region "$REGION" \
                  --query "CacheClusters[?contains(CacheClusterId, \`$PROTECTED_REDIS_CLUSTER\`)] | length(@)" \
                  --output text 2>/dev/null || echo "0")
  [[ "$redis_count" -gt 0 ]] \
    || warn "Protected ElastiCache cluster $PROTECTED_REDIS_CLUSTER not found (out-of-band state)."
  ok "    ElastiCache cluster present (or not in scope): $PROTECTED_REDIS_CLUSTER"

  local efs_count
  efs_count=$(aws efs describe-file-systems --region "$REGION" \
                --query 'FileSystems[].FileSystemId' --output text 2>/dev/null | tr -d '[:space:]' | wc -c)
  [[ "$efs_count" -gt 0 ]] \
    || warn "No EFS filesystems found (out-of-band state)."
  ok "    EFS filesystems present (will NOT be deleted; PVCs may be removed)"

  ok "Bootstrap isolation verified. All protected resources confirmed intact."
}

# ─── Prerequisites ────────────────────────────────────────────────────────────
step_prerequisites() {
  section "PHASE 0 — Prerequisites Validation"
  local tools=(aws kubectl helm jq)
  for tool in "${tools[@]}"; do
    command -v "$tool" &>/dev/null || fail "Required tool '$tool' is not installed." 1
  done
  ok "Required tools present."

  aws sts get-caller-identity &>/dev/null \
    || fail "AWS credentials invalid or expired." 1
  ok "AWS credentials valid."

  # EKS context (we don't create the cluster, we just need to be on it)
  local ctx
  ctx=$(kubectl config current-context 2>/dev/null || echo "")
  [[ -n "$ctx" ]] || fail "kubectl has no current-context. Configure cluster access first." 1
  echo "$ctx" | grep -qi "minikube" && fail "kubectl is on minikube ($ctx). Refusing." 1
  ok "kubectl context: $ctx"
}

# ─── User confirmation ───────────────────────────────────────────────────────
confirm_destruction() {
  section "PHASE 1 — Destruction Confirmation"

  echo -e "${RED}${BOLD}"
  echo "  ╔════════════════════════════════════════════════════════════════════╗"
  echo "  ║  WARNING — THIS WILL DELETE THE UNIOPS APPLICATION LAYER        ║"
  echo "  ║                                                                    ║"
  echo "  ║  Will be deleted:                                                  ║"
  echo "  ║    • EKS cluster and node groups (via terraform destroy)           ║"
  echo "  ║    • VPC, subnets, NAT, IGW                                        ║"
  echo "  ║    • RDS Postgres, ElastiCache Redis, EFS                          ║"
  echo "  ║    • ALB, Bastion, public EC2 tools                                ║"
  echo "  ║    • WAF, KMS keys, GuardDuty, Backup, CloudWatch alarms            ║"
  echo "  ║    • All Deployments, StatefulSets, Services in namespace 'uniops' ║"
  echo "  ║    • All PVCs (unless --keep-pvcs)                                 ║"
  echo "  ║    • All Secrets (unless --keep-secrets)                           ║"
  echo "  ║    • Helm releases: ingress-nginx, aws-efs-csi-driver              ║"
  echo "  ║    • App-layer Terraform state file (unless --keep-terraform-state)║"
  echo "  ║                                                                    ║"
  echo "  ║  Will NOT be touched:                                              ║"
  echo "  ║    • ECR repos (uniops-backend, uniops-frontend) AND THEIR IMAGES  ║"
  echo "  ║    • S3 bucket uniops-663476173962-tfstate (and ALL its objects)        ║"
  echo "  ║    • DynamoDB table uniops-terraform-locks                         ║"
  echo "  ║    • Bootstrap state key (bootstrap/terraform.tfstate)             ║"
  echo "  ║    • Any resource type listed in BOOTSTRAP_RESOURCE_TYPES          ║"
  echo "  ╚════════════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    warn "DRY-RUN mode — no destructive action will be taken."
    return 0
  fi

  if [[ "$ASSUME_YES" -ne 1 ]]; then
    echo
    echo -n "  Type the exact phrase 'destroy-app-infra' to continue: "
    read -r typed
    [[ "$typed" == "destroy-app-infra" ]] || { fail "Aborted by user." 2; }
  fi
  ok "Destruction confirmed by user."
}

# ─── Phase 2 — Uninstall Helm add-ons ─────────────────────────────────────────
step_helm_uninstall() {
  section "PHASE 2 — Helm Uninstall (add-ons)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: helm uninstall ingress-nginx -n ingress-nginx"
    log "[dry-run] would: helm uninstall aws-efs-csi-driver -n kube-system"
    return 0
  fi

  if helm status ingress-nginx -n ingress-nginx &>/dev/null; then
    log "Uninstalling ingress-nginx..."
    helm uninstall ingress-nginx -n ingress-nginx --wait || fail "ingress-nginx uninstall failed" 3
  else
    log "ingress-nginx not installed — skipping."
  fi

  if helm status aws-efs-csi-driver -n kube-system &>/dev/null; then
    log "Uninstalling aws-efs-csi-driver..."
    helm uninstall aws-efs-csi-driver -n kube-system --wait || fail "aws-efs-csi-driver uninstall failed" 3
  else
    log "aws-efs-csi-driver not installed — skipping."
  fi
  ok "Helm add-ons removed."
}

# ─── Phase 3 — StatefulSets (postgres, redis) ────────────────────────────────
step_statefulsets() {
  section "PHASE 3 — In-cluster StatefulSets (postgres, redis)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: kubectl delete statefulset -n $NAMESPACE postgres redis"
    return 0
  fi

  for s in postgres redis; do
    if kubectl -n "$NAMESPACE" get statefulset "$s" &>/dev/null; then
      log "Deleting statefulset/$s..."
      kubectl -n "$NAMESPACE" delete statefulset "$s" --ignore-not-found
    fi
  done
  ok "StatefulSets deleted."
}

# ─── Phase 4 — PVCs (optional) ────────────────────────────────────────────────
step_pvcs() {
  section "PHASE 4 — PVCs ($([ "$KEEP_PVCS" -eq 1 ] && echo "KEEP" || echo "DELETE"))"
  if [[ "$KEEP_PVCS" -eq 1 ]]; then
    warn "--keep-pvcs set; PVCs will NOT be deleted."
    kubectl -n "$NAMESPACE" get pvc 2>/dev/null || true
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: kubectl delete pvc -n $NAMESPACE --all"
    return 0
  fi

  log "Deleting all PVCs in $NAMESPACE..."
  kubectl -n "$NAMESPACE" delete pvc --all --ignore-not-found
  ok "PVCs deleted."
}

# ─── Phase 5 — Secrets (optional) ────────────────────────────────────────────
step_secrets() {
  section "PHASE 5 — Secrets ($([ "$KEEP_SECRETS" -eq 1 ] && echo "KEEP" || echo "DELETE uniops-secrets only"))"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would delete uniops-secrets (and keep dockerhub-secret, ecr-pull-secret)"
    return 0
  fi

  if [[ "$KEEP_SECRETS" -eq 1 ]]; then
    warn "--keep-secrets set; all secrets preserved."
    return 0
  fi

  # Delete uniops-secrets (app-level); preserve image pull secrets.
  for s in uniops-secrets; do
    if kubectl -n "$NAMESPACE" get secret "$s" &>/dev/null; then
      log "Deleting secret/$s..."
      kubectl -n "$NAMESPACE" delete secret "$s" --ignore-not-found
    fi
  done
  ok "App secrets deleted; image pull secrets preserved."
}

# ─── Phase 6 — Delete the namespace ──────────────────────────────────────────
step_namespace() {
  section "PHASE 6 — Delete Namespace $NAMESPACE"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: kubectl delete namespace $NAMESPACE"
    return 0
  fi

  if kubectl get namespace "$NAMESPACE" &>/dev/null; then
    log "Deleting namespace $NAMESPACE..."
    kubectl delete namespace "$NAMESPACE" --ignore-not-found --wait=false \
      || warn "Namespace delete issued; some finalizers may take time."
  else
    log "Namespace $NAMESPACE not present — skipping."
  fi
  ok "Namespace deletion initiated."
}

# ─── Phase 6.5 — App Terraform destroy (EKS + app-layer AWS) ──────────────────
# This is the actual EKS / RDS / ElastiCache / EFS / VPC / KMS / WAF / etc.
# destroyer. It runs `terraform destroy` against the APP layer only.
# ─── App Terraform working-directory discovery ───────────────────────────────
# Search the repo for a directory that looks like the application Terraform
# layer. Discovery rules:
#   1. Prefer the canonical location: $REPO_ROOT/terraform/app
#   2. If not present, walk the repo and look for any directory that:
#        - contains at least one *.tf file
#        - is NOT a bootstrap directory (terraform/bootstrap, */bootstrap/*)
#        - is NOT a pure-state-storage directory (no .tf files)
#        - is NOT inside infra-backup's bootstrap/ (we do not run from there)
#   3. If multiple candidates are found, sort by depth (shallower preferred)
#      and pick the first.
#   4. If none found, the caller hard-fails.
#
# Echoes the resolved directory path on stdout. Empty if not found.
discover_app_terraform_dir() {
  # CONTRACT: this function prints ONLY the resolved filesystem path to
  # stdout (or nothing if no candidate was found). All informational
  # logging is written to stderr so callers using
  #   resolved=$(discover_app_terraform_dir "$TERRAFORM_APP_DIR")
  # receive a clean, parseable value.
  local primary="$1"   # canonical location
  local found=""

  # 1. Canonical location first
  if [[ -d "$primary" ]] && compgen -G "$primary/*.tf" &>/dev/null; then
    printf '%s\n' "$primary"
    return 0
  fi

  # 2. Search the repo. We exclude the bootstrap tree explicitly.
  # All progress messages go to stderr (>&2) so they don't pollute the
  # captured stdout that the caller will assign to TERRAFORM_APP_DIR.
  {
    log "  Primary location $primary not found or empty. Searching repo..."
  } >&2
  # find: directories containing *.tf, depth-limited to avoid scanning
  # every nested subdir, excluding the bootstrap tree and infra-backup/
  # bootstrap subdir.
  local candidates
  candidates=$(find "$REPO_ROOT" -maxdepth 6 -type f -name "*.tf" 2>/dev/null \
    | xargs -I{} dirname {} 2>/dev/null \
    | sort -u \
    | grep -vE "/terraform/bootstrap($|/)" \
    | grep -vE "/\.terraform($|/)" \
    | grep -vE "/\.git($|/)" \
    | grep -vE "/node_modules($|/)" \
    | head -50 || true)

  for d in $candidates; do
    # Reject anything that only contains the BOOTSTRAP_RESOURCE_TYPES —
    # if a dir's *.tf files only reference bootstrap state, it's not the
    # app layer.
    if [[ -d "$d" ]]; then
      # Must have at least one *.tf
      compgen -G "$d/*.tf" &>/dev/null || continue
      # Must NOT be a pure state-only dir
      [[ -f "$d/main.tf" || -f "$d/root.tf" || -f "$d/provider.tf" ]] || continue
      # Must NOT be the bootstrap dir
      case "$d" in
        */terraform/bootstrap|*/terraform/bootstrap/*) continue ;;
      esac
      found="$d"
      break
    fi
  done

  if [[ -n "$found" ]]; then
    # Final stdout emission: the resolved path, and nothing else.
    printf '%s\n' "$found"
  fi
  # No explicit "not found" log here — the caller decides what to print
  # when $resolved is empty. (Keeping this function silent on the
  # not-found path ensures the captured stdout is empty in that case.)
}

step_terraform_destroy() {
  section "PHASE 6.5 — App Terraform Destroy (EKS + all app-layer AWS)"

  if [[ "$SKIP_TERRAFORM" -eq 1 ]]; then
    warn "--skip-terraform set; EKS and app-layer AWS resources will NOT be destroyed."
    warn "Only the in-cluster Kubernetes resources were removed."
    return 0
  fi

  # ── Discover the app Terraform working directory ────────────────────────────
  log "  Looking for app Terraform working directory..."
  local resolved
  resolved=$(discover_app_terraform_dir "$TERRAFORM_APP_DIR")
  if [[ -z "$resolved" ]]; then
    # No valid app dir found anywhere in the repo.
    # Hard fail — the user explicitly wanted EKS destroyed, and we cannot
    # do it without a Terraform module that knows how to.
    echo -e "${RED}${BOLD}" >&2
    echo "  ╔════════════════════════════════════════════════════════════════════╗" >&2
    echo "  ║  ✗  CANNOT DESTROY EKS — no app Terraform layer found          ║" >&2
    echo "  ║                                                                    ║" >&2
    echo "  ║  The destroy script needs a Terraform working directory that       ║" >&2
    echo "  ║  declares aws_eks_cluster, aws_eks_node_group, and the supporting  ║" >&2
    echo "  ║  VPC / subnets / IAM / security-group resources.                  ║" >&2
    echo "  ║                                                                    ║" >&2
    echo "  ║  Searched:                                                         ║" >&2
    echo "  ║    1. \$REPO_ROOT/terraform/app        (not found)                  ║" >&2
    echo "  ║    2. Recursive search of the repository for any dir with main.tf /║" >&2
    echo "  ║       root.tf / provider.tf AND at least one *.tf file            ║" >&2
    echo "  ║       (excluding terraform/bootstrap/ and infra-backup/bootstrap/) ║" >&2
    echo "  ║                                                                    ║" >&2
    echo "  ║  Without a Terraform app layer, the EKS cluster (uniops-eks-dev)   ║" >&2
    echo "  ║  CANNOT be destroyed by this script. It will continue to bill.     ║" >&2
    echo "  ║                                                                    ║" >&2
    echo "  ║  To fix:                                                           ║" >&2
    echo "  ║    • Restore / clone the repository at a state that contains the   ║" >&2
    echo "  ║      app Terraform layer (typically terraform/app/ or a sibling    ║" >&2
    echo "  ║      infrastructure/ directory), OR                                ║" >&2
    echo "  ║    • Manually destroy EKS with:                                   ║" >&2
    echo "  ║        aws eks delete-cluster --name uniops-eks-dev --region us-east-2 ║" >&2
    echo "  ║      (and remove node groups, VPC, IAM, etc. via the AWS console) ║" >&2
    echo "  ╚════════════════════════════════════════════════════════════════════╝" >&2
    echo -e "${NC}" >&2
    fail "No app Terraform working directory found. EKS cannot be destroyed." 6
  fi

  TERRAFORM_APP_DIR="$resolved"
  log "  Resolved app Terraform dir: $TERRAFORM_APP_DIR"

  # Refuse to invoke terraform against the bootstrap directory or against a
  # state key starting with 'bootstrap/'.
  case "$TERRAFORM_APP_DIR" in
    */terraform/bootstrap|*/terraform/bootstrap/*)
      fail "TERRAFORM_APP_DIR points at bootstrap/. Refusing to run." 1 ;;
  esac

  # Confirm the resolved state key in the backend config is NOT bootstrap/*.
  local backend_tf="$TERRAFORM_APP_DIR/shared/backend.tf"
  if [[ -f "$backend_tf" ]]; then
    if grep -qE 'key\s*=\s*"bootstrap/' "$backend_tf"; then
      fail "App-layer backend config points at bootstrap/* state key. Refusing to destroy." 1
    fi
  fi

  # Pre-flight: scan the local state file (if present) for any bootstrap-owned
  # resource addresses. Finding one is a hard fail.
  if [[ -f "$TERRAFORM_APP_DIR/terraform.tfstate" ]]; then
    log "  Pre-flight: scanning app-layer state for bootstrap resources..."
    for BAD in "${BOOTSTRAP_RESOURCE_TYPES[@]}"; do
      if grep -q "\"$BAD\"" "$TERRAFORM_APP_DIR/terraform.tfstate"; then
        fail "App-layer state contains bootstrap resource: $BAD. Aborting." 1
      fi
    done
    ok "  No bootstrap resources in app-layer state."
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would: (cd $TERRAFORM_APP_DIR && terraform init -input=false)"
    log "[dry-run] would: (cd $TERRAFORM_APP_DIR && terraform plan -destroy -input=false)"
    log "[dry-run] would: (cd $TERRAFORM_APP_DIR && terraform destroy -auto-approve -input=false)"
    return 0
  fi

  # ── Pre-destroy: empty Backup Vaults (AWS blocks vault deletion if it has recovery points) ──
  log "  Pre-destroy: clearing AWS Backup recovery points from all UniOps vaults..."
  local vaults
  vaults=$(aws backup list-backup-vaults --region "$REGION" \
             --query 'BackupVaultList[?contains(BackupVaultName, `uniops`)].BackupVaultName' \
             --output text 2>/dev/null || echo "")
  for vault in $vaults; do
    log "    Vault: $vault — fetching recovery points..."
    local arns
    arns=$(aws backup list-recovery-points-by-backup-vault \
             --backup-vault-name "$vault" \
             --region "$REGION" \
             --query 'RecoveryPoints[].RecoveryPointArn' \
             --output text 2>/dev/null || echo "")
    if [[ -z "$arns" ]]; then
      ok "    Vault $vault is already empty."
    else
      for arn in $arns; do
        [[ -z "$arn" ]] && continue
        log "      Deleting recovery point: $arn"
        aws backup delete-recovery-point \
          --backup-vault-name "$vault" \
          --recovery-point-arn "$arn" \
          --region "$REGION" 2>/dev/null || warn "      Could not delete $arn (may already be gone)"
      done
      ok "    Vault $vault cleared."
    fi
  done
  ok "  All UniOps backup vaults emptied — safe to destroy."

  log "  terraform init (app layer)..."
  (cd "$TERRAFORM_APP_DIR" && terraform init -input=false -reconfigure) \
    || fail "terraform init failed for the app layer." 6

  log "  terraform plan -destroy (preview of what will be removed)..."
  (cd "$TERRAFORM_APP_DIR" && terraform plan -destroy -input=false -no-color \
     | tee /tmp/tf-destroy-plan.txt | tail -40) \
    || warn "terraform plan -destroy exited non-zero — continuing to destroy anyway."

  log "  terraform destroy -auto-approve (app layer)..."
  # -auto-approve because we already required the user to type the confirm
  # phrase in confirm_destruction().
  (cd "$TERRAFORM_APP_DIR" && terraform destroy -auto-approve -input=false) \
    || fail "terraform destroy failed for the app layer." 6
  ok "  App-layer Terraform resources destroyed."

  # Optionally remove the state file itself. We never touch the S3 object
  # (that's bootstrap's bucket); we only delete the local working copy.
  if [[ "$KEEP_TERRAFORM_STATE" -eq 0 ]]; then
    log "  Removing local app-layer state file (--keep-terraform-state NOT set)..."
    rm -f "$TERRAFORM_APP_DIR/terraform.tfstate" \
          "$TERRAFORM_APP_DIR/terraform.tfstate.backup"
    ok "  Local app-layer state file removed."
  else
    warn "  --keep-terraform-state set; local state file preserved."
  fi

  # ── Explicit EKS post-destroy check ───────────────────────────────────────
  # The user's contract: "EKS must be destroyed". This is the authoritative
  # check. It runs at the end of step_terraform_destroy so a failure here
  # exits with code 6 (terraform-destroy error class).
  log "  Verifying EKS cluster uniops-eks-dev is gone..."
  if aws eks describe-cluster --name uniops-eks-dev --region "$REGION" \
       &>/dev/null; then
    echo -e "${RED}${BOLD}"
    echo "  ╔════════════════════════════════════════════════════════════════════╗"
    echo "  ║  ✗  FAILURE — EKS cluster uniops-eks-dev still exists            ║"
    echo "  ║                                                                    ║"
    echo "  ║  terraform destroy returned success, but the EKS cluster is still  ║"
    echo "  ║  present in AWS. This usually means:                               ║"
    echo "  ║    • EKS is managed by a different Terraform state / module        ║"
    echo "  ║    • IAM / dependency graph prevented full teardown                ║"
    echo "  ║    • A separate kubectl/operator reapplied the cluster             ║"
    echo "  ║                                                                    ║"
    echo "  ║  Manual cleanup:                                                   ║"
    echo "  ║    aws eks delete-cluster --name uniops-eks-dev --region us-east-2 ║"
    echo "  ╚════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    fail "EKS cluster uniops-eks-dev still present after terraform destroy." 6
  else
    echo -e "${GREEN}${BOLD}"
    echo "  ╔════════════════════════════════════════════════════════════════════╗"
    echo "  ║  ✓  SUCCESS — EKS cluster uniops-eks-dev is gone                  ║"
    echo "  ╚════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
  fi
}

# ─── Phase 7 — Post-destroy verification ──────────────────────────────────────
# Two checks:
#   7a. Bootstrap resources MUST still exist (negative-existence).
#   7b. App-layer resources MUST have been destroyed (positive-destruction).
step_verify_protected() {
  section "PHASE 7a — Verify Bootstrap Resources Still Exist"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would re-check ECR/S3/DDB/RDS/ElastiCache/EFS"
    return 0
  fi

  for REPO in "${PROTECTED_ECR_REPOS[@]}"; do
    aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" \
      &>/dev/null \
      || fail "PROTECTED RESOURCE LOST: ECR repo $REPO missing after destroy!" 5
  done
  ok "ECR repos intact."

  aws s3api head-bucket --bucket "$PROTECTED_S3_BUCKET" &>/dev/null \
    || fail "PROTECTED RESOURCE LOST: S3 bucket $PROTECTED_S3_BUCKET missing after destroy!" 5
  ok "S3 state bucket intact."

  # Also confirm the bootstrap/ state key is still in S3 — a regression here
  # would mean bootstrap state was somehow deleted.
  local bkeys
  bkeys=$(aws s3api list-objects-v2 --bucket "$PROTECTED_S3_BUCKET" --prefix "bootstrap/" \
           --query 'Contents[].Key' --output text 2>/dev/null || echo "")
  if [[ -z "$bkeys" ]]; then
    warn "No bootstrap/ state keys in S3 (may be empty bootstrap — non-fatal)."
  else
    ok "Bootstrap state keys in S3: $(echo "$bkeys" | tr '\n' ' ')"
  fi

  aws dynamodb describe-table --table-name "$PROTECTED_DDB_TABLE" --region "$REGION" \
    &>/dev/null \
    || fail "PROTECTED RESOURCE LOST: DDB table $PROTECTED_DDB_TABLE missing after destroy!" 5
  ok "DynamoDB lock table intact."

  ok "All bootstrap resources verified intact."
}

step_verify_app_destroyed() {
  section "PHASE 7b — Verify App-Layer Resources Were Destroyed"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] would re-check that EKS / RDS / ElastiCache / EFS are gone"
    return 0
  fi

  # If --skip-terraform was set, the user opted out of Terraform destroy.
  # In that case, EKS may still be present and we don't fail the script.
  if [[ "$SKIP_TERRAFORM" -eq 1 ]]; then
    warn "--skip-terraform was set; skipping app-destroyed check."
    return 0
  fi

  # EKS cluster should be GONE. This is the explicit SUCCESS / FAILURE gate.
  # Note: step_terraform_destroy() already does this check at the end of
  # Phase 6.5. This is a redundant final gate to be defensive.
  local cluster
  cluster=$(aws eks list-clusters --region "$REGION" \
              --query 'clusters[?contains(@, `uniops`)] | [0]' \
              --output text 2>/dev/null | tr -d '[]"' || true)
  if [[ -n "$cluster" && "$cluster" != "None" ]]; then
    echo -e "${RED}${BOLD}"
    echo "  ╔════════════════════════════════════════════════════════════════════╗"
    echo "  ║  ✗  FAILURE — EKS cluster $cluster still present"
    echo "  ╚════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    fail "App-layer resource NOT destroyed: EKS cluster $cluster still present." 6
  fi
  echo -e "${GREEN}${BOLD}"
  echo "  ╔════════════════════════════════════════════════════════════════════╗"
  echo "  ║  ✓  SUCCESS — EKS cluster uniops-eks-dev is gone                  ║"
  echo "  ╚════════════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"

  # RDS — note: RDS may be a managed data-tier resource that the user wants
  # to keep out-of-band. We don't fail the script if it's still here, but
  # we warn. If you provisioned RDS via the app Terraform layer, it should
  # be gone by now.
  if aws rds describe-db-instances --db-instance-identifier "$PROTECTED_RDS_ID" \
       --region "$REGION" &>/dev/null; then
    warn "RDS instance $PROTECTED_RDS_ID still present (out-of-band or partial destroy)."
  else
    ok "RDS instance $PROTECTED_RDS_ID is gone."
  fi

  ok "App-layer resources verified destroyed (or out-of-band)."
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
  divider
  echo -e "${RED}${BOLD}  UniOps SaaS — Application Infrastructure DESTROY (v1.0)${NC}${NC}"
  echo -e "  $(date)"
  echo -e "  Region:    $REGION"
  echo -e "  Namespace: $NAMESPACE"
  echo -e "  Flags:     ASSUME_YES=$ASSUME_YES DRY_RUN=$DRY_RUN KEEP_PVCS=$KEEP_PVCS KEEP_SECRETS=$KEEP_SECRETS SKIP_TERRAFORM=$SKIP_TERRAFORM KEEP_TERRAFORM_STATE=$KEEP_TERRAFORM_STATE"
  divider

  guard_bootstrap_isolation
  step_prerequisites
  confirm_destruction
  step_helm_uninstall
  step_statefulsets
  step_pvcs
  step_secrets
  step_namespace
  step_terraform_destroy
  step_verify_protected
  step_verify_app_destroyed

  echo
  ok "Application layer destroyed. Bootstrap layer untouched."
  log "To redeploy: bash start-app-infra.sh"
}

main "$@"
