PYTHON=python
UVICORN=uvicorn
ALEMBIC=alembic
CELERY=celery

.PHONY: dev worker beat migrate upgrade seed test lint format

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	$(CELERY) -A app.tasks.worker worker --loglevel=info --concurrency=4

beat:
	$(CELERY) -A app.tasks.worker beat --loglevel=info

migrate:
	$(ALEMBIC) revision --autogenerate -m "$(msg)"

upgrade:
	$(ALEMBIC) upgrade head

downgrade:
	$(ALEMBIC) downgrade -1

seed:
	$(PYTHON) scripts/seed_data.py

init-db:
	$(PYTHON) scripts/init_db.py

test:
	pytest tests/ -v --cov=app --cov-report=html

lint:
	flake8 app/ --max-line-length=100
	mypy app/

format:
	black app/ tests/
	isort app/ tests/

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f api
