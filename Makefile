# HIPAA Voice Agent - Makefile
# Convenient commands for development and operations

.PHONY: help setup deploy test audit backup clean logs

# Default target - show help
help:
	@echo "HIPAA Voice Agent - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup          - Initial setup and configuration"
	@echo "  make deploy         - Deploy all services (production)"
	@echo "  make deploy-dev     - Deploy for development"
	@echo "  make stop           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo ""
	@echo "Testing & Validation:"
	@echo "  make test           - Run test suite"
	@echo "  make audit          - Run HIPAA compliance audit"
	@echo "  make check-health   - Check service health"
	@echo "  make validate       - Validate configuration"
	@echo ""
	@echo "Operations:"
	@echo "  make backup         - Create encrypted backup"
	@echo "  make restore        - Restore from backup"
	@echo "  make logs           - Tail all service logs"
	@echo "  make logs-SERVICE   - Tail specific service logs"
	@echo "  make shell-SERVICE  - Open shell in service container"
	@echo ""
	@echo "Maintenance:"
	@echo "  make update         - Update dependencies"
	@echo "  make clean          - Clean temporary files"
	@echo "  make reset          - Reset all data (CAUTION!)"
	@echo "  make rotate-keys    - Rotate encryption keys"
	@echo ""
	@echo "Monitoring:"
	@echo "  make monitor        - Open monitoring dashboard"
	@echo "  make metrics        - Display current metrics"
	@echo "  make alerts         - Show active alerts"

