# UniOps — Local Setup Guide

Run UniOps Control Tower on any local machine (Windows / Linux / macOS).
No Replit account required.

---

## Option A — Docker Compose (recommended, full stack)

### Requirements
- **Docker Desktop** 4.x+ — https://www.docker.com/products/docker-desktop
  - Windows: Docker Desktop with WSL2 backend
  - macOS: Docker Desktop (Apple Silicon supported)
  - Linux: Docker Engine + Docker Compose plugin

### Quick start

```bash
# 1. Clone / unzip the project
cd uniops-pro

# 2. First-time setup (generates secret keys)
make setup
#  Windows (no make): copy backend\.env.docker.example backend\.env.docker

# 3. Start everything
make dev
# OR:  docker compose up --build

# 4. Open in browser
#   Frontend:   http://localhost:5173
#   API docs:   http://localhost:8000/docs
#   Flower:     http://localhost:5555
#   Grafana:    http://localhost:3002  (admin / admin123)
#   Prometheus: http://localhost:9090
```

Login with: **admin@demo.com** / **demo123!** (seeded automatically on first run)

---

### Troubleshooting: "dial tcp: lookup registry-1.docker.io … i/o timeout"

Docker can't reach Docker Hub (common in some regions or corporate networks).

**Fix 1 — Use a mirror registry (fastest)**

Create or edit `/etc/docker/daemon.json` (Linux) or open  
Docker Desktop → Settings → Docker Engine and add:

```json
{
  "registry-mirrors": [
    "https://mirror.gcr.io",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
```

Then restart Docker, and run `docker compose up --build` again.

**Fix 2 — Use the override file (per-project)**

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Edit the file and pick the mirror closest to you
docker compose up --build
```

**Fix 3 — Pre-pull images manually** (if you have a machine that can reach Docker Hub)

```bash
docker pull postgres:16-alpine
docker pull redis:7-alpine
docker pull prom/prometheus:latest
docker pull grafana/grafana:latest
# Transfer images via: docker save / docker load
```

---

### Makefile commands

| Command | Description |
|---------|-------------|
| `make setup` | First-time setup, generate secret keys |
| `make dev` | Start full stack (foreground, live logs) |
| `make dev-bg` | Start in background |
| `make stop` | Stop all containers |
| `make clean` | Stop + delete all volumes (data reset) |
| `make logs` | Follow all logs |
| `make logs-backend` | Python backend logs only |
| `make seed` | Re-seed demo data |
| `make psql` | PostgreSQL console |
| `make shell` | Python shell in backend container |
| `make health` | Check API health |
| `make migrate` | Run DB migrations manually |
| `make monitoring` | Start Prometheus / Grafana / Flower only |

---

## Option B — No Docker (Node.js only, lightweight)

Runs the React frontend + Node.js Express backend without Docker, Postgres, or Redis.
Uses in-memory storage — data resets on restart.

### Requirements
- **Node.js** 18+ — https://nodejs.org
- **pnpm** — `npm install -g pnpm`

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

### Windows

```
start.bat
```

Then open **http://localhost:5173** — login with any email + any password (6+ chars).

### Manual start

```bash
# Install dependencies
pnpm install

# Terminal 1 — Node.js backend (port 3001)
node artifacts/server/src/index.js

# Terminal 2 — React frontend (port 5173)
PORT=5173 pnpm --filter @workspace/uniops run dev
```

---

## Option C — Python backend only (local dev, no Docker)

```bash
cd backend
pip install -r requirements.txt
# .env already has SQLite config — no Postgres needed

# Run migrations
alembic -c alembic/alembic.ini upgrade head

# Seed demo data
python scripts/seed_data.py

# Start API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then in another terminal, start the frontend with the Python backend target:

```bash
pnpm --filter @workspace/uniops run dev:local
# opens http://localhost:5173, proxies /api → localhost:8000
```

---

## Port map

| Service | Port | URL |
|---------|------|-----|
| Frontend (React/Nginx) | 5173 | http://localhost:5173 |
| Python API (FastAPI) | 8000 | http://localhost:8000 |
| Node.js API (Express) | 3001 | http://localhost:3001 |
| PostgreSQL | 5432 | — |
| Redis | 6379 | — |
| Flower (Celery) | 5555 | http://localhost:5555 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3002 | http://localhost:3002 |

---

## Environment variables

| File | Used by |
|------|---------|
| `backend/.env` | Local dev (no Docker) — uses SQLite |
| `backend/.env.docker` | Docker Compose — uses PostgreSQL |
| `artifacts/uniops/.env.local` | Frontend overrides (optional) |

Copy `backend/.env.example` or `backend/.env.docker` and edit as needed.
Third-party keys (GitHub, AWS, Stripe, etc.) are all optional — the app runs in demo mode without them.
