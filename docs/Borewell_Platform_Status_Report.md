# Borewell Platform — Status Report, Roadmap & Developer Guide

**Date:** September 3, 2026
**Repository state:** 8 commits, `main` branch
**Test baseline:** 89 passing tests across 4 services

---

## Part 1 — What Has Been Built

### 1.1 Commit History

| # | Commit | What landed |
|---|---|---|
| 1 | `bb06a1a` | Monorepo skeleton: 5-folder structure, STRUCTURE.md stability policy, CI workflows, AGENTS.md hierarchy, ADR template |
| 2 | `4015d0d` | AI-agent guardrails: contract-conformance checker, ruff linting, PR template with AI checklist, CODEOWNERS |
| 3 | `885c875` | **platform-spine** fully implemented: JWT auth, 4-role RBAC, 14-state job state machine with Postgres persistence, Alembic migrations |
| 4 | `653e23c` | **quotation** service: configurable pricing engine (Decimal arithmetic), flat-depth estimation engine, append-only versioned quotations, approve/reject flow |
| 5 | `3012d15` | **resource-network** service: inventory CRUD, 5-state resource lifecycle (Available → Reserved → Assigned → In Use → Returned), contractor-scoped |
| 6 | `303eb13` | **payments-data** service: DB-enforced idempotent payments, real synchronous cross-service HTTP call to quotation for approval + exact-amount validation, admin-gated gateway webhook placeholders |
| 7 | `1159c94` | `resource_owner` role added; npm workspaces wired for `shared-ui`; `resource-owner-app` gets real login screen gated on role |
| 8 | `40132d1` | **Audit remediation** (two independent audits reviewed): closed F-01 (IDOR), F-03 (JWT secret), F-06 (payment error mapping); fixed enum drift, Float→Numeric money columns, composite index, pricing_rules unique constraint, `make migrate` coverage |

---

### 1.2 Services — Current State

#### `platform-spine` (port 8001)
**Endpoints implemented:**
- `POST /v1/auth/register` — creates user, returns JWT
- `POST /v1/auth/login` — authenticates, returns JWT
- `POST /v1/jobs` — customer creates a job (status: `lead`)
- `GET /v1/jobs` — lists jobs (own jobs for customers, all for contractor/admin)
- `GET /v1/jobs/{job_id}` — fetch single job including `customer_id`
- `PATCH /v1/jobs/{job_id}/status` — contractor advances job status (state machine enforced)

**Key behaviors proven by tests:**
- 14-state machine rejects skipped, backward, and invalid transitions
- Customer token cannot call contractor-only endpoints (and vice versa)
- `resource_owner` role issues/verifies correctly; isolated from all data endpoints
- JWT_SECRET is required at startup — no insecure fallback (F-03 fix)

**Migrations:** `0001` (users + jobs tables), `0002` (adds `resource_owner` to `user_role` enum)

---

#### `quotation` (port 8002)
**Endpoints implemented:**
- `POST /v1/pricing-rules` — contractor upserts pricing config per job_type
- `GET /v1/pricing-rules` — lists contractor's rules
- `POST /v1/quotations` — generates quotation from rules (calls platform-spine to verify job exists and capture real `customer_id`)
- `GET /v1/quotations/{quotation_id}` — fetch (ownership enforced for customers)
- `GET /v1/quotations/job/{job_id}/latest` — latest version for a job (ownership enforced)
- `PATCH /v1/quotations/{quotation_id}` — edit (inserts new version row, never mutates)
- `POST /v1/quotations/{quotation_id}/approve` — customer approves (ownership enforced)
- `POST /v1/quotations/{quotation_id}/reject` — customer rejects (ownership enforced)

**Key behaviors proven by tests:**
- Pricing engine uses `Decimal` arithmetic — float imprecision bug confirmed and fixed
- Minimum job charge enforced at DB level — quotation total cannot go below configured floor
- Edit creates version N+1 row; original is immutable (BR-06)
- Real cross-service call to platform-spine at generation time; fails closed if unreachable
- Customer can only read/approve/reject quotations for their own jobs (F-01 IDOR fix, 7 regression tests)
- `resource_owner` role rejected from all quotation endpoints

**Migrations:** `0001` (pricing_rules + quotations), `0002` (adds `customer_id`), `0003` (Numeric money columns, composite index, unique constraint)

---

#### `resource-network` (port 8003)
**Endpoints implemented:**
- `POST /v1/resources` — contractor registers a rig, equipment item, or labour crew
- `GET /v1/resources` — lists own resources, filterable by status
- `GET /v1/resources/{resource_id}` — fetch single resource (ownership enforced)
- `PATCH /v1/resources/{resource_id}` — update status/name/notes (ownership enforced)

