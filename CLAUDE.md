# TradeQuote (working name)

Quote and job-management tool for small trade contractors. A contractor measures a job, the app calculates materials and labor from a trade template, generates a branded PDF quote, the client approves it through a public link, and the job is tracked from quote to paid.

Built first for a real user: KBS Painting. Painting is the first trade. The architecture must support other trades (flooring, drywall, fencing, electrical, etc.) through data, not new code.

This is a portfolio project and a possible startup. Code quality, tests, and clear architecture matter more than speed.

## How to work with me (read this first)

- I'm a new-grad engineer and I'm using this project to learn. Explain what you're doing and why, in plain language, before and after each step.
- Comment every non-trivial block of code: what it does and why it's written that way.
- Work in small steps. Plan first, wait for my approval, then implement ONE milestone at a time. Stop at the end of each milestone and summarize what was built, what I should understand, and how to verify it.
- Never skip ahead to later milestones or add features that aren't in the current milestone.
- When there's a real design choice, give me 2 options with trade-offs and a recommendation. Don't silently pick.
- After each milestone, give me 2-3 questions I might get asked in an interview about what we just built.
- If something is unclear, ask. Don't guess about business rules; I'll confirm them with KBS.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x (typed, `Mapped[]` style), Pydantic v2, Alembic, pytest
- Database: PostgreSQL (Docker locally)
- Frontend: Next.js (App Router), React, TypeScript strict mode, Tailwind
- PDF: server-side HTML-to-PDF (propose WeasyPrint vs. alternatives when we get there)
- Auth: JWT-based (propose options at the auth milestone; I've used Supabase Auth before)
- Later: AWS deployment with Terraform and GitHub Actions. Keep the app 12-factor friendly (config from env vars, no local-disk state) so this is easy.

## Repo layout

```
/backend    FastAPI app
  app/
    api/           routers (HTTP only, no business logic)
    services/      business logic
    repositories/  database access; tenancy enforced here
    models/        SQLAlchemy models
    schemas/       Pydantic request/response models
    estimating/    pure estimating engine (no DB, no HTTP)
  tests/
  alembic/
/frontend   Next.js app
/infra      Terraform (later)
docker-compose.yml, Makefile, .github/workflows/
```

## Architecture rules (non-negotiable)

1. **Layering:** routers -> services -> repositories -> models. Routers never touch the DB directly.
2. **Multi-tenancy:** every tenant-owned table has `organization_id`. The org is resolved server-side from the authenticated user, never from the request body or URL. Repositories always filter by it. Write tests proving one org cannot read or modify another org's data.
3. **Money:** stored as integer cents (`BIGINT`). Never use floats for money or quantities. Use Python `Decimal` in calculations and round only at defined points.
4. **Estimating engine is pure:** functions take plain inputs (areas, template items, rates) and return results. No database, no I/O. This makes it easy to test exhaustively.
5. **Trades are data:** trade-specific rules live in `trade_templates` and `template_items`. Adding a new trade must not require code changes. If you're tempted to write `if trade == "painting"`, stop and tell me.
6. **Price snapshots:** when a quote is calculated, results are copied into `quote_line_items`. Changing a template later must never change an existing quote.
7. **Approved quotes are immutable.** Revisions create a new quote version on the same job.
8. **Public approval links:** use a cryptographically random token (`secrets.token_urlsafe(32)` or stronger), store only a hash of it, give it an expiry, and rate-limit the public endpoints. The public page exposes only that one quote.
9. **Migrations:** every schema change goes through Alembic. Never edit an applied migration.

## Data model (MVP)

- `organizations`: name, logo_url, default_labor_rate_cents, tax_rate
- `users`: organization_id, email, role (owner | staff)
- `clients`: organization_id, name, email, phone, address
- `trade_templates`: organization_id (NULL = system default that orgs copy), trade, name
- `template_items`: template_id, name, measure_type (area | linear | count), material_name, material_unit (e.g. gallon), material_unit_cost_cents, coverage_per_material_unit, waste_factor, labor_hours_per_unit, default_coats
- `jobs`: organization_id, client_id, title, address, status (quoted | approved | scheduled | in_progress | completed | paid)
- `quotes`: organization_id, job_id, version, status (draft | sent | approved | declined), public_token_hash, token_expires_at, subtotal_cents, tax_cents, total_cents, deposit_required_cents, approved_at, approved_by_name
- `quote_areas`: quote_id, name, measure_type, quantity, template_item_id, coats
- `quote_line_items`: quote_id, area_id (nullable), description, quantity, unit, unit_price_cents, total_cents, is_override
- `payments`: organization_id, job_id, amount_cents, kind (deposit | final), method, received_at

All tables: UUID primary keys, `created_at`, `updated_at`. Add indexes on `organization_id` and foreign keys. Use DB constraints (enums/checks, NOT NULL, unique quote version per job) as a second line of defense.

## Estimating rules (painting, first version)

- Material quantity = quantity x coats / coverage_per_material_unit x (1 + waste_factor), then round UP to whole purchase units.
- Labor hours = quantity x coats x labor_hours_per_unit, rounded to the nearest 0.25 hour.
- Line totals in cents, rounded half-up. Tax applied to the subtotal.
- Contractors can override any line; overrides are flagged and survive recalculation.
- The seed numbers are placeholders. Real coverage, labor, and pricing numbers will come from KBS.

## Milestones (build in this order, one at a time)

0. **Scaffold:** repo layout, docker-compose Postgres, FastAPI health check, Next.js app, Makefile (`make dev`, `make test`, `make lint`, `make verify`), ruff + mypy + pytest, GitHub Actions CI.
1. **Data model:** SQLAlchemy models, first Alembic migration, seed script with a default painting template.
2. **Estimating engine:** pure functions plus thorough unit tests (rounding, waste, coats, zero/edge values, overrides). Aim for full coverage of this module.
3. **Auth + tenancy:** sign-up creates an org and owner, JWT auth, org resolution, cross-tenant isolation tests.
4. **Core API:** clients, jobs, quotes, areas, recalculation, quote versioning. Integration tests for each endpoint.
5. **Frontend:** client list, job pipeline board, quote builder with live totals.
6. **PDF + public approval:** branded PDF, secure public link, approve/decline with typed name, status updates.
7. **Payments:** record deposit/final payments, job moves to paid.
8. **Second trade (the proof):** add flooring or drywall using ONLY seed data. If any code change is needed, stop and explain why.

Out of scope until after the MVP: photo-based measuring, Stripe, scheduling calendar, SMS, crew management, accounting integrations.

## Definition of done (every milestone)

- `make verify` passes: lint, type checks, all tests.
- New behavior has tests. Business rules have unit tests; endpoints have integration tests.
- No secrets in code; config comes from environment variables, with a `.env.example` documenting them.
- README updated with how to run what was just built.
- A short summary for me: what changed, why, how to verify it, and interview questions.
- Small, focused git commits with clear messages.
