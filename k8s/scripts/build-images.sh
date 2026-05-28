#!/usr/bin/env bash
################################################################################
# build-images.sh — Build and push all UniOps Docker images
#
# Usage:
#   # Dev build (local registry, :dev tags)
#   bash k8s/scripts/build-images.sh
#
#   # Prod release
#   REGISTRY=ghcr.io/your-org TAG=1.2.0 bash k8s/scripts/build-images.sh
#
#   # Skip push (local build only)
#   PUSH=false bash k8s/scripts/build-images.sh
#
# Environment variables:
#   REGISTRY   Container registry prefix  (default: ghcr.io/your-org)
#   TAG        Image tag                  (default: dev)
#   PUSH       Push after build           (default: true)
#   PLATFORM   Target platform            (default: linux/amd64)
#   NO_CACHE   Disable build cache        (default: false)
################################################################################
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
REGISTRY="${REGISTRY:-ghcr.io/your-org}"
TAG="${TAG:-dev}"
PUSH="${PUSH:-true}"
PLATFORM="${PLATFORM:-linux/amd64}"
NO_CACHE="${NO_CACHE:-false}"

# Script must run from project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()   { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
ok()    { echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC} $*"; }
error() { echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*" >&2; exit 1; }

# ── Verify prerequisites ──────────────────────────────────────────────────────
for cmd in docker; do
  command -v "$cmd" >/dev/null 2>&1 || error "$cmd is not installed"
done

if [[ "$PUSH" == "true" ]]; then
  # Verify docker is logged in to the registry
  REGISTRY_HOST="${REGISTRY%%/*}"
  if ! docker info 2>/dev/null | grep -q "Username"; then
    warn "Not logged in to Docker. Attempting registry check..."
    docker pull "${REGISTRY_HOST}/nonexistent" 2>/dev/null || true
  fi
fi

# ── Build arguments ───────────────────────────────────────────────────────────
BUILD_ARGS=("--platform" "$PLATFORM")
[[ "$NO_CACHE" == "true" ]] && BUILD_ARGS+=("--no-cache")
[[ "$PUSH" == "true" ]] && BUILD_ARGS+=("--push") || BUILD_ARGS+=("--load")

echo ""
echo "══════════════════════════════════════════════════════"
echo "  UniOps Docker Build"
echo "  Registry : $REGISTRY"
echo "  Tag      : $TAG"
echo "  Platform : $PLATFORM"
echo "  Push     : $PUSH"
echo "  No-cache : $NO_CACHE"
echo "══════════════════════════════════════════════════════"
echo ""

# ── Helper: build single image ────────────────────────────────────────────────
build_image() {
  local name="$1"
  local context="$2"
  local dockerfile="$3"
  local full_tag="${REGISTRY}/${name}:${TAG}"

  log "Building ${name}:${TAG} ..."
  log "  Context:    $context"
  log "  Dockerfile: $dockerfile"

  docker buildx build \
    "${BUILD_ARGS[@]}" \
    --file "$dockerfile" \
    --tag "$full_tag" \
    --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --label "org.opencontainers.image.revision=$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
    --label "org.opencontainers.image.version=$TAG" \
    --label "org.opencontainers.image.title=$name" \
    "$context"

  ok "Built: $full_tag"
}

# ── Image 1: Backend (FastAPI + Celery — same image, different CMD) ───────────
# Used by: migration Job, backend Deployment, celery-worker, celery-beat
build_image \
  "uniops-backend" \
  "backend" \
  "backend/Dockerfile"

# ── Image 2: Frontend (React → nginx) ─────────────────────────────────────────
# Build context MUST be project root (Dockerfile copies from lib/ and artifacts/)
build_image \
  "uniops-frontend" \
  "." \
  "artifacts/uniops/Dockerfile"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
ok "All images built successfully!"
echo ""
echo "  ${REGISTRY}/uniops-backend:${TAG}"
echo "  ${REGISTRY}/uniops-frontend:${TAG}"
echo ""
if [[ "$TAG" != "dev" && "$PUSH" == "true" ]]; then
  echo "  To deploy:"
  echo "  TAG=$TAG kubectl apply -k k8s/overlays/prod"
fi
echo "══════════════════════════════════════════════════════"
