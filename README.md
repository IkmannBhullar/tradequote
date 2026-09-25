# TradeQuote

[![CI](https://github.com/IkmannBhullar/tradequote/actions/workflows/ci.yml/badge.svg)](https://github.com/IkmannBhullar/tradequote/actions/workflows/ci.yml)

Quote and job-management tool for small trade contractors. A contractor measures a job, the app
calculates materials and labor from a trade template, generates a branded PDF quote, the client
approves it through a public link, and the job is tracked from quote to paid.

Painting is the first trade; other trades are added through data, not code.

> **Status:** Milestone 0 (scaffold). The app runs and is fully checked, but has no features yet.

## Stack

| Layer    | Tech                                                                 |
| -------- | -------------------------------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, pytest (uv-managed) |
| Database | PostgreSQL 16 (Docker)                                               |
| Frontend | Next.js 16 (App Router), React 19, TypeScript (strict), Tailwind      |
| Quality  | ruff, mypy (strict), ESLint, tsc, GitHub Actions                     |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you if needed)
- Node.js 20.9+ (see `.nvmrc`)
- GNU Make (preinstalled on macOS/Linux)

## Getting started

```bash
make install   # creates .env from .env.example, installs backend + frontend deps
make dev       # starts Postgres, the API on :8000, and the web app on :3000
```

Then open:

- Web app: http://localhost:3000
- API docs (Swagger UI): http://localhost:8000/docs
- Liveness: http://localhost:8000/health
- Readiness (checks the DB): http://localhost:8000/health/ready

Postgres is published on **port 5433** (not 5432) so it doesn't collide with a locally installed
Postgres.

## Common commands

Run `make` to list everything. The important ones:

| Command         | What it does                                                   |
| --------------- | -------------------------------------------------------------- |
| `make dev`      | Run the whole app locally                                      |
| `make verify`   | Lint + type-check + tests. This is what CI runs; keep it green. |
| `make test`     | Backend tests (starts Postgres first)                          |
| `make format`   | Auto-format backend code                                       |
| `make db-down`  | Stop Postgres (keeps data)                                     |
| `make db-reset` | Stop Postgres and delete its data                              |

## Configuration

All configuration comes from environment variables (see [`.env.example`](.env.example)). Locally,
they're read from a git-ignored `.env` in the repo root; in CI and production, they're set
directly in the environment.

## Repo layout

```
backend/     FastAPI app
  app/
    api/           routers (HTTP only, no business logic)
    services/      business logic
    repositories/  database access; tenancy enforced here
    models/        SQLAlchemy models
    schemas/       Pydantic request/response models
    estimating/    pure estimating engine (no DB, no HTTP)
  tests/
frontend/    Next.js app
.github/     CI workflow
```
