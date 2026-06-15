#!/bin/bash
set -e
echo "🔍 SonarQube Analysis..."
sonar-scanner \
    -Dsonar.projectKey=${SONAR_PROJECT_KEY:-uniops} \
    -Dsonar.sources=./backend,./artifacts/uniops/src \
    -Dsonar.host.url=${SONAR_HOST_URL:-http://sonarqube:9000} \
    -Dsonar.login=${SONAR_TOKEN}
echo "✅ SonarQube completed"