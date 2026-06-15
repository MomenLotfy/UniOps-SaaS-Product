#!/bin/bash
set -e
echo "🕵️ Semgrep Secrets + SAST"
semgrep --config=auto --error --metrics=off
echo "✅ Semgrep completed"