.PHONY: dev build test lint clean

# Development
dev:
	cd backend && uvicorn aegis.main:app --reload --port 8000 &
	cd frontend && npm run dev &

dev-backend:
	cd backend && uvicorn aegis.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# Build
build:
	docker compose build

# Test
test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest

test-backend-cov:
	cd backend && python -m pytest --cov=aegis

test-frontend:
	cd frontend && npm test

# Lint
lint:
	cd backend && ruff check aegis/ tests/
	cd frontend && npm run lint

format:
	cd backend && ruff format aegis/ tests/

# Database
db-migrate:
	cd backend && alembic upgrade head

db-revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# Docker
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
