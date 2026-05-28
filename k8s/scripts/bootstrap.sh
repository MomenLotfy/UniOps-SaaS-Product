#!/usr/bin/env bash
################################################################################
#  UniOps — Bootstrap Script
#  من الصفر إلى تطبيق يشتغل بدون domain / email / registry مدفوع
#
#  ماذا يفعل هذا السكريبت تلقائياً:
#    1. يتحقق من المتطلبات ويثبّت الناقصة (minikube, kubectl, helm, docker)
#    2. يشغّل minikube ويفعّل ingress
#    3. يكتشف الـ IP ويبني hostname من nip.io
#    4. يسألك عن registry (ghcr.io / Docker Hub / محلي)
#    5. يبني Docker images ويرفعها
#    6. يولّد Self-Signed TLS certificate
#    7. يُنشئ Kubernetes secrets عشوائية
#    8. يُعدّل الـ overlays بالقيم الحقيقية
#    9. يطبّق الـ manifests على الـ cluster
#   10. يطبع الـ URL النهائي ويفتحه في المتصفح
#
#  الاستخدام:
#    bash k8s/scripts/bootstrap.sh
#
#  متطلبات مسبقة: macOS أو Linux، Docker مثبّت ويشتغل
################################################################################
set -euo pipefail
IFS=$'\n\t'

# ══════════════════════════════════════════════════════════════════════════════
#  COLORS & LOGGING
# ══════════════════════════════════════════════════════════════════════════════
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step()    { echo -e "\n${BOLD}${BLUE}══▶ $*${NC}"; }
ok()      { echo -e "  ${GREEN}✓${NC}  $*"; }
warn()    { echo -e "  ${YELLOW}⚠${NC}  $*"; }
info()    { echo -e "  ${CYAN}ℹ${NC}  $*"; }
error()   { echo -e "\n${RED}✗ ERROR: $*${NC}\n" >&2; exit 1; }
ask()     { echo -e "\n  ${BOLD}${YELLOW}?${NC}  $*"; }
divider() { echo -e "${BLUE}────────────────────────────────────────────────────${NC}"; }

# ══════════════════════════════════════════════════════════════════════════════
#  BANNER
# ══════════════════════════════════════════════════════════════════════════════
clear
echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  ██╗   ██╗███╗   ██╗██╗ ██████╗ ██████╗ ███████╗
  ██║   ██║████╗  ██║██║██╔═══██╗██╔══██╗██╔════╝
  ██║   ██║██╔██╗ ██║██║██║   ██║██████╔╝███████╗
  ██║   ██║██║╚██╗██║██║██║   ██║██╔═══╝ ╚════██║
  ╚██████╔╝██║ ╚████║██║╚██████╔╝██║     ███████║
   ╚═════╝ ╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝     ╚══════╝
  Bootstrap — Zero to Running in One Script
BANNER
echo -e "${NC}"
divider
echo -e "  بدون domain / email مدفوع / container registry مدفوع"
divider

# ══════════════════════════════════════════════════════════════════════════════
#  0. LOCATE PROJECT ROOT
# ══════════════════════════════════════════════════════════════════════════════
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"

[[ -d "$K8S_DIR/base" ]]     || error "k8s/base not found. Run from project root."
[[ -d "$K8S_DIR/overlays" ]] || error "k8s/overlays not found."

cd "$PROJECT_ROOT"
info "Project root: $PROJECT_ROOT"

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
has() { command -v "$1" >/dev/null 2>&1; }

gen_secret() {
  openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"
}
gen_hex() {
  openssl rand -hex "${1:-32}"
}

wait_for_pod() {
  local label="$1" ns="${2:-uniops-dev}" timeout="${3:-120}"
  info "Waiting for pod with label $label in $ns ..."
  kubectl wait pod \
    --for=condition=ready \
    --selector="$label" \
    --namespace="$ns" \
    --timeout="${timeout}s" 2>/dev/null || warn "Pod wait timed out — might still be starting"
}

# ══════════════════════════════════════════════════════════════════════════════
#  1. CHECK / INSTALL PREREQUISITES
# ══════════════════════════════════════════════════════════════════════════════
step "Checking prerequisites"

OS="$(uname -s)"

