# FinSight AI Monorepo Task Runner

.PHONY: dev build down logs lint format test clean

dev:
	docker compose up -d

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	@echo "=== Linting Python (Backend) ==="
	cd backend && ruff check .
	@echo "=== Linting Python (ML Service) ==="
	cd ml && ruff check .
	@echo "=== Linting Frontend ==="
	cd frontend && npm run lint

format:
	@echo "=== Formatting Python (Backend & ML) ==="
	cd backend && ruff format .
	cd ml && ruff format .
	@echo "=== Formatting Frontend ==="
	cd frontend && npm run format

test:
	@echo "=== Running Backend Tests ==="
	cd backend && pytest
	@echo "=== Running ML Service Tests ==="
	cd ml && pytest
