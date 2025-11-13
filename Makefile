.PHONY: help install test lint format clean run-dev run-prod docker-build docker-up health-check

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Betting Expert Advisor - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

install: ## Install dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	pip install -e .
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-dev: ## Install development dependencies
	@echo "$(YELLOW)Installing development dependencies...$(NC)"
	pip install -r requirements.txt
	pip install pytest pytest-cov black flake8 mypy isort pre-commit
	pre-commit install
	@echo "$(GREEN)✓ Development environment ready$(NC)"

test: ## Run all tests
	@echo "$(YELLOW)Running tests...$(NC)"
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	pytest tests/ --cov=src --cov-report=html --cov-report=term

test-fast: ## Run tests without coverage
	@echo "$(YELLOW)Running fast tests...$(NC)"
	pytest tests/ -v --tb=short -x

lint: ## Run linting checks
	@echo "$(YELLOW)Running linting checks...$(NC)"
	flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203,W503
	@echo "$(GREEN)✓ Linting passed$(NC)"

format: ## Format code with black and isort
	@echo "$(YELLOW)Formatting code...$(NC)"
	black src/ tests/ --line-length=100
	isort src/ tests/ --profile black
	@echo "$(GREEN)✓ Code formatted$(NC)"

type-check: ## Run type checking with mypy
	@echo "$(YELLOW)Running type checks...$(NC)"
	mypy src/ --ignore-missing-imports
	@echo "$(GREEN)✓ Type checking passed$(NC)"

clean: ## Clean up generated files
	@echo "$(YELLOW)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ dist/ build/ *.egg-info
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

init-db: ## Initialize database
	@echo "$(YELLOW)Initializing database...$(NC)"
	python -c "from src.db import init_db; init_db()"
	@echo "$(GREEN)✓ Database initialized$(NC)"

health-check: ## Run system health checks
	@echo "$(YELLOW)Running health checks...$(NC)"
	python -m src.health_check

run-dev: ## Run in development mode (DRY_RUN)
	@echo "$(YELLOW)Starting in development mode...$(NC)"
	MODE=DRY_RUN python src/main.py --mode simulate

run-fetch: ## Fetch latest data
	@echo "$(YELLOW)Fetching data...$(NC)"
	python src/main.py --mode fetch

run-train: ## Train ML model
	@echo "$(YELLOW)Training model...$(NC)"
	python src/main.py --mode train

run-backtest: ## Run backtest
	@echo "$(YELLOW)Running backtest...$(NC)"
	python src/backtest.py

docker-build: ## Build Docker image
	@echo "$(YELLOW)Building Docker image...$(NC)"
	docker build -t betting-advisor:latest .
	@echo "$(GREEN)✓ Docker image built$(NC)"

docker-up: ## Start Docker containers
	@echo "$(YELLOW)Starting Docker containers...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Containers started$(NC)"

docker-down: ## Stop Docker containers
	@echo "$(YELLOW)Stopping Docker containers...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Containers stopped$(NC)"

docker-logs: ## View Docker logs
	docker-compose logs -f

monitoring-up: ## Start monitoring stack
	@echo "$(YELLOW)Starting monitoring stack...$(NC)"
	cd monitoring && docker-compose up -d
	@echo "$(GREEN)✓ Monitoring stack started$(NC)"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"

monitoring-down: ## Stop monitoring stack
	@echo "$(YELLOW)Stopping monitoring stack...$(NC)"
	cd monitoring && docker-compose down
	@echo "$(GREEN)✓ Monitoring stack stopped$(NC)"

setup: ## Complete development setup
	@echo "$(YELLOW)Running complete setup...$(NC)"
	bash scripts/dev_setup.sh

pre-commit: ## Run pre-commit hooks on all files
	@echo "$(YELLOW)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files

ci: lint type-check test ## Run all CI checks

all: clean install-dev init-db test ## Complete setup and test