**Key behaviors proven by tests:**
- 5-state lifecycle transitions all exercised
- Contractor A cannot view or edit Contractor B's resources
- `resource_owner` role correctly rejected (Phase 1 data model work required before this changes — the service currently keys resources to `contractor_id`, not an independent owner)
- Resource matching engine (`/v1/resources/match`) declared in contract as Phase 1, not implemented yet

**Migrations:** `0001` (resources table)

---

#### `payments-data` (port 8004)
**Endpoints implemented:**
- `POST /v1/payments` — customer initiates payment (idempotent; verifies quotation approval and exact amount match via real call to quotation service)
- `GET /v1/payments` — lists payments (own for customers, all for contractor/admin)
- `GET /v1/payments/{payment_id}` — fetch single payment
- `POST /v1/payments/{payment_id}/confirm` — admin marks payment completed (gateway webhook placeholder)
- `POST /v1/payments/{payment_id}/fail` — admin marks payment failed (gateway webhook placeholder)

**Key behaviors proven by tests:**
- Duplicate idempotency key returns the existing record — enforced by DB `UNIQUE` constraint, not just app logic (race-safe)
- Unapproved quotation blocks payment (FR-PAY-01)
- Amount mismatch blocks payment with clear error
- `job_id` and `quotation_id` cross-checked: a valid quotation for a different job cannot be used (F-06 fix)
- Quotation service returning 403 surfaces as a real 403 here, not a generic 502 (F-06 cascade fix)
- Analytics endpoint (`/v1/analytics/estimate-accuracy`) declared in contract as Phase 1, not implemented

**Migrations:** `0001` (payments table)

---

### 1.3 Frontend

| App | State | Notes |
|---|---|---|
| `contractor-app` | Scaffold only — builds with Vite | Milestone 3 work |
| `customer-app` | Scaffold only — builds with Vite | Milestone 3 work |
| `resource-owner-app` | Real login screen + role-gate | Role check wired to real backend; dashboard is a placeholder pending Phase 1 data model |
| `apps/shared-ui` | Real auth helper | `login()` calls platform-spine; `decodeJwtPayload()` decodes JWT role for routing; consumed via npm workspaces |

---

### 1.4 Infrastructure

| Item | State |
|---|---|
| `docker-compose.yml` | All 4 services + 4 Postgres DBs + Redis; `JWT_SECRET`, `PLATFORM_SPINE_URL`, `QUOTATION_SERVICE_URL` all correctly wired |
| `make up` | Boots everything |
| `make test` | Runs all 4 service test suites |
| `make lint` | `ruff check` across all services |
| `make check-contracts` | Conformance check on all 4 contracts |
| `make migrate` | Runs `alembic upgrade head` on all 4 services |
| GitHub Actions CI | Path-triggered per service; runs tests + ruff + contract-check |
| Pre-commit hooks | `ruff` + contract-check on every commit |
| AGENTS.md hierarchy | Root + per-service + apps + contracts; AI coding guardrails enforced mechanically |
| Contract-check tool | Catches hallucinated/undeclared endpoints; proved to catch a real fabricated route in earlier testing |

---

### 1.5 Test Count

| Service | Tests | Key things proven |
|---|---|---|
| platform-spine | 24 | Auth, RBAC, state machine, job CRUD, `resource_owner` role |
| quotation | 36 | Pricing engine (Decimal), estimation, versioning, IDOR fix (7 regression tests), cross-service failure modes |
| resource-network | 12 | Inventory lifecycle, ownership isolation, role isolation |
| payments-data | 17 | Idempotency (DB-enforced), amount check, approval check, job/quotation mismatch, error-cascade mapping |
| **Total** | **89** | — |

---

## Part 2 — What Is Not Built Yet

These are not gaps — they are deliberate scope decisions in the PRD and Development Plan, tracked here so nothing slips through.

### Milestone 2 — Event Wiring (next sprint)
Redis pub/sub events (`job.created`, `job.quoted`, `job.completed`, `payment.completed`) are schematically defined in `packages/contracts/events/` but not yet published or consumed by any service. Services currently act in isolation; the event layer is what makes them react to each other automatically.

### Milestone 3 — Frontend (parallel with Milestone 2)
The full Customer App and Contractor App UIs described in the UI/UX document are not built. Only `resource-owner-app`'s login screen exists. All three apps have working scaffolds (Vite/React, build verified).

