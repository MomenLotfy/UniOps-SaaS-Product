#!/bin/bash
set -e
SEVERITY=${1:-HIGH,CRITICAL}
echo "🔒 Trivy Scan (severity: $SEVERITY)"
trivy fs --severity "$SEVERITY" --exit-code 0 --format sarif -o trivy-fs.sarif ./
echo "✅ Trivy completed"