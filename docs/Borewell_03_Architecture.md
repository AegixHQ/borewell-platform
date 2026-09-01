# Borewell Platform — System Architecture Document

**Project:** Borewell Platform
**Scope:** MVP + near-term extensibility
**Date:** August 23, 2026
**Note:** This document is consistent with `docs/rfc/0001-microservices-architecture.md` in the repo — that RFC is the source of truth for repo structure and contracts; this document focuses on the architecture decisions themselves.

---

## 1. Recommended Tech Stack

Chosen for being practical for a 4-person team to actually ship, not for being maximally impressive:

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Async support, automatic OpenAPI generation (which the contract-first workflow depends on directly), fast to iterate with |
| Frontend | React + Vite | Standard, well-supported, fast local dev |
| Database | PostgreSQL (one schema/instance per service) | Relational data fits this domain (jobs, quotations, payments all have clear structure); DB-per-service keeps services genuinely independent |
| Event/cache layer | Redis | Sufficient for pub/sub at 4-service scale; avoids the operational overhead of Kafka/RabbitMQ this project doesn't need yet |
| Containerization | Docker + Docker Compose | Local dev parity across 4 devs without each hand-configuring their machine |
| CI | GitHub Actions | Free at this scale, path-triggered per service |

**Explicitly avoided for now:** Kubernetes, a message broker beyond Redis, a microservices mesh/service registry — all real technologies, none justified at 4-service, single-contractor-pilot scale. Revisit only when actual load or team size demands it.

---

## 2. System Components

Four backend services (full detail in RFC 0001 §2/§9):

| Service | Responsibility | MVP status |
|---|---|---|
| `platform-spine` | Auth, job state machine, notifications, gateway routing | Fully active |
| `quotation` | Pricing engine + estimation engine | Fully active (flat-depth estimate only — see PRD §5) |
| `resource-network` | Inventory, matching, media | Inventory CRUD only in MVP; matching engine is Phase 1 |
| `payments-data` | Payments, analytics | Single-flow payment only in MVP; split settlement is Phase 1 |

---

## 3. Frontend

Two active apps in MVP: **Customer App**, **Contractor App**. `Resource Owner App` exists as a scaffold but isn't functionally needed until resource-network's matching engine ships.

- **State management:** keep it simple for MVP — component state + fetch/React Query for server state. No global state library needed yet; adding one before there's a real cross-screen state-sharing problem would be exactly the kind of unnecessary complexity the RFC's `AGENTS.md` warns against.
- **Routing:** standard client-side routing per app; each app is a separate deployable bundle (RFC 0001 §3).
- **Shared components:** anything used by more than one app lives in `apps/shared-ui`, not duplicated.

---

## 4. Backend

- Each service is a standalone FastAPI app with its own `/healthz`, `/readyz`, and OpenAPI-documented routes.
- Services never call each other's databases directly — only via HTTP (sync) or Redis events (async), per RFC 0001 §5.
- A single API Gateway is the only entry point frontends talk to; it validates JWTs once and routes to the correct service.

---

## 5. APIs

- REST, versioned from `/v1/` on day one.
- Every endpoint is defined in `packages/contracts/openapi/<service>.yaml` **before** it's implemented — this is enforced mechanically by the `contract-check` tool in the repo, not just by convention.
- Breaking changes get a new version path; `/v1/` is never silently changed once other services depend on it.

---

## 6. Authentication

- `platform-spine` issues JWTs on login.
- Every other service verifies the JWT signature locally — no synchronous call back to `platform-spine` per request, which would create a hard availability dependency for every other service.
- Role (`customer`/`contractor`/`admin`) is embedded in the token and checked at the endpoint level (SRS §7).

---

## 7. Data Flow

**Customer requests a quote → job created → quote sent → approved → paid → tracked → completed:**

```
Customer App
     │  POST /v1/jobs (via gateway)
     ▼
platform-spine  ──creates Job (status: lead)──▶  Postgres (platform-spine)
     │  emits: job.created
     ▼
quotation  ──consumes job.created, generates quote using contractor's
              pricing rules──▶  Postgres (quotation)
     │  emits: job.quoted
     ▼
Customer App  ◀── displays quotation, customer approves
     │  POST /v1/payments (via gateway, idempotency key required)
     ▼
payments-data  ──records payment──▶  Postgres (payments-data)
     │  emits: payment.completed
     ▼
platform-spine  ──advances Job status through booking → drilling →
                    progress, driven by contractor actions in Contractor App
     │  on completion: contractor logs actual depth/cost
     │  emits: job.completed
     ▼
payments-data (analytics)  ──stores quoted-vs-actual variance for
                              future reference (RFC 0001 §6.3 data threshold)
```

---

## 8. Storage

- Structured data: PostgreSQL, one database per service (SRS §5 entities map directly to tables).
- Documents/photos (site images, etc.): not required for MVP functionality; when needed, object storage (S3-compatible) referenced by URL from `resource-network`'s media module — deferred, not built speculatively ahead of need.

---

## 9. Security

- HTTPS everywhere; no plaintext credentials or payment details stored (SRS §9).
- Secrets via `.env` locally (gitignored), a real secrets manager once there's a staging/prod target — never hardcoded, never committed.
- Idempotency keys on all payment mutations (SRS FR-PAY-02) to prevent duplicate-charge bugs, which are the highest-cost class of bug in this domain.
- DB-per-service isolation means a bug or compromise in one service cannot directly read another service's data.

---

## 10. Deployment

**MVP:** a single small cloud VM (or equivalent) running the same `docker-compose.yml` used locally — deliberately simple. A single-contractor pilot does not justify a managed container orchestration platform.

**Path to scale (not built yet, not needed yet):** once there's real multi-contractor load, the natural next step is a managed container service (e.g. a managed Kubernetes or a simpler PaaS) — the DB-per-service, stateless-service design already supports this without a rewrite, which is the actual payoff of doing it this way from the start.

---

## 11. Monitoring

**MVP:** structured JSON logs per service + `/healthz`/`/readyz` checks (already in the repo scaffold) are sufficient to know if something is broken.

**Deferred, not needed yet:** a full observability stack (metrics dashboards, distributed tracing UI). RFC 0001 §7 (Sprint 9+) is where this gets picked up — building it now, before there's real traffic to observe, would be effort spent on a problem that doesn't exist yet.

---

## 12. Scalability

The architecture doesn't need to change to scale — that's the point of DB-per-service and stateless services from day one. What scaling actually requires later:
- More container instances per service (horizontal scaling) — no code change needed, services are stateless
- A real message broker if event volume outgrows Redis pub/sub — an isolated swap, since events are already schema-defined and decoupled
- Read replicas per service's database if read load grows — again, isolated to one service at a time, never a cross-service migration

This is intentionally not built now. Over-engineering for scale that doesn't exist yet is the same mistake as under-engineering for scale that does.
