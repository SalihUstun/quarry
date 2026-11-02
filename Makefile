COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: up dev down logs test lint test-gateway test-ai test-web test-rust lint-gateway lint-ai lint-web lint-rust fixtures bench migration

up:
	docker compose up -d --build

dev:
	$(COMPOSE_DEV) up -d --build postgres migrate ai

down:
	docker compose down

logs:
	docker compose logs -f

test: test-gateway test-ai test-web test-rust

lint: lint-gateway lint-ai lint-web lint-rust

test-gateway:
	cd gateway && dotnet test

test-ai:
	cd ai && uv run pytest

test-web:
	cd web && npm test

test-rust:
	cd rust && cargo test

lint-gateway:
	cd gateway && dotnet format --verify-no-changes

lint-ai:
	cd ai && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests scripts

lint-web:
	cd web && npm run lint && npm run format:check && npm run typecheck

lint-rust:
	cd rust && cargo fmt --all --check && cargo clippy --all-targets -- -D warnings

bench:
	ai/.venv/bin/python bench/run.py

fixtures:
	cd ai && uv run python -m scripts.generate_chunking_fixtures

migration:
	@test -n "$(name)" || (echo "usage: make migration name=create_documents" && exit 1)
	touch db/migrations/$$(date -u +%Y%m%d%H%M%S)_$(name).sql
