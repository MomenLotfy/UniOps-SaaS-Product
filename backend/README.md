# UniOps Control Tower — Backend API

Full-featured FastAPI backend for the UniOps Control Tower platform.

## Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | FastAPI 0.111 + Uvicorn |
| **Database** | PostgreSQL + SQLAlchemy 2.0 Async (asyncpg) |
| **Cache/Broker** | Redis 7 |
| **Task Queue** | Celery 5 + Celery Beat |
| **Auth** | JWT (python-jose) + bcrypt |
| **ML** | scikit-learn + numpy + pandas |
| **Integrations** | AWS, GitHub, GitLab, Kubernetes, Stripe, Slack, SendGrid |
| **Migrations** | Alembic |
| **Testing** | pytest-asyncio + httpx |

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your credentials
docker-compose up -d
```

API docs: http://localhost:8000/docs

## Local Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start dependencies
docker-compose up -d db redis

# Run migrations
alembic upgrade head

# Seed data
python scripts/seed_data.py

# Start API
uvicorn app.main:app --reload --port 8000
```

## Architecture

```
backend/
├── app/
│   ├── main.py              # FastAPI app + lifespan + WebSocket
│   ├── config.py            # Settings (pydantic-settings)
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py    # Central router
│   │   │   ├── endpoints/   # 17 endpoint modules
│   │   │   └── websocket/   # WebSocket manager + handlers
│   │   └── webhooks/        # Inbound webhooks (GitHub, Stripe, etc.)
│   ├── core/
│   │   ├── database.py      # Async SQLAlchemy engine
│   │   ├── security.py      # JWT + bcrypt
│   │   ├── dependencies.py  # FastAPI Depends
│   │   ├── exceptions.py    # Custom exceptions
│   │   ├── redis_client.py  # Redis async client
│   │   ├── pagination.py    # Page model
│   │   └── celery_app.py    # Celery config + beat schedule
│   ├── models/              # 22 SQLAlchemy models
│   ├── schemas/             # 13 Pydantic schema modules
│   ├── services/            # 16 service classes
│   ├── integrations/        # AWS, GitHub, GitLab, K8s, Stripe, Slack, Email, Scanners
│   ├── ml/                  # ML models + feature store + registry
│   ├── tasks/               # 8 Celery tasks
│   ├── events/              # Event bus (Redis pub/sub)
│   ├── middleware/           # Logging, Audit, RateLimit, Tenant, CORS
│   ├── utils/               # Logger, JWT, Hashing, Encryption, Validators, Formatters
│   └── constants/           # Roles, Permissions, Plans, Error codes
├── alembic/                 # DB migrations
├── scripts/                 # init_db, seed_data, create_superadmin
├── tests/                   # pytest + conftest
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── Makefile
```

## API Endpoints

| Module | Prefix | Auth Required |
|--------|--------|---------------|
| Auth | `/api/v1/auth` | No |
| Users | `/api/v1/users` | Yes |
| Companies | `/api/v1/companies` | Yes |
| Integrations | `/api/v1/integrations` | Yes |
| Pipelines | `/api/v1/pipelines` | Yes |
| Pods | `/api/v1/pods` | Yes |
| Threats | `/api/v1/threats` | Yes |
| Vulnerabilities | `/api/v1/vulnerabilities` | Yes |
| Compliance | `/api/v1/compliance` | Yes |
| Costs | `/api/v1/costs` | Yes |
| Savings | `/api/v1/savings` | Yes |
| ML | `/api/v1/ml` | Yes |
| Alerts | `/api/v1/alerts` | Yes |
| Audit Logs | `/api/v1/audit-logs` | Admin |
| Webhooks | `/api/v1/webhooks` | Yes |
| Billing | `/api/v1/billing` | Yes |
| Health | `/api/v1/health` | No |

## WebSocket

Connect at `ws://localhost:8000/ws/{tenant_id}?token={jwt_token}`

Events: `alert.new`, `pipeline.update`, `pod.update`, `threat.detected`, `cost.anomaly`, `ml.insight`

## Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

## Makefile Commands

```bash
make dev        # Start with uvicorn --reload
make worker     # Start Celery worker
make beat       # Start Celery beat
make test       # Run tests
make migrate    # Run alembic upgrade head
make seed       # Seed development data
make format     # black + isort
make lint       # flake8 + mypy
```
# trigger ci
# trigger build 1781542000
