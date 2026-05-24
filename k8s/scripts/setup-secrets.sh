#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup-secrets.sh — generate and apply Kubernetes secrets for UniOps
#
# Usage:
#   bash k8s/scripts/setup-secrets.sh dev     # creates secret in uniops-dev
#   bash k8s/scripts/setup-secrets.sh prod    # creates secret in uniops (prod)
#
# Requirements: kubectl configured and pointing at your cluster
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ENV="${1:-dev}"

if [[ "$ENV" == "dev" ]]; then
  NAMESPACE="uniops-dev"
  PG_PASSWORD="uniops_dev_password"
else
  NAMESPACE="uniops"
  # Prod: generate a strong random password
  PG_PASSWORD="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 32)"
fi

SECRET_KEY="$(openssl rand -hex 32)"
JWT_SECRET_KEY="$(openssl rand -hex 32)"

echo "Creating namespace ${NAMESPACE} (if missing)..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo "Creating/replacing secret uniops-secrets in ${NAMESPACE}..."
kubectl -n "${NAMESPACE}" create secret generic uniops-secrets \
  --from-literal=SECRET_KEY="${SECRET_KEY}" \
  --from-literal=JWT_SECRET_KEY="${JWT_SECRET_KEY}" \
  --from-literal=POSTGRES_USER="uniops" \
  --from-literal=POSTGRES_PASSWORD="${PG_PASSWORD}" \
  --from-literal=POSTGRES_DB="uniops_db" \
  --from-literal=AWS_ACCESS_KEY_ID="" \
  --from-literal=AWS_SECRET_ACCESS_KEY="" \
  --from-literal=GITHUB_TOKEN="" \
  --from-literal=GITHUB_WEBHOOK_SECRET="" \
  --from-literal=GITLAB_TOKEN="" \
  --from-literal=STRIPE_SECRET_KEY="" \
  --from-literal=STRIPE_WEBHOOK_SECRET="" \
  --from-literal=SLACK_BOT_TOKEN="" \
  --from-literal=SLACK_WEBHOOK_URL="" \
  --from-literal=SENDGRID_API_KEY="" \
  --from-literal=EMAIL_FROM="noreply@uniops.io" \
  --from-literal=SENTRY_DSN="" \
  --save-config \
  --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "Done! Secret created in namespace: ${NAMESPACE}"
if [[ "$ENV" != "dev" ]]; then
  echo ""
  echo "  POSTGRES_PASSWORD: ${PG_PASSWORD}"
  echo "  (save this somewhere safe)"
fi
echo ""
echo "Next steps:"
echo "  kubectl apply -k k8s/overlays/${ENV}"
