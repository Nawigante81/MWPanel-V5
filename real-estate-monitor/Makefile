# =============================================================================
# Real Estate Monitor - Makefile
# Convenient commands for development and operations
# =============================================================================

.PHONY: help build up down logs test migrate shell

# Default target
help:
	@echo "Real Estate Monitor - Available Commands:"
	@echo ""
	@echo "  make build       - Build all Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make test        - Run tests"
	@echo "  make migrate     - Run database migrations"
	@echo "  make shell       - Open shell in API container"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make scale       - Scale workers (make scale N=3)"
	@echo ""

# Build images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d

# Stop services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Run tests
test:
	docker-compose exec api pytest -v

# Run migrations
migrate:
	docker-compose exec api alembic upgrade head

# Create new migration
migration:
	docker-compose exec api alembic revision --autogenerate -m "$(msg)"

# Open shell in API container
shell:
	docker-compose exec api bash

# Open database shell
db-shell:
	docker-compose exec postgres psql -U postgres -d realestate

# Scale workers
scale:
	docker-compose up -d --scale worker=$(N)

# Clean everything
clean:
	docker-compose down -v
	docker system prune -f

# Seed sources
seed:
	docker-compose exec worker python -m app.manage seed_sources

# Run single scrape
scrape:
	docker-compose exec worker python -m app.manage run_once --source $(source)

# Check health
health:
	@curl -s http://localhost:8000/health | python -m json.tool

# View metrics
metrics:
	@curl -s http://localhost:8000/metrics | python -m json.tool

# List sources
sources:
	docker-compose exec worker python -m app.manage list_sources

# Test WhatsApp
whatsapp-test:
	docker-compose exec worker python -m app.manage test_whatsapp