# Setup and configuration
setup:
	@echo "Starting initial setup..."
	@chmod +x scripts/*.sh
	@if [ ! -f config/.env ]; then \
		cp config/.env.example config/.env; \
		echo "Created config/.env - please configure with your credentials"; \
	fi
	@mkdir -p data/{postgres,redis,logs/{pipecat,audit},models,backups,temp}
	@mkdir -p config/certs
	@echo "Generating encryption keys..."
	@echo "MASTER_ENCRYPTION_KEY=$$(openssl rand -base64 32)" >> config/.env.keys
	@echo "DATA_ENCRYPTION_KEY=$$(openssl rand -base64 32)" >> config/.env.keys
	@echo "Setup complete! Next steps:"
	@echo "1. Edit config/.env with your credentials"
	@echo "2. Copy keys from config/.env.keys to config/.env"
	@echo "3. Run 'make deploy' to start services"

# Deployment targets
deploy:
	@echo "Deploying HIPAA Voice Agent (Production)..."
	@./scripts/deploy.sh production

deploy-dev:
	@echo "Deploying HIPAA Voice Agent (Development)..."
	@./scripts/deploy.sh development

stop:
	@echo "Stopping all services..."
	@docker-compose down

restart:
	@echo "Restarting all services..."
	@docker-compose restart

# Testing and validation
test:
	@echo "Running test suite..."
	@python tests/test_agent.py

test-integration:
	@echo "Running integration tests..."
	@python tests/test_integration.py

audit:
	@echo "Running HIPAA compliance audit..."
	@./scripts/compliance-audit.sh

check-health:
	@echo "Checking service health..."
	@curl -s http://localhost:8081/health | python -m json.tool

validate:
	@echo "Validating configuration..."
	@python scripts/validate_config.py

# Operations
backup:
	@echo "Creating backup..."
	@./scripts/backup.sh

restore:
	@echo "Restoring from backup..."
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Usage: make restore BACKUP_FILE=backups/hipaa_backup_YYYYMMDD_HHMMSS.tar.gz.enc"; \
		exit 1; \
	fi
	@./scripts/restore.sh $(BACKUP_FILE)

# Logging
logs:
	@docker-compose logs -f --tail=100

logs-pipecat:
	@docker-compose logs -f --tail=100 pipecat

logs-temporal:
	@docker-compose logs -f --tail=100 temporal

logs-postgres:
	@docker-compose logs -f --tail=100 postgres

logs-redis:
	@docker-compose logs -f --tail=100 redis

logs-llm:
	@docker-compose logs -f --tail=100 vllm

logs-audit:
	@tail -f data/logs/audit/*.log

# Shell access
shell-pipecat:
	@docker exec -it hipaa-pipecat /bin/bash

shell-postgres:
	@docker exec -it hipaa-postgres psql -U postgres

shell-redis:
	@docker exec -it hipaa-redis redis-cli -a $$(grep REDIS_PASSWORD config/.env | cut -d= -f2)

shell-temporal:
	@docker exec -it hipaa-temporal /bin/bash

# Maintenance
update:
	@echo "Updating dependencies..."
	@docker-compose pull
	@pip install --upgrade -r requirements.txt

clean:
	@echo "Cleaning temporary files..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type f -name ".DS_Store" -delete
	@rm -rf .pytest_cache
	@rm -rf .coverage
	@docker system prune -f

reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		rm -rf data/*; \
		echo "All data has been reset"; \
	else \
		echo "Reset cancelled"; \
	fi

rotate-keys:
	@echo "Rotating encryption keys..."
	@./scripts/rotate-keys.sh

# Monitoring
monitor:
	@echo "Opening monitoring dashboards..."
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000"
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || echo "Please open http://localhost:3000 in your browser"

metrics:
	@echo "Fetching current metrics..."
	@curl -s http://localhost:9090/api/v1/query?query=up | python -m json.tool

alerts:
	@echo "Checking active alerts..."
	@curl -s http://localhost:9090/api/v1/alerts | python -m json.tool

# Development helpers
dev-setup:
	@echo "Setting up development environment..."
	@python -m venv venv
	@./venv/bin/pip install -r requirements.txt
	@./venv/bin/pip install -r requirements-dev.txt
	@./venv/bin/pre-commit install

format:
	@echo "Formatting code..."
	@black src/ tests/
	@isort src/ tests/

lint:
	@echo "Running linters..."
	@flake8 src/ tests/
	@mypy src/
	@bandit -r src/

# Docker compose shortcuts
up:
	@docker-compose up -d

down:
	@docker-compose down

ps:
	@docker-compose ps

build:
	@docker-compose build

# Database operations
db-migrate:
	@echo "Running database migrations..."
	@docker-compose run --rm pipecat python -m alembic upgrade head

db-backup:
	@echo "Backing up database..."
	@docker exec hipaa-postgres pg_dumpall -U postgres > backups/postgres_$$(date +%Y%m%d_%H%M%S).sql

db-restore:
	@echo "Restoring database..."
	@if [ -z "$(SQL_FILE)" ]; then \
		echo "Usage: make db-restore SQL_FILE=backups/postgres_YYYYMMDD_HHMMSS.sql"; \
		exit 1; \
	fi
	@docker exec -i hipaa-postgres psql -U postgres < $(SQL_FILE)

# Compliance operations
compliance-report:
	@echo "Generating compliance report..."
	@./scripts/compliance-audit.sh
	@echo "Report saved to audits/"

baa-check:
	@echo "Checking BAA status..."
	@echo "Twilio BAA: $$([ -n \"$$(grep TWILIO_HIPAA_PROJECT_ID config/.env | cut -d= -f2)\" ] && echo '✓ Configured' || echo '✗ Not configured')"
	@echo "AWS BAA: Check https://console.aws.amazon.com/artifact"
	@echo "Other vendors: Review documentation in docs/vendors/"

# Testing shortcuts
test-unit:
	@python -m pytest tests/unit/

test-integration:
	@python -m pytest tests/integration/

test-security:
	@echo "Running security tests..."
	@safety check -r requirements.txt
	@bandit -r src/

test-load:
	@echo "Running load tests..."
	@./scripts/load-test.sh --concurrent=10 --duration=60

# Call testing
test-call:
	@echo "Making test call..."
	@if [ -z "$(PHONE)" ]; then \
		echo "Usage: make test-call PHONE=+15025551234"; \
		exit 1; \
	fi
	@./scripts/test-call.sh $(PHONE)

# Version management
version:
	@echo "HIPAA Voice Agent Version:"
	@cat VERSION
	@echo ""
	@echo "Component Versions:"
	@docker-compose exec pipecat python --version
	@docker-compose exec postgres psql --version
	@docker-compose exec temporal temporal --version

# CI/CD helpers
ci-test:
	@docker-compose -f docker-compose.test.yml up --abort-on-container-exit

ci-build:
	@docker-compose build --no-cache

ci-push:
	@docker-compose push

# Default environment variables
export ENVIRONMENT ?= production
export LOG_LEVEL ?= INFO

# Include local overrides if they exist
-include Makefile.local
