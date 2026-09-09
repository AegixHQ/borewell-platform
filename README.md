# Borewell Platform

A location-aware marketplace connecting borewell customers, contractors,
and independent resource owners (rig/equipment/labour) in Tamil Nadu,
starting with a pilot in Madurai district (Virudhunagar and other
villages, expandable later). Customers request a borewell and get a
location-aware quote; contractors manage leads, quotes, and jobs, and
find nearby rigs/equipment through a real marketplace search; resource
owners list their own fleet and accept or reject booking requests
directly, independent of any one contractor.

See `docs/rfc/0001-microservices-architecture.md` for the full
architecture decision and `STRUCTURE.md` for how this repo is allowed to
grow. `docs/adr/` holds every decision made since that RFC that changes
or extends it - **read the ADRs, not just the original PRD/SRS/
Architecture docs, for the current state of the product.** In particular:
- `docs/adr/0002` - the frontend is one unified app (`apps/web-app`), not
  three separate apps per role, as the original UI/UX doc described.
- `docs/adr/0004` - resource ownership is a real multi-owner marketplace
  ("Zomato for drilling rigs"), not a single contractor's own fleet, and
  quotation pricing is location-aware for a pilot set of villages. This
  is a real, deliberate expansion beyond the original MVP scope
  documents, not a drift - see that ADR for the full reasoning.

> **If you're an AI coding agent (or setting one up to work in this
> repo): read `AGENTS.md` first.** It's the canonical rulebook for
> avoiding hallucinated endpoints, unnecessary code, and unverified
> claims of "done" in this codebase. Nested `AGENTS.md` files in
> `services/*/`, `apps/`, and `packages/contracts/` add domain-specific
> rules on top of it.

## Services & Current State

| Service | Owner | Port (local) | Description |
|---|---|---|---|
| platform-spine | Dev A | 8001 | Identity/RBAC (customer/contractor/resource_owner/admin), Job Orchestration state machine, job completion + variance tracking |
| quotation | Dev B | 8002 | Configurable pricing engine, location-aware depth estimation (pilot service areas), quotations |
| resource-network | Dev C | 8003 | Multi-owner resource inventory, cross-owner nearest-resource search, booking request flow (request/accept/reject), pilot service-area reference data |
| payments-data | Dev D | 8004 | DB-enforced idempotent payments, sync cross-service validation, real Razorpay integration (order creation + signed webhook confirmation - needs live API keys, see `docs/deployment/PRODUCTION.md` section 4) |
| web-app | - | 5173 (dev) / 80 (prod) | Single React/Vite frontend for all 4 roles - customer, contractor, resource_owner, admin (see `docs/adr/0002`) |

`apps/shared-ui` is a shared npm workspace package (not a standalone
service) holding API client functions and auth helpers used by `web-app`.

## Quick Start (local development)

**Prerequisites:** Docker/Podman, Docker Compose / Podman Compose, Python 3.11+, Node.js 20+

```bash
# 1. Clone the repo
# 2. Copy and fill in secrets (only JWT_SECRET is required to start)
cp services/platform-spine/.env.example services/platform-spine/.env
# Edit: set JWT_SECRET to any long random string

# 3. Start all 4 backend services, the frontend, databases, and redis
make up

# 4. Verify everything is healthy
curl localhost:8001/healthz   # platform-spine
curl localhost:8002/healthz   # quotation
curl localhost:8003/healthz   # resource-network
curl localhost:8004/healthz   # payments-data

# 5. Open the app
# http://localhost:5173
```

Install `.pre-commit-config.yaml` locally (`pip install pre-commit && pre-commit install`) to catch lint and contract-drift issues before you commit, not just in CI.

## Production Deployment

Single-VM deployment via `docker-compose.prod.yml`, per Architecture doc
section 10's explicit decision to stay off managed orchestration until
there's real multi-contractor load. **Full runbook:
`docs/deployment/PRODUCTION.md`** - covers secrets setup, first deploy,
verification, HTTPS, redeploys, and rollback. Quick reference once
`.env.prod` is configured:

```bash
make prod-up     # build + start the production stack
make prod-logs   # follow logs
make prod-down   # stop it
```

## Using the App

Register as any of the four roles from the frontend's registration
screen - `customer`, `contractor`, `resource_owner`, or `admin`. Each
role routes to its own dashboard after login (client-side routing only;
the real access-control boundary is every backend service's `require_role`
dependency - see each service's isolation tests, e.g.
`resource-network/tests/test_resources.py` and `test_matching.py`).

**Typical flow across roles:**
1. **resource_owner** registers, lists a rig/equipment (with location +
   hourly rate) via their dashboard's "My Fleet" tab.
2. **customer** submits a job request with a location.
3. **contractor** sees the lead, optionally searches nearby resources for
   that job ("Find Nearby Rigs"), sends a booking request.
4. **resource_owner** accepts or rejects the request from their
   dashboard's "Booking Requests" tab.
5. **contractor** generates a quotation - location-aware if the job falls
   within a configured pilot service area (Madurai district villages;
   configure these via `POST /v1/service-areas`), otherwise the
   contractor's flat configured assumption.
6. **customer** reviews the quotation (depth range + confidence badge are
   always shown, per UI/UX doc section 7) and approves it.
7. **customer** pays through Razorpay Checkout - `payments-data` creates a
   Razorpay order, the frontend opens Checkout, and Razorpay's signed
   webhook confirms the payment on completion (needs live API keys in
   production; see `docs/deployment/PRODUCTION.md` section 4 for setup,
   and `services/payments-data/app/gateway/razorpay_client.py` for the
   integration itself and its honest caveat about not being checked
   against live Razorpay docs).
8. **contractor** advances the job through its lifecycle and logs actual
   depth/cost at completion; quoted-vs-actual variance is computed and
   stored automatically.

## Raw API Developer Dashboard (optional, secondary to `web-app`)

`tools/demo-frontend` is a single-file, dependency-free HTML dashboard for
exercising every backend endpoint directly - useful for verifying service
health and API behavior without going through the full product UI/role
flow. It predates `web-app` and is not a substitute for it; use `web-app`
(above) for anything resembling the real product experience, and this
for quick backend-only debugging.

```bash
python3 -m http.server 3000 --directory tools/demo-frontend
# then open http://localhost:3000
```

## Development Commands

```bash
make test             # runs each backend service's test suite
make up               # start the dev stack (backend + frontend + DBs + redis)
make down             # stops everything and removes volumes
make lint             # ruff check across all backend services
make check-contracts  # verifies no service exposes an undeclared endpoint
make migrate          # runs `alembic upgrade head` on all 4 backend services
make prod-up          # build + start the production stack (needs .env.prod)
make prod-down        # stop the production stack
make prod-logs        # follow production logs
```

## Before you touch the top-level structure

Read `STRUCTURE.md` first. New services/apps are added by following the existing template folders, not by renaming or restructuring what's already here.

## Contracts

`packages/contracts/` is the source of truth for all inter-service communication — OpenAPI specs for synchronous calls, JSON Schema for events. Change contracts there first, in a reviewed PR, before changing service code that depends on them.
