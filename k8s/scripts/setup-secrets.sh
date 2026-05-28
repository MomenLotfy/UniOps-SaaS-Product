#!/usr/bin/env bash
################################################################################
# setup-secrets.sh — Create Kubernetes Secret for UniOps
#
# Generates strong random values for sensitive fields.
# NEVER prints secret values to stdout or logs.
# Uses --dry-run=client | kubectl apply (idempotent — safe to re-run).
#
# Usage:
#   bash k8s/scripts/setup-secrets.sh dev
#   bash k8s/scripts/setup-secrets.sh prod
#
# For prod: pass optional integrations as env vars before running:
#   export GITHUB_TOKEN="ghp_..."
#   export STRIPE_SECRET_KEY="sk_live_..."
#   export SENDGRID_API_KEY="SG...."
#   export SLACK_BOT_TOKEN="xoxb-..."
#   export AWS_ACCESS_KEY_ID="AKIA..."
#   export AWS_SECRET_ACCESS_KEY="..."
#   export SENTRY_DSN="https://...@sentry.io/..."
#   bash k8s/scripts/setup-secrets.sh prod
################################################################################
set -euo pipefail

# ── Argument ──────────────────────────────────────────────────────────────────
ENV="${1:-dev}"
if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 <dev|prod>" >&2
  exit 1
fi

# ── Namespace ─────────────────────────────────────────────────────────────────
NAMESPACE="uniops"
[[ "$ENV" == "dev" ]] && NAMESPACE="uniops-dev"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[setup-secrets]${NC} $*"; }
warn()  { echo -e "${YELLOW}[setup-secrets] ⚠${NC} $*"; }
error() { echo -e "${RED}[setup-secrets] ✗${NC} $*" >&2; exit 1; }

# ── Prerequisites ─────────────────────────────────────────────────────────────
command -v kubectl >/dev/null 2>&1 || error "kubectl not found"
command -v openssl >/dev/null 2>&1 || error "openssl not found"

log "Environment : $ENV"
log "Namespace   : $NAMESPACE"

# ── Ensure namespace exists ───────────────────────────────────────────────────
if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
  warn "Namespace $NAMESPACE does not exist. Creating..."
  kubectl create namespace "$NAMESPACE"
fi

# ── Generate secure random values ─────────────────────────────────────────────
gen_secret() {
  openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"
}
gen_hex() {
  openssl rand -hex "${1:-32}"
}

log "Generating cryptographically random secret values..."

# Fixed values for dev (predictable for local debugging)
# Randomly generated for prod (MUST be strong)
if [[ "$ENV" == "dev" ]]; then
  SECRET_KEY="dev-secret-key-uniops-2025-$(gen_secret 8)"
  JWT_SECRET_KEY="dev-jwt-key-uniops-2025-$(gen_secret 8)"
  POSTGRES_PASSWORD="uniops_dev_password"
  REDIS_PASSWORD="uniops_dev_redis"
else
  SECRET_KEY="$(gen_hex 32)"
  JWT_SECRET_KEY="$(gen_hex 32)"
  POSTGRES_PASSWORD="$(gen_secret 32)"
  REDIS_PASSWORD="$(gen_secret 32)"
fi

POSTGRES_USER="uniops"
POSTGRES_DB="uniops_db"

# Optional integrations — use env vars if set, else empty string
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_WEBHOOK_SECRET="${GITHUB_WEBHOOK_SECRET:-$(gen_secret 24)}"
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}"
STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-$(gen_secret 24)}"
SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
SENDGRID_API_KEY="${SENDGRID_API_KEY:-}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
SENTRY_DSN="${SENTRY_DSN:-}"

log "Applying Secret to namespace: $NAMESPACE ..."

