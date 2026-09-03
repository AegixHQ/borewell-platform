# Borewell Platform

Location-aware digital platform connecting borewell contractors, resource owners (rigs/equipment/labour), and customers. See `docs/rfc/0001-microservices-architecture.md` for the full architecture decision and `STRUCTURE.md` for how this repo is allowed to grow.

> **If you're an AI coding agent (or setting one up to work in this repo): read `AGENTS.md` first.** It's the canonical rulebook for avoiding hallucinated endpoints, unnecessary code, and unverified claims of "done" in this codebase. Nested `AGENTS.md` files in `services/*/`, `apps/`, and `packages/contracts/` add domain-specific rules on top of it.

## Services & Current State

| Service | Owner | Port (local) | Description |
|---|---|---|---|
| platform-spine | Dev A | 8001 | Identity/RBAC, Job Orchestration state machine, Gateway routing |
| quotation | Dev B | 8002 | Configurable pricing engine, Estimation engine, Quotations |
| resource-network | Dev C | 8003 | Inventory CRUD, Resource lifecycle |
| payments-data | Dev D | 8004 | DB-enforced idempotent payments, Sync cross-service validation |

## Quick Start

**Prerequisites:** Docker/Podman, Docker Compose / Podman Compose, Python 3.11+, Node.js 20+

```bash
# 1. Clone the repo
# 2. Copy and fill in secrets (only JWT_SECRET is required to start)
cp services/platform-spine/.env.example services/platform-spine/.env
# Edit: set JWT_SECRET to any long random string

# 3. Start all services, databases, and redis
make up

# 4. Verify everything is healthy
curl localhost:8001/healthz   # platform-spine
curl localhost:8002/healthz   # quotation
curl localhost:8003/healthz   # resource-network
curl localhost:8004/healthz   # payments-data
```

Install `.pre-commit-config.yaml` locally (`pip install pre-commit && pre-commit install`) to catch lint and contract-drift issues before you commit, not just in CI.

## Testing & Demo Frontend

To test the full suite of microservices in a single, unified view, you can use the built-in Developer Demo Dashboard.

**1. Start the Frontend Server**
Open a new terminal and run:
```bash
python3 -m http.server 3000 --directory tools/demo-frontend
```

**2. Access the Dashboard**
Navigate to **http://localhost:3000** in your web browser. Ensure the status indicators for all 4 services turn Green (Healthy).

**3. Run a Full Lifecycle**
1. **Auth:** Register a new user (`customer` role). The dashboard automatically logs you in and saves your token.
2. **Jobs:** Create a new job, take note of the returned Job ID. Transition its state to `estimating`.
3. **Quotations:** Use the Job ID to generate a quotation.
4. **Payments & Resources:** Explore the other tabs to verify the state machine constraints and endpoints of the remaining microservices.

## Development Commands

```bash
make test             # runs each service's test suite
make down             # stops everything and removes volumes
make lint             # ruff check across all services
make check-contracts  # verifies no service exposes an undeclared endpoint
make migrate          # runs `alembic upgrade head` on all 4 services
```

## Before you touch the top-level structure

Read `STRUCTURE.md` first. New services/apps are added by following the existing template folders, not by renaming or restructuring what's already here.

## Contracts

`packages/contracts/` is the source of truth for all inter-service communication — OpenAPI specs for synchronous calls, JSON Schema for events. Change contracts there first, in a reviewed PR, before changing service code that depends on them.
