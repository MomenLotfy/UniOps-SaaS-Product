#!/bin/bash
set -e
BUILD_TAG=${1:-latest}
FRONTEND_IMAGE="uniops-frontend:${BUILD_TAG}"
BACKEND_IMAGE="uniops-backend:${BUILD_TAG}"

echo "🐳 Building Frontend"
docker build -t "$FRONTEND_IMAGE" -f artifacts/uniops/Dockerfile artifacts/uniops/

echo "🐳 Building Backend"
docker build -t "$BACKEND_IMAGE" -f backend/Dockerfile backend/

if [ "${PUSH_IMAGES}" == "true" ]; then
    docker push "$FRONTEND_IMAGE"
    docker push "$BACKEND_IMAGE"
    echo "✅ Images pushed"
else
    echo "✅ Images built (not pushed)"
fi