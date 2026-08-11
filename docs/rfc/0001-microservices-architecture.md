# RFC 0001 — Borewell Platform: Microservices Architecture, Repo Strategy & Sprint Roadmap

**Status:** Proposed
**Author:** Shrey Kumar
**Date:** August 11, 2026
**Decision:** Monorepo, contract-first microservices, 4-person domain-aligned ownership

---

## 1. Decision Summary

- **One repo, isolated services.** Monorepo for coordination speed; each service still owns its own database, its own deploy artifact, and talks to others only through versioned contracts — never direct imports of another service's internals.
- **Contracts are written before code.** OpenAPI specs and event schemas live in a shared `packages/contracts` folder and are the actual integration surface between the 4 devs — not the repo structure itself.
- **4 services, domain-aligned, not headcount-aligned.** Grouped by coupling so integration pain stays inside one person's head instead of becoming a cross-dev sync tax.
- **Assumed stack** (swap freely, but this is what the examples below assume): Python + FastAPI per service, PostgreSQL (one schema/instance per service), Redis for the event bus, React for the three frontends, Docker Compose for local dev, GitHub Actions for CI. This is recommended partly because it matches stacks already used successfully on your other projects (Sparkeefy Wingman's FastAPI backend) — familiar tooling reduces setup friction for a 4-person team.

> **Note on scope:** This RFC proposes the repo skeleton below as the target structure. If a repo already exists with a different layout, share it and this doc should be trued up against it rather than treated as the source of truth — see §9.3.

---

## 2. Service Ownership

| Service | Owner | Responsibilities |
|---|---|---|
| **platform-spine** | Dev A | Identity/RBAC, Job Orchestration (state machine), Notifications, API Gateway routing |
| **quotation** | Dev B | Location Intelligence & Estimation Engine, Quotation/Pricing Engine |
| **resource-network** | Dev C | Resource Matching Engine, Inventory (rig/equipment/labour), Document/Media Storage |
| **payments-data** | Dev D | Payments & Split Settlement, Data & Analytics |

Dev A ships first and thinnest — everyone else's service depends on job state and auth tokens existing, even as stubs.

---

## 3. Repository Skeleton

```
borewell-platform/
├── README.md
├── Makefile
├── docker-compose.yml
├── docker-compose.override.yml.example
├── .github/
│   └── workflows/
│       ├── ci-platform-spine.yml       # path-triggered: services/platform-spine/**
│       ├── ci-quotation.yml            # path-triggered: services/quotation/**
│       ├── ci-resource-network.yml     # path-triggered: services/resource-network/**
│       ├── ci-payments-data.yml        # path-triggered: services/payments-data/**
│       └── ci-frontend.yml             # path-triggered: apps/**
├── packages/
│   └── contracts/
│       ├── openapi/
│       │   ├── platform-spine.yaml
│       │   ├── quotation.yaml
│       │   ├── resource-network.yaml
│       │   └── payments-data.yaml
│       └── events/
│           ├── job.created.schema.json
│           ├── job.quoted.schema.json
│           ├── job.completed.schema.json
│           ├── resource.assigned.schema.json
│           └── payment.completed.schema.json
├── services/
│   ├── platform-spine/
│   │   ├── app/
│   │   ├── tests/
│   │   ├── alembic/               # migrations, this service's DB only
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── quotation/
│   │   ├── app/
│   │   │   ├── estimation/        # Location Intelligence & Estimation Engine
│   │   │   └── pricing/           # Quotation rules engine
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── resource-network/
│   │   ├── app/
│   │   │   ├── matching/
│   │   │   ├── inventory/
│   │   │   └── media/
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── payments-data/
│       ├── app/
│       │   ├── payments/
│       │   └── analytics/
│       ├── tests/
│       ├── alembic/
│       ├── Dockerfile
│       └── pyproject.toml
├── apps/
│   ├── contractor-app/            # composite dashboard, touches all 4 domains
│   ├── resource-owner-app/
│   ├── customer-app/
│   └── shared-ui/                 # shared component library, design tokens
├── infra/
│   ├── gateway/                   # Traefik/reverse proxy + auth middleware config
│   └── local/                     # docker-compose seed data, dev scripts
└── docs/
    ├── rfc/
    │   └── 0001-microservices-architecture.md   (this document)
    └── adr/
```

**Rule of thumb enforced by this layout:** if a change requires editing two service folders in the same PR to work, that's a signal the contract wasn't agreed on first — not a normal occurrence.

---

## 4. Contracts — The Actual Integration Surface

Two contract types, both versioned, both reviewed in PRs like code:

### 4.1 Synchronous — OpenAPI (request/response)
Used for "get me an answer now" calls (e.g., Contractor App asking Quotation service for a price).

```yaml
# packages/contracts/openapi/quotation.yaml (excerpt)
paths:
  /v1/quotations:
    post:
      summary: Generate a quotation for a job
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [job_id, location, job_type]
              properties:
                job_id: { type: string, format: uuid }
                location:
                  type: object
                  properties:
                    lat: { type: number }
                    lng: { type: number }
                job_type: { type: string, enum: [residential, agricultural, commercial] }
      responses:
        '200':
          description: Quotation generated
          content:
            application/json:
              schema:
                type: object
                properties:
                  quotation_id: { type: string, format: uuid }
                  estimated_depth_range:
                    type: object
                    properties:
                      min_ft: { type: number }
                      max_ft: { type: number }
                      confidence: { type: string, enum: [low, medium, high] }
                  line_items:
                    type: array
                    items: { type: object }
                  total_estimate: { type: number }
```

### 4.2 Asynchronous — Event schemas (state changes)
Used when a state change should trigger reactions in other services without the originating service knowing or caring who's listening.

```json
// packages/contracts/events/job.completed.schema.json
{
  "$id": "job.completed.v1",
  "type": "object",
  "required": ["job_id", "actual_depth_ft", "actual_cost", "completed_at"],
  "properties": {
    "job_id": { "type": "string", "format": "uuid" },
    "actual_depth_ft": { "type": "number" },
    "actual_cost": { "type": "number" },
    "resources_used": { "type": "array", "items": { "type": "string" } },
    "completed_at": { "type": "string", "format": "date-time" }
  }
}
```

**Core events:** `job.created`, `job.quoted`, `job.approved`, `resource.assigned`, `job.completed`, `payment.completed`. `job.completed` is the important one — Payments (settle + payout) and Data/Analytics (feed the Estimation Engine) both react to it independently.

### 4.3 Contract workflow
1. Schema change proposed as a PR to `packages/contracts/` only.
2. Reviewed by whichever dev(s) consume it — not just the owner.
3. Merged → both producer and consumer services build against the new version.
4. **Never break a contract in place.** Add `/v2/` or a new event version; don't silently change `/v1/` semantics.

---

## 5. Production-Grade Architecture

This is the section that turns "4 services in folders" into something that survives real usage.

| Concern | Approach |
|---|---|
| **API Gateway** | Single entry point (Traefik or a thin FastAPI gateway) routes `/quotation/*`, `/resources/*`, etc. to services; handles auth token validation once, not per-service |
| **Auth** | JWT issued by platform-spine; every other service validates the token signature locally (no per-request call back to platform-spine — avoids a hard dependency chain) |
| **Error format** | Every service returns the same error shape, so frontends handle errors identically regardless of which service failed: `{"error": {"code": "...", "message": "...", "trace_id": "..."}}` |
| **Observability** | Structured JSON logs from every service; a `trace_id` generated at the gateway and passed through every downstream call and event, so one job's full path across 4 services is traceable in logs |
| **Health checks** | Every service exposes `/healthz` (liveness) and `/readyz` (dependency check, e.g. DB reachable) — required for Docker Compose and any orchestrator later |
| **Resilience** | Timeouts + retry-with-backoff on all inter-service HTTP calls; payment operations use idempotency keys so a retried request can't double-charge or double-payout |
| **Database-per-service** | Non-negotiable: platform-spine, quotation, resource-network, and payments-data each get their own Postgres schema (own instance in prod). No service queries another's tables directly — full stop, even for "just a quick join" |
| **Migrations** | Alembic per service, scoped to that service's schema only |
| **API versioning** | `/v1/` from day one; breaking changes get `/v2/`, old version stays live until nothing depends on it |
| **Secrets** | `.env` (gitignored) for local dev; a real secrets manager (not env vars in CI config) once there's a staging/prod deploy target |
| **CI/CD** | Path-triggered GitHub Actions per service — a change to `services/quotation/**` only builds/tests/deploys quotation, not all 4 services. Keeps 4 devs from blocking each other on unrelated CI runs |
| **Environments** | local (Docker Compose) → staging → production, same container images promoted between them, not rebuilt per environment |
| **Testing** | Unit tests per service (business logic); schema-validation tests confirming each service's actual responses match its OpenAPI spec (catches contract drift automatically in CI, not just at review time); a docker-compose-based integration test suite for the 2–3 critical cross-service flows (job creation → quote → completion) |

---

## 6. AI / Estimation Engine — Explicit Scope

The Estimation Engine is the part most likely to silently expand into "add ML to everything." Scoping it precisely now avoids that.

### 6.1 In scope (v1)
- **Reference-data lookup:** district/block-level groundwater and geological data pulled from public sources (CGWB, GSI), used only as a coarse prior for a region.
- **Nearby-historical-job averaging:** a simple statistical function — mean/median actual depth from the platform's own completed jobs within a configurable radius, weighted by recency and distance. This is arithmetic, not a trained model.
- **Confidence bucketing:** confidence (`low` / `medium` / `high`) is derived from a rule: sample count of nearby historical jobs (e.g. <5 jobs = low, 5–20 = medium, 20+ = high). No probabilistic model is being fit.
- **Output is always a range**, never a single number, and is always labeled as an estimate in every UI surface.

### 6.2 Explicitly out of scope (v1)
- Trained ML/regression models of any kind.
- Computer vision on site photos.
- Any autonomous pricing decision — the contractor always reviews and can override before a quotation is sent; the engine proposes, it never auto-sends.
- Predictive maintenance, demand forecasting, or any other "AI" feature not directly tied to depth/cost estimation.
- Chatbot/LLM-based customer interaction.

### 6.3 Gate for revisiting scope
Do not consider a trained model until there is a defined minimum dataset (e.g., 50+ completed jobs within 5km of a target region) — before that threshold, a trained model has nothing meaningful to learn from and just adds opacity to what is currently an explainable, auditable calculation. This threshold should be tracked in the Data & Analytics service and surfaced on the contractor's estimation-confidence dashboard, not decided ad hoc.

---

## 7. Sprint Roadmap (2-week sprints)

### Sprint 0 — Setup (Week 1)
- Repo skeleton committed (§3)
- `packages/contracts` scaffolded with placeholder schemas for the 6 core events + 4 OpenAPI specs
- Docker Compose baseline: 4 empty services + Postgres x4 + Redis, all boot with health checks passing
- CI skeleton: path-triggered pipelines exist, even if they just run `pytest --collect-only`

### Sprint 1–2 — Platform Spine + parallel stubs
- **Dev A:** Auth/JWT issuance, Job state machine (§8 of the PRD) with in-memory or minimal persistence, API Gateway routing live
- **Dev B / C / D:** Build against Sprint 0's mocked contracts — no real cross-service calls yet, just service skeletons responding with fixture data matching the agreed schema

### Sprint 3–4 — Core domain logic, still isolated
- **Dev B:** Quotation Engine v1 — static rule-based pricing only; Estimation Engine returns a **flat assumed depth** (no historical averaging yet)
- **Dev C:** Resource/Inventory CRUD — rig/equipment profiles, availability status; **no matching algorithm yet**, contractor assigns manually
- **Dev D:** Payments v1 — single customer→contractor payment flow; **no split settlement yet**

### Sprint 5–6 — Integration → **MVP boundary**
- Mocked contracts replaced with real service-to-service calls
- End-to-end flow works: lead → quote (flat-depth estimate) → customer approval → manual resource assignment → job tracked to completion → single payment collected
- Contract-validation tests added to CI (real responses checked against OpenAPI/event schemas)

> **MVP = end of Sprint 6.** Explicitly:
> - **In:** full job lifecycle, rule-based quotation, manual resource assignment, single-flow payment, basic job tracking UI in all 3 apps
> - **Out:** Resource Matching Engine (ranked suggestions), Payment splitting/payouts, historical-data-based estimation, analytics dashboards, notifications beyond basic status change

### Sprint 7–8 — Post-MVP: network intelligence
- **Dev C:** Resource Matching Engine — ranked suggestions by availability/distance/cost
- **Dev D:** Payment Splitting — contractor/rig/equipment/labour/platform-fee payouts, GST invoicing
- **Dev B:** Estimation Engine upgraded to nearby-historical-job averaging + confidence bucketing (§6.1) — still no ML

### Sprint 9+ — Hardening & polish
- Analytics dashboards (Dev D), notification polish (Dev A), location intelligence reference-data integration (Dev B), observability/tracing pass across all services, load testing on the Quotation and Job Orchestration paths (highest-traffic endpoints)

---

## 8. Explicit Non-Goals of This RFC
- Does not select a cloud provider or deployment target — that's a separate infra decision once staging is needed.
- Does not define the UI/UX design system — covered by `apps/shared-ui`, owned collectively.
- Does not commit to Kafka/RabbitMQ-scale event infrastructure — Redis pub/sub is sufficient at 4-service, single-team scale; revisit only if event volume or delivery-guarantee needs actually demand it.

---

## 9. Self-Check Against Review Criteria

| Criterion | Status | Where addressed |
|---|---|---|
| Production-grade architecture | ✅ Addressed | §5 — auth, observability, resilience, DB-per-service, CI/CD, versioning, testing strategy all specified concretely |
| Sprint roadmap alignment | ✅ Addressed | §7 — every sprint maps to a named owner (Dev A–D) from §2, building in the dependency order the ownership split implies |
| Current repo skeleton alignment | ⚠️ Partial | §3 proposes a concrete target skeleton, but this hasn't been checked against an actual existing repo — see the note in §1. If one already exists, share it and this section should be reconciled against it, not assumed correct |
| AI scope | ✅ Addressed | §6 — explicit in-scope/out-of-scope lists and a stated data threshold before any ML is considered, replacing the previously implicit "estimation refinement" language |
| MVP/Sprint boundaries | ✅ Addressed | §7 — MVP is pinned to "end of Sprint 6" with an explicit in/out feature list, not a loose phase description |

The one open item is repo alignment (§3), and it's open for a real reason: I don't have visibility into any code you may have already scaffolded. Everything else in this doc is self-contained and doesn't depend on that.
