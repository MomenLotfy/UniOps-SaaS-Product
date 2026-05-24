.PHONY: setup dev dev-bg prod stop clean reset-db migrate seed \
        logs logs-backend logs-worker logs-frontend \
        status shell psql health metrics monitoring \
        restart-backend build-images lint-backend help

# ── Setup ──────────────────────────────────────────────────────────────────────
setup: ## First-time setup: create .env.docker and generate secret keys
        @echo "Setting up UniOps..."
        @if [ ! -f backend/.env.docker ]; then \
                cp backend/.env.docker.example backend/.env.docker 2>/dev/null || cp backend/.env.example backend/.env.docker; \
                echo "Created backend/.env.docker from example"; \
        fi
        @if command -v openssl >/dev/null 2>&1; then \
                SECRET=$$(openssl rand -hex 32); \
                JWT=$$(openssl rand -hex 32); \
                sed -i.bak "s/change-me-run-make-setup-to-auto-generate-32chars/$$SECRET/1" backend/.env.docker; \
                sed -i.bak "s/change-me-run-make-setup-to-auto-generate-32chars/$$JWT/1" backend/.env.docker; \
                rm -f backend/.env.docker.bak; \
                echo "Auto-generated SECRET_KEY and JWT_SECRET_KEY"; \
        fi
        @echo "Setup complete. Run: make dev"

# ── Development ────────────────────────────────────────────────────────────────
dev: ## Start full stack in foreground (with live logs)
        @echo "Starting UniOps..."
        docker compose up --build

dev-bg: ## Start full stack in background
        docker compose up --build -d
        @echo ""
        @echo "UniOps is running:"
        @echo "  Frontend:   http://localhost:5173"
        @echo "  API (Python): http://localhost:8000"
        @echo "  API Docs:   http://localhost:8000/docs"
        @echo "  Node API:   http://localhost:3001"
        @echo "  Flower:     http://localhost:5555"
        @echo "  Grafana:    http://localhost:3002  (admin / admin123)"
        @echo "  Prometheus: http://localhost:9090"

prod: ## Start in production mode (no hot-reload)
        docker compose up --build -d
        @echo "Production stack started."

# ── Database ───────────────────────────────────────────────────────────────────
migrate: ## Run database migrations
        docker compose exec backend alembic -c alembic/alembic.ini upgrade head

seed: ## Seed demo data (admin@demo.com / demo123!)
        @echo "Seeding demo data..."
        docker compose exec backend python scripts/seed_data.py
        @echo "Done. Login: admin@demo.com / demo123!"

reset-db: ## Drop and recreate database (WARNING: destroys all data)
        @echo "WARNING: This will DELETE all data. Press Ctrl+C to cancel (3s)..."
        @sleep 3
        docker compose exec db psql -U uniops -c "DROP DATABASE IF EXISTS uniops_db; CREATE DATABASE uniops_db;"
        $(MAKE) migrate
        $(MAKE) seed

# ── Logs ───────────────────────────────────────────────────────────────────────
logs: ## Follow logs for all services
        docker compose logs -f --tail=100

logs-backend: ## Follow Python backend logs
        docker compose logs -f backend --tail=100

logs-worker: ## Follow Celery worker logs
        docker compose logs -f celery_worker --tail=100

logs-frontend: ## Follow frontend logs
        docker compose logs -f frontend --tail=100

# ── Utilities ──────────────────────────────────────────────────────────────────
status: ## Show running containers
        docker compose ps

shell: ## Open Python shell in backend container
        docker compose exec backend python

psql: ## Open PostgreSQL console
        docker compose exec db psql -U uniops -d uniops_db

health: ## Check backend health endpoint
        @curl -sf http://localhost:8000/api/v1/health | python3 -m json.tool 2>/dev/null || \
         curl -sf http://localhost:3001/api/health

metrics: ## Show Prometheus metrics (first 30 lines)
        @curl -sf http://localhost:8000/metrics | head -30

monitoring: ## Start only monitoring services (Prometheus, Grafana, Flower)
        @echo "Starting monitoring stack..."
        docker compose up -d prometheus grafana flower
        @echo "  Prometheus: http://localhost:9090"
        @echo "  Grafana:    http://localhost:3002  (admin / admin123)"
        @echo "  Flower:     http://localhost:5555"

restart-backend: ## Restart backend + workers without full rebuild
        docker compose restart backend celery_worker celery_beat

build-images: ## Rebuild all images without cache
        docker compose build --no-cache

# ── Cleanup ────────────────────────────────────────────────────────────────────
stop: ## Stop all services (keeps volumes)
        docker compose down

clean: ## Stop and remove volumes (WARNING: destroys all data)
        docker compose down -v --remove-orphans
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find . -name "*.pyc" -delete 2>/dev/null || true

# ── Code quality ───────────────────────────────────────────────────────────────
lint-backend: ## Check Python syntax
        cd backend && python -m py_compile $$(find app -name "*.py")
        @echo "Backend syntax OK"

# ── Kubernetes ─────────────────────────────────────────────────────────────────
k8s-setup-dev: ## Generate secrets and apply dev overlay
        bash k8s/scripts/setup-secrets.sh dev
        kubectl apply -k k8s/overlays/dev

k8s-setup-prod: ## Generate secrets and apply prod overlay
        bash k8s/scripts/setup-secrets.sh prod
        kubectl apply -k k8s/overlays/prod

k8s-dev: ## Apply dev overlay (secrets must already exist)
        kubectl apply -k k8s/overlays/dev

k8s-prod: ## Apply prod overlay (secrets must already exist)
        kubectl apply -k k8s/overlays/prod

k8s-diff-dev: ## Dry-run diff for dev overlay
        kubectl diff -k k8s/overlays/dev

k8s-diff-prod: ## Dry-run diff for prod overlay
        kubectl diff -k k8s/overlays/prod

k8s-status-dev: ## Show pod status in uniops-dev namespace
        kubectl -n uniops-dev get pods,svc,ingress

k8s-status-prod: ## Show pod status in uniops namespace
        kubectl -n uniops get pods,svc,ingress

k8s-logs-dev: ## Follow backend logs in dev
        kubectl -n uniops-dev logs -f -l app=backend --tail=100

k8s-logs-prod: ## Follow backend logs in prod
        kubectl -n uniops logs -f -l app=backend --tail=100

k8s-delete-dev: ## Delete all resources in uniops-dev namespace
        kubectl delete namespace uniops-dev

k8s-images: ## Build and push all Docker images (set REGISTRY and TAG)
        bash k8s/scripts/build-images.sh

k8s-monitoring: ## Apply Prometheus/Grafana ServiceMonitor rules
        kubectl apply -k k8s/monitoring

# ── Help ───────────────────────────────────────────────────────────────────────
help: ## Show this help
        @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
          awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