### Phase 1 items (explicitly out of MVP scope)
- **Resource matching engine** — `POST /v1/resources/match` is declared in the contract, not implemented. Requires the contractor to assign manually via `PATCH` for now.
- **Payment gateway integration** — `confirm` and `fail` endpoints are admin-gated placeholders. A real Razorpay (or equivalent) webhook replaces both. This requires a business decision on gateway selection before engineering work can start.
- **Split payment/payout** — Contractor revenue + rig/equipment/labour owner payouts. Requires the resource-owner data model to exist first.
- **Resource Owner App** (full) — Login works and role is issued. The app itself awaits a schema change in `resource-network` (currently keys resources to `contractor_id`; needs an independent owner concept).
- **Depth estimation improvement** — Historical-job averaging and reference data (CGWB groundwater levels, GSI geological data). Currently returns a flat contractor-configured range with `confidence: low` always.
- **Quoted-vs-actual analytics** (`GET /v1/analytics/estimate-accuracy`) — Declared in contract, not built.
- **JWT refresh tokens** — Access tokens expire at 60 minutes. Refresh flow is a separate implementation; the token format already supports it.

---

## Part 3 — Roadmap

### Sprint 6 — Event Wiring (Milestone 2) — Now
**Goal:** services react to each other via Redis events instead of only through tested-but-isolated HTTP calls.

Tasks in order:
1. `platform-spine` publishes `job.created` on `POST /v1/jobs`
2. `quotation` subscribes to `job.created` and auto-generates a draft quotation
3. `platform-spine` publishes `job.completed` when contractor marks completion
4. `payments-data` subscribes to `job.completed` and stores the quoted-vs-actual variance record (foundation for US-11 margin dashboard)
5. `payments-data` publishes `payment.completed`; `platform-spine` advances job to `payment` state on receipt
6. Integration test: trigger one event chain end-to-end in Docker Compose, assert the full cascade

### Sprint 7–8 — Frontend (Milestone 3)
Build all screens from the UI/UX document. Sequencing: Customer App first (simpler linear flow), then Contractor App (more screens, more state).

**Customer App screens:**
- Location Entry → Quotation Display → Payment → Job Tracking → Job History

**Contractor App screens:**
- Dashboard → Lead Detail / Quotation Generator → Pricing Rules → Job List → Job Detail / Progress → Job Completion → Margin Summary

**Shared-ui components to build:**
- Status badge (14-state color coding), Stepper, Itemized cost list, Form input group, Data table

### Sprint 9 — Payment Gateway (Phase 1 prerequisite)
Select a real gateway (Razorpay is the natural choice for India). Replace the admin-gated `confirm`/`fail` placeholders with a real webhook that verifies the gateway's HMAC signature and advances job state. This is gated on a business decision, not an engineering one.

### Sprint 10 — Resource Matching + Resource Owner App (Phase 1)
1. Schema change in `resource-network`: add `owner_id` to resources so resource owners have an independent identity
2. Implement `POST /v1/resources/match`: ranked suggestions by availability, distance, cost
3. Build out the Resource Owner App: inventory management, availability toggle, job request acceptance, earnings view

### Sprint 11–12 — Depth Estimation Upgrade + Analytics (Phase 1)
1. Estimation engine: nearby-historical-job averaging (the data flywheel that justified storing actual depth on completion from day one)
2. Confidence bucketing: `medium`/`high` when job count within radius crosses configured thresholds
3. Analytics dashboard: quoted-vs-actual margin per job, by region, by job type (US-11)

### Sprint 13+ — Hardening, Deployment, Multi-contractor
1. Full acceptance-criterion test pass (all SRS §11 criteria as automated tests, not manual checks)
2. End-to-end manual walkthrough (Milestone 4)
3. Deploy to pilot VM (Milestone 5): same docker-compose stack, promoted not rebuilt
4. Run one real job lifecycle with a real contractor and real customer
5. After pilot: multi-contractor support (routing leads by service area, contractor-scoped data isolation at scale)

---

## Part 4 — Developer Usage Guide

### Getting Started

**Prerequisites:** Docker, Docker Compose, Python 3.11+, Node.js 20+

```bash
# 1. Clone / unzip the repo
cd borewell-platform

# 2. Copy and fill in secrets (only JWT_SECRET is required to start)
cp services/platform-spine/.env.example services/platform-spine/.env
# Edit: set JWT_SECRET to any long random string

# 3. Start all services
make up

# 4. Verify everything is healthy
curl localhost:8001/healthz   # platform-spine
curl localhost:8002/healthz   # quotation
curl localhost:8003/healthz   # resource-network
curl localhost:8004/healthz   # payments-data
```

