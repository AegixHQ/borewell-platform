# Borewell Platform — Development Plan

**Project:** Borewell Platform
**Based on:** `Borewell_01_PRD_MVP.md`, `Borewell_02_SRS.md`, `Borewell_03_Architecture.md`, `Borewell_04_UIUX.md`
**Date:** August 23, 2026

This plan converts the four prior documents into a sequence a team can execute without guessing what "done" means at each step. Dev ownership (A/B/C/D) matches `docs/rfc/0001-microservices-architecture.md` §2 in the repo.

---

## 1. Priorities & Dependencies

Everything depends on `platform-spine` existing first — auth and job creation are load-bearing for every other service. The dependency graph:

```
platform-spine (auth + job state machine)
        │
        ├──▶ quotation (needs a job to quote against)
        │
        ├──▶ resource-network (needs a job to assign resources to)
        │
        └──▶ payments-data (needs an approved quotation to charge against)
                    │
                    ▼
        Frontend apps (need all of the above to have real endpoints,
        not mocks, before end-to-end flows can be tested)
```

This is why the roadmap below starts every dev in parallel against **mocked contracts**, then integrates once `platform-spine`'s core is real.

---

## 2. Milestones & Roadmap

### Milestone 0 — Setup (Week 1)
| Task | Owner | Depends on | DoD |
|---|---|---|---|
| Repo skeleton, contracts scaffold, CI, AGENTS.md guardrails | Dev A (lead) | — | `make up` boots all 4 services; `make test` and `make check-contracts` pass |
| Pricing-rule data model drafted | Dev B | SRS §5 | Reviewed against SRS entities table |
| Job/quotation/payment table schemas drafted | Dev A/B/D | SRS §5 | Migrations exist per service (empty tables OK at this stage) |

*(This milestone is already complete in the repo as delivered.)*

### Milestone 1 — Core backend logic (Weeks 2–3)
| Task | Owner | Depends on | DoD |
|---|---|---|---|
| `POST /v1/auth/login`, `POST /v1/jobs`, job state machine (FR-AUTH-*, FR-JOB-*) | Dev A | Milestone 0 | Matches SRS FR-AUTH/FR-JOB exactly; contract-check passes; tests cover every status-transition rule in FR-JOB-03 |
| Pricing-rule configuration + quotation generation (FR-QUOTE-*) | Dev B | Job creation contract (can build against mock until Dev A ships) | Quotation never below minimum charge (BR-01); always returns a depth range + confidence (FR-QUOTE-02/03) |
| Inventory CRUD (no matching yet) | Dev C | — | Basic resource records creatable/listable; matching engine explicitly deferred (PRD §5) |
| Payment creation with idempotency (FR-PAY-*) | Dev D | Quotation approval contract (mocked until Dev B ships) | Duplicate idempotency key never creates two payment records (verified by test, not inspection) |

### Milestone 2 — Integration (Week 4)
| Task | Owner | Depends on | DoD |
|---|---|---|---|
| Replace all mocked contract calls with real service-to-service calls | All | Milestone 1 complete for all 4 services | End-to-end flow (lead → quote → approve → pay → track → complete) runs against real services, not mocks |
| Event wiring (`job.created`, `job.quoted`, `job.completed`, `payment.completed`) | Dev A (infra) + each owning service | Milestone 1 | Each event is both emitted and consumed correctly — verified with a test that triggers the emitting action and asserts the consumer reacted |

### Milestone 3 — Frontend (Weeks 3–5, in parallel with Milestone 1–2 backend work)
| Task | Owner | Depends on | DoD |
|---|---|---|---|
| Customer App: Location Entry → Quotation → Payment → Tracking (UI/UX §4.1) | Whoever owns frontend for this slice | Corresponding backend contract (can build against mock OpenAPI responses early) | Every screen in UI/UX §4.1 implemented; loading/error/empty states from §7 present, not just happy path |
| Contractor App: Dashboard → Quotation Generator → Pricing Rules → Job List → Job Detail (UI/UX §4.2) | Whoever owns frontend for this slice | Same | Same — including the required depth-uncertainty disclosure from UI/UX §7 |

### Milestone 4 — Testing & Bug Fixing (Week 6)
| Task | Owner | Depends on | DoD |
|---|---|---|---|
| Run every acceptance criterion in SRS §11 as an automated test, not a manual check | All (per service) | Milestone 2 | All pass in CI |
| End-to-end manual walkthrough of PRD §6 user stories (US-01 through US-12) | Whole team | Milestone 3 | Every user story's flow completable without a developer intervening manually |
| Fix bugs found above | All | — | Re-run the specific failing test/story until green |

### Milestone 5 — Deployment (Week 7)
| Task | Owner | Depends on | DoD |
|---|---|---|---|
| Deploy `docker-compose.yml` stack to a single pilot VM (Architecture §10) | Dev A | Milestone 4 | All 4 services + both frontend apps reachable and passing health checks in the deployed environment, not just locally |
| Pilot with one real contractor | Whole team | Deployment | At least one full real job lifecycle completed end-to-end with a real customer and real payment |

---

## 3. MVP Scope Recap

Exactly what's in Milestones 0–5 above — nothing from the PRD §10 out-of-scope list is scheduled here. If a task during development seems to need something on that list (resource matching, split payments, historical estimation), that's a signal to stop and check the PRD/RFC before building it, not a reason to quietly expand scope mid-sprint.

---

## 4. Definition of Done (applies to every task above)

A task is not done until:
1. **It matches its SRS requirement ID exactly** — not "close enough."
2. **Tests were actually run and passed**, with real output, per `AGENTS.md`'s rule against unverified "should work" claims.
3. **`contract-check` passes** for any service touched — no undeclared endpoints (see the repo's `tools/contract-check/`).
4. **`ruff check` passes** — no dead code, no unused imports.
5. **The corresponding UI/UX screen/state is implemented**, if the task is frontend — not just the happy path; loading/error/empty states from UI/UX §7 are part of "done," not a follow-up.
6. **No scope beyond the task's own milestone row** was added without it being logged as a separate, explicitly-scoped task.

---

## 5. Testing Strategy

- **Unit tests** per service, covering business logic (pricing calculation, state-transition rules, idempotency handling) — required before a PR merges.
- **Contract tests** — `tools/contract-check/` run in CI on every push, catching drift between implementation and `packages/contracts/` automatically.
- **Integration tests** — the Milestone 2 end-to-end flow, run via Docker Compose in CI, not just locally.
- **Manual walkthrough** — the Milestone 4 user-story pass is deliberately manual once, to catch anything automated tests miss (particularly UX friction, which tests don't detect).

---

## 6. Deployment Plan

MVP deployment is deliberately minimal, per Architecture §10: one VM, the same `docker-compose.yml` used in dev, promoted rather than rebuilt. No blue-green deploy, no managed orchestration — those get justified once there's real multi-contractor load, not before. Rollback for the pilot is simply redeploying the previous image tag; anything more elaborate would be solving a problem that doesn't exist yet at this scale.