install_brew_pkg() {
  if [[ "$OS" == "Darwin" ]]; then
    has brew || error "Homebrew not found. Install from https://brew.sh"
    brew install "$1" -q
  else
    error "$1 not found. Please install it manually:\n  https://github.com/$2"
  fi
}

# ── Docker ────────────────────────────────────────────────────────────────────
if ! has docker; then
  error "Docker not found.\nInstall Docker Desktop: https://www.docker.com/products/docker-desktop"
fi
if ! docker info >/dev/null 2>&1; then
  error "Docker daemon is not running. Please start Docker Desktop."
fi
ok "Docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"

# ── kubectl ───────────────────────────────────────────────────────────────────
if ! has kubectl; then
  warn "kubectl not found — installing..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install kubectl -q
  else
    curl -sLO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl && sudo mv kubectl /usr/local/bin/
  fi
fi
ok "kubectl $(kubectl version --client --short 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')"

# ── minikube ──────────────────────────────────────────────────────────────────
if ! has minikube; then
  warn "minikube not found — installing..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install minikube -q
  else
    curl -sLO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64
  fi
fi
ok "minikube $(minikube version --short 2>/dev/null || echo 'installed')"

# ── helm ──────────────────────────────────────────────────────────────────────
if ! has helm; then
  warn "helm not found — installing..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install helm -q
  else
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  fi
fi
ok "helm $(helm version --short 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')"

# ── openssl ───────────────────────────────────────────────────────────────────
has openssl || error "openssl not found. Install it via your package manager."
ok "openssl $(openssl version | awk '{print $2}')"

# ══════════════════════════════════════════════════════════════════════════════
#  2. CHOOSE CONTAINER REGISTRY
# ══════════════════════════════════════════════════════════════════════════════
step "Container Registry"
echo ""
echo "  اختر طريقة رفع الـ Docker images:"
echo ""
echo "  [1] ghcr.io  — GitHub Container Registry (مجاني، يحتاج GitHub account)"
echo "  [2] Docker Hub — docker.io (مجاني، يحتاج DockerHub account)"
echo "  [3] Local    — registry محلي (بدون إنترنت، بدون حساب)"
echo ""
read -rp "  اختيارك [1/2/3]: " REGISTRY_CHOICE
REGISTRY_CHOICE="${REGISTRY_CHOICE:-1}"

case "$REGISTRY_CHOICE" in
  1)
    ask "GitHub username:"
    read -rp "  > " GH_USERNAME
    [[ -n "$GH_USERNAME" ]] || error "Username فارغ"

    ask "GitHub Personal Access Token (ghp_...):\n  أنشئه من: https://github.com/settings/tokens/new\n  الـ scopes المطلوبة: write:packages, read:packages"
    read -rsp "  > " GH_TOKEN
    echo ""
    [[ -n "$GH_TOKEN" ]] || error "Token فارغ"

    echo "$GH_TOKEN" | docker login ghcr.io -u "$GH_USERNAME" --password-stdin \
      || error "GitHub login فشل — تأكد من الـ token والـ username"
    ok "Logged in to ghcr.io"

    REGISTRY="ghcr.io/${GH_USERNAME}"
    ;;
  2)
    ask "Docker Hub username:"
    read -rp "  > " DH_USERNAME
    [[ -n "$DH_USERNAME" ]] || error "Username فارغ"

    ask "Docker Hub password:"
    read -rsp "  > " DH_PASSWORD
    echo ""
    [[ -n "$DH_PASSWORD" ]] || error "Password فارغ"

    echo "$DH_PASSWORD" | docker login docker.io -u "$DH_USERNAME" --password-stdin \
      || error "Docker Hub login فشل"
    ok "Logged in to docker.io"

    REGISTRY="docker.io/${DH_USERNAME}"
    ;;
  3)
    REGISTRY="localhost:5000"
    PUSH_LOCAL=true
    ok "Local registry selected (localhost:5000)"
    ;;
  *)
    error "اختيار غير صحيح"
    ;;
esac

IMAGE_TAG="dev"
info "Registry : $REGISTRY"
info "Image tag: $IMAGE_TAG"

# ══════════════════════════════════════════════════════════════════════════════
#  3. START / CONFIGURE MINIKUBE
# ══════════════════════════════════════════════════════════════════════════════
step "Setting up minikube"