**First-time database setup** (happens automatically inside Docker via `alembic upgrade head` in each service's CMD, but if running locally):
```bash
make migrate
```

---

### Running Tests

```bash
make test          # all 4 services
make lint          # ruff across all services
make check-contracts  # contract-conformance check
```

Running one service's tests in isolation:
```bash
cd services/platform-spine
python -m pytest -v
```

---

### Working on a Service

Each service is independently runnable:
```bash
cd services/quotation
pip install -e ".[dev]"

# Set required env vars (see .env.example)
export JWT_SECRET=your-local-dev-secret
export PLATFORM_SPINE_URL=http://localhost:8001

uvicorn app.main:app --reload --port 8002
```

The service's interactive API docs are then available at `http://localhost:8002/docs`.

---

### Adding an Endpoint

1. **Update the contract first** — edit `packages/contracts/openapi/<service>.yaml`. Submit as its own PR; get it reviewed by whoever consumes it.
2. **Implement in `app/main.py`** — the contract-check tool in CI will fail if your implementation exposes a route not declared in step 1.
3. **Write a test** — minimum: the happy path and at least one rejection/error case.
4. **Run the full check**: `make test && make lint && make check-contracts`

---

### Adding a Migration

```bash
cd services/<service-name>
alembic revision -m "describe what changes"
# Edit the generated file in alembic/versions/
alembic upgrade head   # apply locally
```

Migration naming convention: `000N_short_description.py`. Never edit a migration that has already been applied to any real database.

---

### Changing the Job State Machine

The state order lives in one place only: `services/platform-spine/app/job_state_machine.py`'s `STATE_ORDER` list. Changing it also requires:
1. Updating `services/platform-spine/app/models.py`'s `JOB_STATUSES` tuple to match
2. Adding a migration to update the `job_status` Postgres enum (`ALTER TYPE job_status ADD VALUE ...`)
3. Updating `packages/contracts/openapi/platform-spine.yaml`'s status enum list
4. Running the state-machine unit tests to confirm the new transitions are correct

---

### Environment Variables Reference

| Variable | Used by | Description |
|---|---|---|
| `DATABASE_URL` | All services | Postgres connection string |
| `JWT_SECRET` | All services | Signing/verification key — **must match across all services** |
| `JWT_EXPIRY_MINUTES` | platform-spine | Token lifetime (default: 60) |
| `PLATFORM_SPINE_URL` | quotation | Base URL to verify jobs at quotation generation time |
| `QUOTATION_SERVICE_URL` | payments-data | Base URL to verify quotation approval + amount at payment time |
| `REDIS_URL` | All services (event bus) | Redis connection string — not yet used for events, wired for Sprint 6 |

---

### Key Architectural Rules (must not break)

These are not guidelines — they are structural commitments with test coverage or tooling enforcement behind them.

1. **No service reads another's database.** All cross-service data access is via HTTP or Redis events. Violating this breaks the isolation that makes independent deployment possible.

2. **Contracts are changed before code.** `packages/contracts/openapi/<service>.yaml` is amended in a reviewed PR first. The contract-check tool then fails CI if the implementation diverges.

3. **JWT_SECRET is never hardcoded.** It is read via `os.environ["JWT_SECRET"]` (fails closed if missing) — not `os.getenv(..., "default")`.

4. **Money is Decimal, not float.** The quotation service's pricing engine, models, and edit logic all use `Decimal` internally. New financial calculations belong in `Decimal` too. See `services/quotation/app/pricing/engine.py` for the pattern.

5. **Payments are idempotent.** Every `POST /v1/payments` call requires an `idempotency_key`. The uniqueness constraint is at the DB level, not just the application level.

6. **Job state transitions are sequential.** `validate_transition()` in `platform-spine/app/job_state_machine.py` enforces this. No endpoint is allowed to set `job.status` directly without going through that function.

7. **Structural changes require an ADR.** Any new top-level folder, renamed folder, or moved folder requires `docs/adr/NNNN-description.md` and sign-off. See `STRUCTURE.md` and the existing `docs/adr/0001-developer-tooling-folder.md` for the pattern.

---

### What Each AGENTS.md Covers

AI coding agents (and humans using AI tools) must read the relevant `AGENTS.md` before making changes:

| File | Covers |
|---|---|
| `AGENTS.md` (root) | The three hallucination patterns + pre-done checklist for every PR |
| `services/platform-spine/AGENTS.md` | Job state machine ownership; auth token issuance boundary |
| `services/quotation/AGENTS.md` | Estimation engine scope boundary (no ML in MVP); pricing rule patterns |
| `services/resource-network/AGENTS.md` | 5-state inventory model; matching engine deferral |
| `services/payments-data/AGENTS.md` | Idempotency requirement; split-settlement deferral; money-handling rules |
| `apps/AGENTS.md` | Never call services directly (always through gateway); `shared-ui` as the only shared code |
| `packages/contracts/AGENTS.md` | Two-step workflow: contract PR merged before implementation PR |
