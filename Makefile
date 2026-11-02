COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: up dev down logs test lint test-gateway test-ai test-web lint-gateway lint-ai lint-web migration

up:
	docker compose up -d --build

dev:
	$(COMPOSE_DEV) up -d --build postgres migrate ai

down:
	docker compose down

logs:
	docker compose logs -f

test: test-gateway test-ai test-web

lint: lint-gateway lint-ai lint-web

test-gateway:
	cd gateway && dotnet test

test-ai:
	cd ai && uv run pytest

test-web:
	cd web && npm test

lint-gateway:
	cd gateway && dotnet format --verify-no-changes

lint-ai:
	cd ai && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests

lint-web:
	cd web && npm run lint && npm run format:check && npm run typecheck

migration:
	@test -n "$(name)" || (echo "usage: make migration name=create_documents" && exit 1)
	touch db/migrations/$$(date -u +%Y%m%d%H%M%S)_$(name).sql