# ── Create/update the Secret (idempotent) ─────────────────────────────────────
# --dry-run=client generates the YAML without applying it
# Piped to kubectl apply -f - applies or updates (never fails if already exists)
# IMPORTANT: No secret values are echoed or logged below
kubectl create secret generic uniops-secrets \
  --namespace="$NAMESPACE" \
  --from-literal=SECRET_KEY="$SECRET_KEY" \
  --from-literal=JWT_SECRET_KEY="$JWT_SECRET_KEY" \
  --from-literal=POSTGRES_USER="$POSTGRES_USER" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=POSTGRES_DB="$POSTGRES_DB" \
  --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD" \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --from-literal=GITHUB_WEBHOOK_SECRET="$GITHUB_WEBHOOK_SECRET" \
  --from-literal=GITLAB_TOKEN="$GITLAB_TOKEN" \
  --from-literal=STRIPE_SECRET_KEY="$STRIPE_SECRET_KEY" \
  --from-literal=STRIPE_WEBHOOK_SECRET="$STRIPE_WEBHOOK_SECRET" \
  --from-literal=SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN" \
  --from-literal=SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
  --from-literal=SENDGRID_API_KEY="$SENDGRID_API_KEY" \
  --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  --from-literal=SENTRY_DSN="$SENTRY_DSN" \
  --dry-run=client -o yaml \
| kubectl apply -f -

log "Secret 'uniops-secrets' created/updated in namespace '$NAMESPACE'"

# ── Prod: save credentials to a local encrypted file (NOT git) ────────────────
if [[ "$ENV" == "prod" ]]; then
  CREDS_FILE="./uniops-prod-credentials-$(date +%Y%m%d-%H%M%S).txt"
  # Write to temp file, then encrypt with openssl
  TEMP_FILE="$(mktemp)"
  # Only write the DB and Redis passwords (minimal needed for ops access)
  # Do NOT include API tokens — those come from .env files
  cat > "$TEMP_FILE" << CREDS
UniOps Production Credentials — $(date)
Generated by: $0

POSTGRES_USER:     $POSTGRES_USER
POSTGRES_DB:       $POSTGRES_DB
POSTGRES_PASSWORD: $POSTGRES_PASSWORD
REDIS_PASSWORD:    $REDIS_PASSWORD

KEEP THIS FILE SECURE. DELETE AFTER STORING IN YOUR PASSWORD MANAGER.
Store in: 1Password / Bitwarden / AWS Secrets Manager / HashiCorp Vault
NEVER commit to Git.
CREDS

  # Optional: encrypt with a passphrase
  if command -v gpg >/dev/null 2>&1; then
    warn "Saving encrypted credentials to: ${CREDS_FILE}.gpg"
    warn "You will be prompted for a GPG passphrase."
    gpg --symmetric --cipher-algo AES256 --output "${CREDS_FILE}.gpg" "$TEMP_FILE" 2>/dev/null \
      && warn "Saved: ${CREDS_FILE}.gpg  ← Store in password manager, then delete"
  else
    warn "GPG not found — credentials NOT saved to file."
    warn "Save the POSTGRES_PASSWORD and REDIS_PASSWORD to your password manager NOW."
    warn "They cannot be recovered from the cluster (stored as base64, not plaintext)."
  fi

  # Wipe temp file immediately
  rm -f "$TEMP_FILE"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Secrets applied successfully!${NC}"
echo ""
echo "  Namespace: $NAMESPACE"
echo "  Secret:    uniops-secrets"
echo ""
if [[ "$ENV" == "dev" ]]; then
  echo "  Next: kubectl apply -k k8s/overlays/dev"
else
  echo "  Next: kubectl apply -k k8s/overlays/prod"
  echo "        kubectl apply -k k8s/monitoring"
fi
echo -e "${GREEN}════════════════════════════════════════${NC}"

# Unset all secret variables from the shell environment
unset SECRET_KEY JWT_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD
unset GITHUB_TOKEN GITHUB_WEBHOOK_SECRET GITLAB_TOKEN
unset STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
unset SLACK_BOT_TOKEN SLACK_WEBHOOK_URL SENDGRID_API_KEY
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY SENTRY_DSN
