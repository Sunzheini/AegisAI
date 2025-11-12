.PHONY: build up down logs clean ps

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

ps:
	docker-compose ps

# Build specific services
build-api:
	docker-compose build api-gateway

build-orchestrator:
	docker-compose build workflow-orchestrator

# Logs for specific services
logs-api:
	docker-compose logs -f api-gateway

logs-orchestrator:
	docker-compose logs -f workflow-orchestrator

# Development with rebuild
dev:
	docker-compose up --build