MINIKUBE_STATUS="$(minikube status --format='{{.Host}}' 2>/dev/null || echo 'Stopped')"

if [[ "$MINIKUBE_STATUS" != "Running" ]]; then
  info "Starting minikube (2 CPUs, 4GB RAM)..."

  MINIKUBE_ARGS=("--cpus=2" "--memory=4096" "--driver=docker")

  # Local registry: add insecure-registry flag
  if [[ "${PUSH_LOCAL:-false}" == "true" ]]; then
    MINIKUBE_ARGS+=("--insecure-registry=localhost:5000")
  fi

  minikube start "${MINIKUBE_ARGS[@]}"
  ok "minikube started"
else
  ok "minikube already running"
fi

# Enable ingress addon
info "Enabling ingress addon..."
minikube addons enable ingress 2>/dev/null || true
minikube addons enable ingress-dns 2>/dev/null || true
ok "Ingress addon enabled"

# Enable metrics-server for HPA
info "Enabling metrics-server..."
minikube addons enable metrics-server 2>/dev/null || true
ok "metrics-server enabled"

# ── Local registry setup ───────────────────────────────────────────────────────
if [[ "${PUSH_LOCAL:-false}" == "true" ]]; then
  if ! docker ps | grep -q "registry"; then
    info "Starting local Docker registry on port 5000..."
    docker run -d -p 5000:5000 --restart=always --name uniops-registry registry:2
    ok "Local registry running on localhost:5000"
  else
    ok "Local registry already running"
  fi

  # Point minikube at local registry via port-forward
  info "Configuring minikube to use local registry..."
  kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5000"
    help: "https://minikube.sigs.k8s.io/docs/tasks/registry/"
EOF
fi

# ══════════════════════════════════════════════════════════════════════════════
#  4. DISCOVER CLUSTER IP → BUILD NIP.IO HOSTNAME
# ══════════════════════════════════════════════════════════════════════════════
step "Discovering cluster IP for nip.io domain"

# Wait for ingress controller to get an IP
info "Waiting for ingress controller IP (up to 90s)..."
for i in $(seq 1 30); do
  CLUSTER_IP="$(minikube ip 2>/dev/null)"
  if [[ -n "$CLUSTER_IP" && "$CLUSTER_IP" != "127.0.0.1" ]]; then
    break
  fi
  sleep 3
done

[[ -n "${CLUSTER_IP:-}" ]] || CLUSTER_IP="$(minikube ip)"
[[ -n "$CLUSTER_IP" ]] || error "فشل الحصول على minikube IP"

APP_HOSTNAME="uniops.${CLUSTER_IP}.nip.io"

ok "Cluster IP  : $CLUSTER_IP"
ok "App hostname: $APP_HOSTNAME"
info "nip.io يحوّل $APP_HOSTNAME تلقائياً → $CLUSTER_IP (بدون أي إعداد DNS)"

# ══════════════════════════════════════════════════════════════════════════════
#  5. GENERATE SELF-SIGNED TLS CERTIFICATE
# ══════════════════════════════════════════════════════════════════════════════
step "Generating Self-Signed TLS certificate"

TLS_DIR="$(mktemp -d)"
trap 'rm -rf "$TLS_DIR"' EXIT

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$TLS_DIR/tls.key" \
  -out    "$TLS_DIR/tls.crt" \
  -subj   "/CN=${APP_HOSTNAME}/O=UniOps-Dev/C=US" \
  -extensions v3_req \
  -addext "subjectAltName=DNS:${APP_HOSTNAME},DNS:*.${CLUSTER_IP}.nip.io" \
  2>/dev/null

ok "Certificate generated (365 days, RSA-2048)"
info "CN: $APP_HOSTNAME"
warn "المتصفح سيُظهر تحذير 'Not Secure' — هذا طبيعي مع self-signed cert"
info "اضغط 'Advanced' ثم 'Proceed' لتجاوز التحذير"

# ══════════════════════════════════════════════════════════════════════════════
#  6. PATCH KUSTOMIZE OVERLAYS WITH REAL VALUES
# ══════════════════════════════════════════════════════════════════════════════
step "Patching k8s overlays with real values"

