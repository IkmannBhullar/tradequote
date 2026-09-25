# TradeQuote developer commands: the single entry point for humans AND CI.
#
# Run `make` (or `make help`) to list targets.
#
# Make basics: each target is "name: prerequisites" followed by TAB-indented
# shell commands. Each command line runs in its own shell, which is why every
# line that needs a folder starts with `cd backend &&`.
# `.PHONY` marks targets that are commands, not files Make should look for.

.PHONY: help install env db-up db-down db-reset dev dev-backend dev-frontend \
        lint typecheck test format verify \
        backend-lint backend-typecheck backend-test backend-verify \
        frontend-lint frontend-typecheck frontend-verify

# First target = what plain `make` runs.
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
install: env ## Install backend + frontend dependencies (from lockfiles)
	cd backend && uv sync
	cd frontend && npm ci

env: ## Create .env from .env.example if it doesn't exist yet
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

# ---------------------------------------------------------------------------
# Database (Postgres in Docker)
# ---------------------------------------------------------------------------
db-up: ## Start Postgres and wait until it's healthy
	docker compose up -d --wait

db-down: ## Stop Postgres (data is kept)
	docker compose down

db-reset: ## Stop Postgres and DELETE its data volume
	docker compose down -v

# ---------------------------------------------------------------------------
# Running the app
# ---------------------------------------------------------------------------
# `-j2` runs both dev servers in parallel; Ctrl-C stops both.
dev: db-up ## Run Postgres + API (:8000) + web app (:3000)
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend: ## Run only the API with auto-reload
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run only the Next.js dev server
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------
backend-lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .

backend-typecheck:
	cd backend && uv run mypy app tests

# Tests include integration tests against the real Postgres, so start it first.
backend-test: db-up
	cd backend && uv run pytest

backend-verify: backend-lint backend-typecheck backend-test

frontend-lint:
	cd frontend && npm run lint

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-verify: frontend-lint frontend-typecheck

lint: backend-lint frontend-lint ## Lint + format-check everything
typecheck: backend-typecheck frontend-typecheck ## Type-check everything (mypy strict, tsc strict)
test: backend-test ## Run all tests
verify: lint typecheck test ## Everything CI checks. Must pass before committing.

format: ## Auto-fix formatting and safe lint issues
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .
