#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  UniOps Control Tower — Startup Script (FASTAPI VERSION)
# ─────────────────────────────────────────────────────────────

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

BACKEND_PORT=3001
FRONTEND_PORT=5173

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/artifacts/uniops"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$LOG_DIR"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      UniOps Control Tower                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Cleanup ────────────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down...${NC}"
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  echo -e "${GREEN}Stopped. Goodbye!${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── Node check (frontend only) ─────────────────────────────
echo -e "${BLUE}[1/4]${NC} Checking Node.js..."
if ! command -v node &>/dev/null; then
  echo -e "${RED}Node.js not found${NC}"
  exit 1
fi

echo -e "    Node.js $(node --version)"

# ── pnpm check ─────────────────────────────────────────────
if ! command -v pnpm &>/dev/null; then
  echo -e "${YELLOW}pnpm not found — installing...${NC}"
  npm install -g pnpm
fi

echo -e "    pnpm $(pnpm --version)"

# ── Backend setup (FastAPI) ────────────────────────────────
echo -e "${BLUE}[2/4]${NC} Installing backend dependencies..."

cd "$BACKEND_DIR"

if [ -f requirements.txt ]; then
  pip install -r requirements.txt >/dev/null 2>&1 || pip install -r requirements.txt
fi

echo -e "    Backend ready"

# ── Frontend setup ─────────────────────────────────────────
echo -e "${BLUE}[3/4]${NC} Installing frontend dependencies..."

cd "$ROOT_DIR"
pnpm install --frozen-lockfile 2>/dev/null || pnpm install

echo -e "    Frontend ready"

# ── Start Backend (FASTAPI) ────────────────────────────────
echo -e "${BLUE}[4/4]${NC} Starting services..."

cd "$BACKEND_DIR"

uvicorn app.main:app \
  --host 0.0.0.0 \
  --port $BACKEND_PORT \
  > "$LOG_DIR/backend.log" 2>&1 &

BACKEND_PID=$!

# ── Wait backend ───────────────────────────────────────────
for i in {1..20}; do
  if curl -sf "http://localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    echo -e "    Backend  →  http://localhost:$BACKEND_PORT"
    break
  fi
  sleep 1
done

# ── Start Frontend ─────────────────────────────────────────
cd "$ROOT_DIR"

PORT=$FRONTEND_PORT BASE_PATH=/ pnpm --filter @workspace/uniops run dev \
  > "$LOG_DIR/frontend.log" 2>&1 &

FRONTEND_PID=$!

# ── Wait frontend ──────────────────────────────────────────
for i in {1..30}; do
  if grep -q "Local:\|ready in" "$LOG_DIR/frontend.log" 2>/dev/null; then
    echo -e "    Frontend →  http://localhost:$FRONTEND_PORT"
    break
  fi
  sleep 1
done

# ── Done ───────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  UniOps is running 🚀                                  ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Dashboard → http://localhost:$FRONTEND_PORT            ║${NC}"
echo -e "${GREEN}║  API       → http://localhost:$BACKEND_PORT             ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  API Docs  → http://localhost:$BACKEND_PORT/docs        ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  Logs: ./logs/backend.log / frontend.log               ║${NC}"
echo -e "${GREEN}║  Ctrl+C to stop                                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

wait $BACKEND_PID $FRONTEND_PID