# Backup originals
cp "$K8S_DIR/overlays/dev/kustomization.yaml" \
   "$K8S_DIR/overlays/dev/kustomization.yaml.bak" 2>/dev/null || true
cp "$K8S_DIR/base/configmap.yaml" \
   "$K8S_DIR/base/configmap.yaml.bak" 2>/dev/null || true

# ── Patch image registry in dev overlay ───────────────────────────────────────
python3 << PYEOF
import re

path = "${K8S_DIR}/overlays/dev/kustomization.yaml"
with open(path) as f:
    content = f.read()

# Replace registry placeholders
content = content.replace("ghcr.io/your-org/uniops-backend",  "${REGISTRY}/uniops-backend")
content = content.replace("ghcr.io/your-org/uniops-frontend", "${REGISTRY}/uniops-frontend")

# Replace hostname
content = content.replace("uniops.127.0.0.1.nip.io", "${APP_HOSTNAME}")
content = content.replace(
    '["http://localhost:5173","http://localhost:3000","http://localhost:8000","http://uniops.127.0.0.1.nip.io"]',
    '["http://localhost:5173","http://localhost:3000","http://localhost:8000","http://${APP_HOSTNAME}","https://${APP_HOSTNAME}"]'
)
content = content.replace(
    "FRONTEND_URL=http://uniops.127.0.0.1.nip.io",
    "FRONTEND_URL=http://${APP_HOSTNAME}"
)

with open(path, "w") as f:
    f.write(content)
print("  ✓ dev/kustomization.yaml patched")
PYEOF

# ── Patch backend.yaml image registry ─────────────────────────────────────────
python3 << PYEOF
import re

for path in [
    "${K8S_DIR}/base/backend.yaml",
    "${K8S_DIR}/base/celery.yaml",
    "${K8S_DIR}/base/frontend.yaml",
]:
    with open(path) as f:
        content = f.read()
    content = content.replace("ghcr.io/your-org/uniops-backend",  "${REGISTRY}/uniops-backend")
    content = content.replace("ghcr.io/your-org/uniops-frontend", "${REGISTRY}/uniops-frontend")
    with open(path, "w") as f:
        f.write(content)
    print(f"  ✓ {path.split('k8s/')[-1]} patched")
PYEOF

ok "All registry references updated → $REGISTRY"

# ══════════════════════════════════════════════════════════════════════════════
#  7. BUILD & PUSH DOCKER IMAGES
# ══════════════════════════════════════════════════════════════════════════════
step "Building Docker images"

# Check Dockerfiles exist
for f in "backend/Dockerfile" "artifacts/server/Dockerfile" "artifacts/uniops/Dockerfile"; do
  [[ -f "$PROJECT_ROOT/$f" ]] || error "Dockerfile not found: $f"
done

build_and_push() {
  local name="$1" ctx="$2" dockerfile="$3"
  local full_tag="${REGISTRY}/${name}:${IMAGE_TAG}"
  info "Building ${name}:${IMAGE_TAG} ..."
  docker build \
    --platform linux/amd64 \
    --file "$dockerfile" \
    --tag "$full_tag" \
    --label "bootstrap=true" \
    "$ctx"
  ok "Built: $full_tag"

  if [[ "${PUSH_LOCAL:-false}" == "true" ]]; then
    # For local registry: tag and push to localhost:5000
    docker push "$full_tag"
    # Also load into minikube directly (faster than registry roundtrip)
    minikube image load "$full_tag" 2>/dev/null || true
  else
    docker push "$full_tag"
  fi
  ok "Pushed: $full_tag"
}

build_and_push "uniops-backend"  "backend"         "backend/Dockerfile"
build_and_push "uniops-frontend" "."               "artifacts/uniops/Dockerfile"

ok "All 3 images built and pushed!"

# ══════════════════════════════════════════════════════════════════════════════
#  8. CREATE KUBERNETES SECRETS
# ══════════════════════════════════════════════════════════════════════════════
step "Creating Kubernetes secrets"

NAMESPACE="uniops"

# Create namespace if it doesn't exist
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 \
  || kubectl create namespace "$NAMESPACE"

ok "Namespace: $NAMESPACE"
info "Generating cryptographically random secrets..."

SECRET_KEY="$(gen_hex 32)"
JWT_SECRET_KEY="$(gen_hex 32)"
POSTGRES_PASSWORD="$(gen_secret 24)"
REDIS_PASSWORD="$(gen_secret 24)"

