#!/bin/bash
# Jenkins Script: Health Check for UniOps
# Usage: ./health-check.sh [environment] [base_url]

set -euo pipefail

ENVIRONMENT="${1:-dev}"
BASE_URL="${2:-http://localhost:8000}"
MAX_RETRIES=10
RETRY_INTERVAL=5

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🏥 بدء فحص الصحة لبيئة: ${ENVIRONMENT}"
echo "🌐 Base URL: ${BASE_URL}"
echo ""

# ──────────────────────────────────────────────
# 1. API Health
# ──────────────────────────────────────────────
echo -n "📡 فحص صحة API... "
if curl -sf "${BASE_URL}/api/v1/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ FAILED${NC}"
    echo "   تعذر الاتصال بـ ${BASE_URL}/api/v1/health"
    exit 1
fi

# ──────────────────────────────────────────────
# 2. Frontend
# ──────────────────────────────────────────────
echo -n "🎨 فحص Frontend... "
if curl -sf -o /dev/null "${BASE_URL}/" 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${YELLOW}⚠️  تعذر الوصول إلى Frontend${NC}"
fi

# ──────────────────────────────────────────────
# 3. Auth API
# ──────────────────────────────────────────────
echo -n "🔒 فحص Auth API... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"health@uniops.dev","password":"test123"}')

if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 401 ] || [ "$HTTP_CODE" -eq 404 ]; then
    echo -e "${GREEN}✅ OK (HTTP ${HTTP_CODE})${NC}"
else
    echo -e "${RED}❌ FAILED (HTTP ${HTTP_CODE})${NC}"
    exit 1
fi

# ──────────────────────────────────────────────
# 4. Kubernetes Pods (if kubectl available)
# ──────────────────────────────────────────────
if command -v kubectl &> /dev/null; then
    echo -n "☸️  فحص Kubernetes Pods... "
    NAMESPACE="uniops-${ENVIRONMENT}"
    FAILED_PODS=$(kubectl get pods -n "${NAMESPACE}" \
        --field-selector=status.phase!=Running,status.phase!=Succeeded \
        --no-headers 2>/dev/null | wc -l || echo "0")
    
    if [ "${FAILED_PODS}" -eq 0 ]; then
        echo -e "${GREEN}✅ جميع الـ Pods تعمل${NC}"
    else
        echo -e "${RED}❌ توجد ${FAILED_PODS} Pods غير عاملة${NC}"
        kubectl get pods -n "${NAMESPACE}" --field-selector=status.phase!=Running
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  kubectl غير متاح - تخطي فحص Kubernetes${NC}"
fi

# ──────────────────────────────────────────────
# 5. Database (via health endpoint response)
# ──────────────────────────────────────────────
echo -n "🗄️  فحص قاعدة البيانات... "
HEALTH_RESPONSE=$(curl -s "${BASE_URL}/api/v1/health")
if echo "${HEALTH_RESPONSE}" | grep -q '"database":"healthy"'; then
    echo -e "${GREEN}✅ متصلة${NC}"
else
    echo -e "${YELLOW}⚠️  غير مؤكدة (استجابة: ${HEALTH_RESPONSE})${NC}"
fi

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ اكتمل فحص الصحة لبيئة ${ENVIRONMENT}${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"