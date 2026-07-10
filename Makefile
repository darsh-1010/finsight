# FinSight AI Monorepo Task Runner

.PHONY: dev build down logs lint format test clean \
        test-backend test-ml test-all security ci

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

## ── CI / Test targets ────────────────────────────────────────────────────────

# Run backend tests with coverage gate (≥60% required; target is 80%)
test-backend:
	@echo "=== Backend Tests (with coverage) ==="
	cd backend && pytest tests/ \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=60 \
		-v --tb=short --import-mode=importlib

# Run ML tests with coverage gate
test-ml:
	@echo "=== ML Tests (with coverage) ==="
	cd ml && pytest tests/ \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=60 \
		-v --tb=short --import-mode=importlib

# Run all tests (backend + ml)
test-all: test-backend test-ml
	@echo "=== All tests complete ==="

# Run bandit SAST on both Python services
security:
	@echo "=== SAST: Backend ==="
	bandit -r backend/app -ll -x backend/app/seeds,backend/app/scripts
	@echo "=== SAST: ML ==="
	bandit -r ml/src -ll -x ml/src/scripts

# Simulate the full CI pipeline locally (lint → security → tests)
ci: lint security test-all
	@echo "=== Local CI complete ==="