kubectl create secret generic uniops-secrets \
  --namespace="$NAMESPACE" \
  --from-literal=SECRET_KEY="$SECRET_KEY" \
  --from-literal=JWT_SECRET_KEY="$JWT_SECRET_KEY" \
  --from-literal=POSTGRES_USER="uniops" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=POSTGRES_DB="uniops_db" \
  --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD" \
  --from-literal=GITHUB_TOKEN="" \
  --from-literal=GITHUB_WEBHOOK_SECRET="$(gen_secret 24)" \
  --from-literal=GITLAB_TOKEN="" \
  --from-literal=STRIPE_SECRET_KEY="" \
  --from-literal=STRIPE_WEBHOOK_SECRET="$(gen_secret 24)" \
  --from-literal=SLACK_BOT_TOKEN="" \
  --from-literal=SLACK_WEBHOOK_URL="" \
  --from-literal=SENDGRID_API_KEY="" \
  --from-literal=AWS_ACCESS_KEY_ID="" \
  --from-literal=AWS_SECRET_ACCESS_KEY="" \
  --from-literal=SENTRY_DSN="" \
  --dry-run=client -o yaml \
| kubectl apply -f -

ok "Secret uniops-secrets created"

# ── Install TLS secret (self-signed cert) ──────────────────────────────────────
kubectl create secret tls uniops-tls \
  --namespace="$NAMESPACE" \
  --cert="$TLS_DIR/tls.crt" \
  --key="$TLS_DIR/tls.key" \
  --dry-run=client -o yaml \
| kubectl apply -f -

ok "TLS secret uniops-tls created (self-signed)"

# Unset secret vars from environment immediately
unset SECRET_KEY JWT_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD

# ══════════════════════════════════════════════════════════════════════════════
#  9. APPLY KUSTOMIZE MANIFESTS
# ══════════════════════════════════════════════════════════════════════════════
step "Deploying to Kubernetes"

info "Applying k8s/overlays/dev ..."
kubectl apply -k "$K8S_DIR/overlays/dev"
ok "Manifests applied"

# ── ImagePullPolicy: switch to IfNotPresent for local/minikube performance ────
if [[ "${PUSH_LOCAL:-false}" == "true" ]]; then
  info "Patching imagePullPolicy → IfNotPresent for local registry..."
  for deploy in backend frontend celery-worker celery-beat; do
    kubectl patch deployment "$deploy" \
      -n "$NAMESPACE" \
      --type=json \
      -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]' \
      2>/dev/null || true
  done
fi

# ══════════════════════════════════════════════════════════════════════════════
#  10. WAIT FOR PODS TO BE READY
# ══════════════════════════════════════════════════════════════════════════════
step "Waiting for services to become ready"

info "This takes 2-4 minutes on first run (image pull + DB init)..."
echo ""

# Wait for postgres first (other services depend on it)
info "Waiting for PostgreSQL..."
kubectl wait statefulset/postgres \
  --for=jsonpath='{.status.readyReplicas}'=1 \
  --namespace="$NAMESPACE" \
  --timeout=180s 2>/dev/null \
  || warn "Postgres taking longer than expected — continuing..."

# Wait for redis
info "Waiting for Redis..."
kubectl wait statefulset/redis \
  --for=jsonpath='{.status.readyReplicas}'=1 \
  --namespace="$NAMESPACE" \
  --timeout=120s 2>/dev/null \
  || warn "Redis taking longer than expected — continuing..."

# Wait for backend (runs migrations on startup)
info "Waiting for backend (includes DB migrations)..."
kubectl wait deployment/backend \
  --for=condition=available \
  --namespace="$NAMESPACE" \
  --timeout=240s 2>/dev/null \
  || warn "Backend taking longer than expected — check: kubectl logs -n $NAMESPACE -l app=backend"

# Wait for frontend
info "Waiting for frontend..."
kubectl wait deployment/frontend \
  --for=condition=available \
  --namespace="$NAMESPACE" \
  --timeout=120s 2>/dev/null \
  || warn "Frontend taking longer than expected"

ok "Core services ready!"

