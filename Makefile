.PHONY: help build up down restart logs test clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

restart: down up ## Restart all services

logs: ## Show logs from all services
	docker-compose logs -f

logs-api: ## Show API logs
	docker-compose logs -f api

logs-worker: ## Show worker logs
	docker-compose logs -f worker

test: ## Run tests in Docker
	docker-compose run --rm api pytest -v

test-local: ## Run tests locally
	pytest -v

shell-api: ## Open shell in API container
	docker-compose exec api /bin/bash

shell-db: ## Open PostgreSQL shell
	docker-compose exec db psql -U postgres globant_challenge

clean: ## Clean up containers, volumes, and temp files
	docker-compose down -v
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache .coverage htmlcov

upload-departments: ## Upload departments CSV
	curl -X POST "http://localhost:8000/api/v1/upload/csv/departments" \
		-H "accept: application/json" \
		-H "Content-Type: multipart/form-data" \
		-F "file=@sample_data/departments.csv"

upload-jobs: ## Upload jobs CSV
	curl -X POST "http://localhost:8000/api/v1/upload/csv/jobs" \
		-H "accept: application/json" \
		-H "Content-Type: multipart/form-data" \
		-F "file=@sample_data/jobs.csv"

upload-employees: ## Upload hired_employees CSV
	curl -X POST "http://localhost:8000/api/v1/upload/csv/hired_employees" \
		-H "accept: application/json" \
		-H "Content-Type: multipart/form-data" \
		-F "file=@sample_data/hired_employees.csv"

upload-all: upload-departments upload-jobs upload-employees ## Upload all CSV files

analytics-quarterly: ## Get quarterly hires analytics
	curl "http://localhost:8000/api/v1/analytics/hired/by-quarter?year=2021" | jq

analytics-departments: ## Get departments above average
	curl "http://localhost:8000/api/v1/analytics/departments/above-average?year=2021" | jq 