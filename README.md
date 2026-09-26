# TradeQuote

[![CI](https://github.com/IkmannBhullar/tradequote/actions/workflows/ci.yml/badge.svg)](https://github.com/IkmannBhullar/tradequote/actions/workflows/ci.yml)

Quote and job-management tool for small trade contractors. A contractor measures a job, the app
calculates materials and labor from a trade template, generates a branded PDF quote, the client
approves it through a public link, and the job is tracked from quote to paid.

Painting is the first trade; other trades are added through data, not code.

> **Status:** MVP complete (Milestones 0–8). The full loop works (quote, secure client approval,
> job board, payments, paid) for two trades, painting and flooring, where flooring was added with
> seed data only. Seed numbers are placeholders until KBS Painting provides real ones.

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
- For quote PDFs: [WeasyPrint's system libraries](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
  (Pango, HarfBuzz). Linux: `apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`.
  macOS: `brew install pango`, using an Apple Silicon Homebrew in `/opt/homebrew` on M-series Macs
  (an Intel Homebrew in `/usr/local` installs x86_64 libraries that arm64 Python can't load); you
  may need `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. Without them, everything else
  works and PDF tests are skipped with a message; CI always runs them.

## Getting started

```bash
make install   # creates .env from .env.example, installs backend + frontend deps
make seed      # starts Postgres, applies migrations, loads the default painting template
make dev       # migrates, then runs the API on :8000 and the web app on :3000
```

Then open:

- Web app: http://localhost:3000 (sign up; you'll land on Settings to enter your rates)
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
| `make migrate`  | Apply pending database migrations                              |
| `make migration name="..."` | Autogenerate a migration after changing models     |
| `make seed`     | Load system trade templates (safe to re-run)                   |
| `make db-down`  | Stop Postgres (keeps data)                                     |
| `make db-reset` | Stop Postgres and delete its data                              |

## Database

- **Schema changes go through Alembic, always.** Change a model in `backend/app/models/`, run
  `make migration name="what changed"`, then *read* the generated file in
  `backend/alembic/versions/` before committing: autogenerate is a first draft. Never edit a
  migration that has already been applied anywhere; write a new one.
- A test (`test_models_match_migrations`) fails if models and migrations drift apart.
- Tests use a separate `<db>_test` database that they recreate and migrate on every run, and each
  test runs inside a transaction that is rolled back, so tests never touch your `make dev` data.
- `make seed` loads the system-default "Interior Painting" template. **Its numbers are
  placeholders** until real coverage, labor, and pricing figures come from KBS Painting.

Key rules enforced by the database itself (not just application code):

- Money is `BIGINT` cents; rates and quantities are exact `NUMERIC`, never floats.
- Composite foreign keys make cross-organization references impossible (e.g. a job can only point
  at a client in the same organization).
- CHECK constraints for statuses, non-negative amounts, `total = subtotal + tax`, and more.

## Estimating engine

`backend/app/estimating/` turns measured areas into priced lines. It is **pure**: plain dataclasses
in, plain dataclasses out, no database or HTTP (a test fails if it ever imports them).

- Material units = quantity × coats × (1 + waste) ÷ coverage, **rounded up** per area.
- Labor hours = quantity × coats × labor hours per unit, rounded to the **nearest 0.25 h**.
- Line totals in cents, rounded half-up; tax = subtotal × rate, rounded half-up once.
- Overrides replace a line's quantity and/or unit price and survive recalculation.

Nothing in the math depends on the trade: square feet, linear feet, and counts use the same
formulas. Tests include property-based tests (Hypothesis), and `make test` fails if the engine's
line + branch coverage drops below 100%.

## Authentication

Email + password, with our own JWTs (no external auth provider).

```bash
# Sign up: creates an organization with you as owner, returns a token
curl -X POST localhost:8000/auth/signup -H 'content-type: application/json' \
  -d '{"organization_name":"KBS Painting","email":"you@example.com","password":"at least 12 chars"}'

# Log in: returns a fresh token (valid ACCESS_TOKEN_TTL_MINUTES, default 60)
curl -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"at least 12 chars"}'

# Use it
curl localhost:8000/me -H "Authorization: Bearer <access_token>"
```

In Swagger UI (http://localhost:8000/docs), click **Authorize** and paste the token.

- Passwords are hashed with Argon2id; tokens are HS256 JWTs signed with `JWT_SECRET`.
- The organization is always loaded from the authenticated user's database row, never taken from
  the request. Tenant-owned data is read and written through `TenantRepository`, which filters
  every query by that organization; tests prove one org can't reach another's data.
- Not built yet (needed before onboarding customers beyond KBS): password reset, email
  verification, login rate limiting, refresh tokens (today, you log in again after the 60-minute
  token expires).

## Core API

Explore it interactively at http://localhost:8000/docs (sign up, then **Authorize**).

| Resource | Endpoints |
| --- | --- |
| Organization | `PATCH /organization` (owner only: labor rate, tax rate, name, logo) |
| Templates | `GET /templates` (system templates + your own) |
| Clients | `POST/GET /clients`, `GET/PATCH/DELETE /clients/{id}` |
| Jobs | `POST/GET /jobs` (filter `status`, `client_id`), `GET/PATCH /jobs/{id}` |
| Quotes | `POST/GET /jobs/{id}/quotes`, `GET/PATCH /quotes/{id}` |
| Areas | `POST /quotes/{id}/areas`, `PATCH/DELETE /quotes/{id}/areas/{area_id}` |
| Overrides | `PUT/DELETE /quotes/{id}/line-items/{line_id}/override` |
| Versions | `POST /quotes/{id}/revisions`, `POST /quotes/{id}/refresh-rates` |

How quotes behave:

- **Live totals:** every change to a quote recalculates it in the same transaction and returns the
  whole quote.
- **Price snapshots:** a quote copies the organization's labor/tax rates when created, and each
  area copies its template item's rates when added. Editing templates or settings never changes
  an existing quote; `refresh-rates` deliberately pulls current prices into a draft.
- **Only drafts are editable.** To change a sent/approved/declined quote, create a revision: a new
  draft version (v2, v3...) copying the latest version's areas, rates, and overrides.
- **Overrides** replace a line's quantity and/or unit price and survive recalculation.
- Lists are paginated: `?limit=50&offset=0` returns `{items, total, limit, offset}`.
- Another organization's ids always return 404, as if they didn't exist.

## Frontend

`frontend/` is a Next.js App Router app that acts as a **backend-for-frontend**:

- The login token lives in an **httpOnly cookie** set by the Next.js server. Browser JavaScript
  never sees it; Server Components and Server Actions call FastAPI with it.
- `src/proxy.ts` redirects signed-out visitors to `/login` (a cheap cookie check); FastAPI does the
  real authentication on every call, and an expired session sends you back to login.
- API types are **generated** from FastAPI's OpenAPI schema. After changing backend endpoints or
  schemas, run `make api-types` and commit the result (CI fails if they're stale).
- The browser never calculates prices: every quote edit returns the backend's recalculated quote.

| Page | What it does |
| --- | --- |
| `/jobs` | Pipeline board; each card offers only the moves the backend allows |
| `/clients`, `/clients/[id]` | Client list, details, and a client's jobs |
| `/jobs/[id]` | Job details and quote versions |
| `/quotes/[id]` | Quote builder: areas, overrides, deposit, live totals, revisions |
| `/settings` | Company name, labor rate, tax rate |

Tests: `make frontend-test` (Vitest: utilities + quote builder with fake actions) and
`make e2e` (Playwright: a real browser through sign-up → quote → $483.00 against the full stack;
run `npx playwright install chromium` once first).

## Sending quotes and client approval

1. In the quote builder, **Send to client** freezes the draft and shows a link like
   `https://<app>/q/<token>` **once**: copy it and send it by text or email. Lost it? **New client
   link** issues a fresh one and the old one stops working.
2. The client opens the link (no account needed), sees the quote, downloads the PDF, and
   **approves** (typed full name + "I agree") or **declines** (with an optional reason).
3. Approval marks the quote approved and moves the job to **Approved** on the board.

Security (architecture rule 8):

- Tokens are 256-bit random; the database stores only their SHA-256 hash, with a 30-day expiry
  (`QUOTE_LINK_TTL_DAYS`). Expired links return 410; unknown ones 404.
- Next.js sends the token to FastAPI in an `X-Quote-Token` header, never the URL path, so it stays
  out of API access logs. Client pages send `Referrer-Policy: no-referrer`, `noindex`, `no-store`.
- Public endpoints are rate-limited in Postgres: 60 requests/minute per IP and 10 decisions/hour per
  link (`PUBLIC_REQUESTS_PER_MINUTE`, `QUOTE_DECISIONS_PER_HOUR`).
- Only the latest version of a sent, unexpired quote can be approved; the public API exposes only
  client-facing fields.
- PDFs are rendered by WeasyPrint from an autoescaped Jinja2 template, with all URL fetching
  disabled (no file:// reads, no SSRF). Dates print in `DISPLAY_TIMEZONE`.

## Payments

On a job's page, the **Payments** card shows the quote total (from the latest approved quote), what's
been paid, the balance, and any deposit still owed, and records payments (amount, deposit/final,
method, date received).

- **Paid is automatic:** a job is Paid exactly when it's completed and its balance is zero. The rule
  runs after every payment, void, and move to Completed, so the board always matches the money.
- **Payments are voided, never deleted:** a voided payment stays in the history with its reason and
  stops counting; if that reopens a balance, a Paid job goes back to Completed.
- Overpayments and future dates are rejected. "Today" is the business's date in
  `DISPLAY_TIMEZONE`, returned by the API so every client agrees on it.
- Recording a payment locks the job row (`SELECT … FOR UPDATE`), so two simultaneous payments can't
  both see the same balance and overpay.

## Adding a trade

Trades are data, not code (architecture rule 5). Flooring was added in Milestone 8 without changing
any application code:

1. Add a `TemplateSeed` with its items to `backend/app/seed.py` and list it in `SYSTEM_TEMPLATES`.
   Each item needs a measure type (area / linear / count), a material with its purchase unit and
   coverage, a waste factor, labor hours per unit, and default "coats" (use 1 when the trade has no
   such concept).
2. Run `make seed`. The template appears in every organization's quote builder.

`tests/test_second_trade.py` proves a flooring job works end to end, and fails if application code
ever names a trade.

**Known limitations for multi-trade use** (found while adding flooring; each would need a code
change, so none was made):

- The UI calls the quantity multiplier "Coats", which is painting vocabulary; flooring shows "1".
- Every item must have a material. Labor-only work (e.g. tearing out old carpet) or
  customer-supplied materials would show a $0 material line.
- One measured area feeds one item, so 250 sq ft of floor is entered twice (flooring and underlayment).
- One labor rate per organization; multi-trade businesses often pay trades differently.
- Organizations can't yet copy and edit system templates in the UI to set their own prices.

## Configuration

All configuration comes from environment variables (see [`.env.example`](.env.example)), including
`JWT_SECRET`, which must be at least 32 characters and should be generated per environment. The
frontend's settings (`API_URL`) are documented in [`frontend/.env.example`](frontend/.env.example). Locally,
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