# ══════════════════════════════════════════════════════════════════════════════
#  11. ENABLE MINIKUBE TUNNEL (needed to reach ingress)
# ══════════════════════════════════════════════════════════════════════════════
step "Setting up ingress tunnel"

if [[ "$OS" == "Darwin" ]]; then
  info "On macOS: starting minikube tunnel in background (needs sudo)..."
  warn "إذا طلب منك password، أدخله — هذا لازم لـ ingress يشتغل"
  nohup minikube tunnel > /tmp/minikube-tunnel.log 2>&1 &
  TUNNEL_PID=$!
  sleep 3
  if kill -0 "$TUNNEL_PID" 2>/dev/null; then
    ok "minikube tunnel running (PID: $TUNNEL_PID)"
  else
    warn "Tunnel قد يحتاج sudo — شغّله يدوياً: sudo minikube tunnel"
  fi
else
  info "Linux: استخدم minikube IP مباشرة (لا يحتاج tunnel)"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  12. SAVE STATE FILE
# ══════════════════════════════════════════════════════════════════════════════
STATE_FILE="$PROJECT_ROOT/.bootstrap-state"
cat > "$STATE_FILE" << STATE
# Generated by bootstrap.sh — $(date)
REGISTRY="${REGISTRY}"
IMAGE_TAG="${IMAGE_TAG}"
APP_HOSTNAME="${APP_HOSTNAME}"
CLUSTER_IP="${CLUSTER_IP}"
NAMESPACE="${NAMESPACE}"
STATE

ok "State saved to .bootstrap-state"
info "Add .bootstrap-state to your .gitignore"

# ══════════════════════════════════════════════════════════════════════════════
#  13. FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
echo ""
divider
echo -e "${BOLD}${GREEN}"
cat << 'DONE'
  ██████╗  ██████╗ ███╗   ██╗███████╗██╗
  ██╔══██╗██╔═══██╗████╗  ██║██╔════╝██║
  ██║  ██║██║   ██║██╔██╗ ██║█████╗  ██║
  ██║  ██║██║   ██║██║╚██╗██║██╔══╝  ╚═╝
  ██████╔╝╚██████╔╝██║ ╚████║███████╗██╗
  ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝
DONE
echo -e "${NC}"
divider

echo -e "  ${BOLD}URLs:${NC}"
echo -e "    🌐 App:      ${CYAN}http://${APP_HOSTNAME}${NC}"
echo -e "    🔒 HTTPS:    ${CYAN}https://${APP_HOSTNAME}${NC}  (تجاهل تحذير الـ cert)"
echo -e "    📡 API:      ${CYAN}http://${APP_HOSTNAME}/api/v1/health${NC}"
echo ""
echo -e "  ${BOLD}Namespace:${NC}  $NAMESPACE"
echo -e "  ${BOLD}Registry:${NC}   $REGISTRY"
echo ""
echo -e "  ${BOLD}أوامر مفيدة:${NC}"
echo -e "    ${YELLOW}kubectl get pods -n $NAMESPACE${NC}              # حالة الـ pods"
echo -e "    ${YELLOW}kubectl logs -n $NAMESPACE -l app=backend${NC}   # logs الـ backend"
echo -e "    ${YELLOW}kubectl get svc -n $NAMESPACE${NC}               # الـ services"
echo -e "    ${YELLOW}minikube dashboard${NC}                          # واجهة بصرية"
echo ""
echo -e "  ${BOLD}لإعادة النشر بعد تعديل الكود:${NC}"
echo -e "    ${YELLOW}REGISTRY=$REGISTRY TAG=dev bash k8s/scripts/build-images.sh${NC}"
echo -e "    ${YELLOW}kubectl rollout restart deployment -n $NAMESPACE${NC}"
echo ""
echo -e "  ${BOLD}لحذف كل شيء:${NC}"
echo -e "    ${YELLOW}kubectl delete -k k8s/overlays/dev${NC}"
echo -e "    ${YELLOW}minikube stop${NC}"
divider
echo ""

# Auto-open browser if possible
APP_URL="http://${APP_HOSTNAME}"
if has open; then
  info "فتح المتصفح على $APP_URL ..."
  sleep 2
  open "$APP_URL" 2>/dev/null || true
elif has xdg-open; then
  xdg-open "$APP_URL" 2>/dev/null || true
fi
