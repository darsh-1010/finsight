.PHONY: help install dev lint lint-fix format test run docker-build docker-run clean

PYTHON ?= python3
PYTEST = PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -p pytest_asyncio.plugin

# Default target
help:
	@echo "Financial Intelligence API - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint         Run pylint on all source files"
	@echo "  make lint-src     Run pylint on src/ only"
	@echo "  make lint-api     Run pylint on api/ only"
	@echo "  make lint-fix     Auto-fix linting issues where possible"
	@echo "  make format       Format code with black and isort"
	@echo "  make typecheck    Run mypy type checking"
	@echo ""
	@echo "Testing:"
	@echo "  make test         Run all tests with coverage"
	@echo "  make test-quick   Run tests without coverage"
	@echo "  make test-stream  Run interactive streaming test in Docker"
	@echo "  make test-stream-single  Run single streaming test"
	@echo ""
	@echo "Running:"
	@echo "  make run          Start the development server"
	@echo "  make run-prod     Start the production server"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-run   Run Docker container"
	@echo "  make docker-up    Start with docker-compose"
	@echo "  make docker-down  Stop docker-compose"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        Remove cache and build artifacts"

# ============================================================================
# Setup
# ============================================================================

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install -e ".[dev]"

# ============================================================================
# Code Quality
# ============================================================================

lint:
	pylint src/ config/ --rcfile=.pylintrc

lint-src:
	pylint src/ --rcfile=.pylintrc

lint-api:
	pylint src/api/ --rcfile=.pylintrc

lint-fix:
	@echo "Auto-fixing with autopep8..."
	autopep8 --in-place --recursive src/ config/

format:
	black src/ config/ tests/
	isort src/ config/ tests/

typecheck:
	mypy src/ config/ --ignore-missing-imports

# ============================================================================
# Testing
# ============================================================================

test:
	$(PYTEST) -p pytest_cov tests/ -v --cov=src --cov=config --cov-report=term-missing --cov-report=html

test-quick:
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/unit/ -v

test-integration:
	$(PYTEST) tests/integration/ -v

test-stream:
	docker compose exec -it app python tests/test_streaming_local.py

test-stream-single:
	docker compose exec app python tests/test_streaming_local.py --mode single

# ============================================================================
# Running
# ============================================================================

run:
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	$(PYTHON) -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# ============================================================================
# Docker
# ============================================================================

docker-build:
	docker build -t financial-intelligence:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env financial-intelligence:latest

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# ============================================================================
# Cleanup
# ============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage 2>/dev/null || true
