#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build-images.sh — build and push Docker images to your registry
#
# Usage:
#   REGISTRY=ghcr.io/your-org TAG=dev   bash k8s/scripts/build-images.sh
#   REGISTRY=ghcr.io/your-org TAG=1.0.0 bash k8s/scripts/build-images.sh
#
# Prerequisites:
#   docker login ghcr.io   (or your registry)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REGISTRY="${REGISTRY:-ghcr.io/your-org}"
TAG="${TAG:-dev}"

echo "Building and pushing images to ${REGISTRY} with tag :${TAG}"
echo ""

# ── Python FastAPI backend ────────────────────────────────────────────────────
echo "[1/3] Building uniops-backend..."
docker build \
  --platform linux/amd64 \
  -t "${REGISTRY}/uniops-backend:${TAG}" \
  -f backend/Dockerfile \
  backend/
docker push "${REGISTRY}/uniops-backend:${TAG}"

# ── Node.js Express API ───────────────────────────────────────────────────────
echo "[2/3] Building uniops-node-api..."
docker build \
  --platform linux/amd64 \
  -t "${REGISTRY}/uniops-node-api:${TAG}" \
  -f artifacts/server/Dockerfile \
  artifacts/server/
docker push "${REGISTRY}/uniops-node-api:${TAG}"

# ── React frontend (nginx) ────────────────────────────────────────────────────
echo "[3/3] Building uniops-frontend..."
docker build \
  --platform linux/amd64 \
  -t "${REGISTRY}/uniops-frontend:${TAG}" \
  -f artifacts/uniops/Dockerfile \
  artifacts/uniops/
docker push "${REGISTRY}/uniops-frontend:${TAG}"

echo ""
echo "All images pushed:"
echo "  ${REGISTRY}/uniops-backend:${TAG}"
echo "  ${REGISTRY}/uniops-node-api:${TAG}"
echo "  ${REGISTRY}/uniops-frontend:${TAG}"
