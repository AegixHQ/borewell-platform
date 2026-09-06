# ADR-0003: Move `packages/events` implementation into each service; fix Docker build context

**Status:** Accepted (engineering necessity — blocking Sprint 6 event wiring)
**Date:** 2026-09-06
**Owners involved:** Shrey Kumar (solo at time of writing) — flagging for
Dev A/B/C/D review at handoff per STRUCTURE.md's sign-off requirement,
since this does touch the shared-code convention all 4 will inherit.

## Context

`packages/events/__init__.py` was written as a shared Redis pub/sub module
- lazy-connect, fire-and-forget publishers (`job_created`, `job_quoted`,
`payment_completed`, `job_completed`) intended to be called from all four
backend services. It was never actually wired into any endpoint before
this session.

Two problems surfaced when actually wiring it in, not before:

1. **STRUCTURE.md violation.** STRUCTURE.md's top-level folder table is
   explicit: `packages/contracts/` is "the only integration surface
   between services" and explicitly excludes implementation code from
   that folder. `packages/events/` (note: not `packages/contracts/`) is a
   second `packages/*` folder that was never in STRUCTURE.md's table at
   all, and it holds real runtime logic (a Redis client, retry/fallback
   behavior) - exactly what the policy carves out as not belonging under
   `packages/`.

2. **It would not actually run in Docker.** Every service's Dockerfile
   only copies that service's own `app/`, `alembic/`, and `pyproject.toml`
   - the build context is `./services/<name>/`, one level below repo
   root, so `packages/` is outside it entirely and never reaches the
   image. `import packages.events` (or any equivalent) works when running
   from the repo root locally (e.g. under pytest with the root on
   `sys.path`) but silently fails in the one environment that actually
   matters: `docker compose up`, which is what `make up` and the
   deployment plan (Architecture doc section 10) both depend on. This is
   the kind of gap that "should work" until someone actually runs it -
   exactly what AGENTS.md's rule against unverified claims exists to
   catch, and it would have shipped broken if events had been wired
   without checking the Dockerfiles.

## Decision

- Delete `packages/events/` as a shared location for implementation code.
- Each service gets its own `app/events.py` - same lazy-connect,
  fire-and-forget Redis publish logic, copied per service rather than
  imported from a shared location. This trades a small amount of
  duplication (one ~40-line file, four times) for actually working inside
  each service's own Docker build context without changing any
  Dockerfile's `COPY` scope or introducing a shared-code mount.
- Only the *functions relevant to that service* are copied in - e.g.
  `platform-spine/app/events.py` has `job_created`/`job_status_changed`/
  `job_completed`; `quotation/app/events.py` has only `job_quoted`;
  `payments-data/app/events.py` has only `payment_completed`.
  `resource-network` doesn't publish anything yet (matching definition of
  done had nothing.
- The Redis **channel names and payload shapes** are the actual contract
  between services here (a consuming service needs to know `job.created`'s
  shape, not which file publishes it) - those now live in
  `packages/contracts/events/*.schema.json`, which is squarely inside
  `packages/contracts/`'s stated purpose. `payment.completed.schema.json`
  already exists there; the other three event schemas should be added
  there too as part of closing out Sprint 6, so the contract-first
  discipline actually covers events the same way it covers HTTP routes.

## Consequences

- **This is not purely additive** - `packages/events/__init__.py` is
  deleted, not just added-alongside. Flagging this explicitly per
  STRUCTURE.md's own rule, since a straight reading of "existing folders
  are never renamed or moved" could be read to cover this file too. The
  counter-argument: `packages/events/` was never wired into a working
  Docker build in the first place, so nothing that currently works
  depends on its current location - the cost this ADR is trying to avoid
  (breaking something that works) doesn't apply yet. If Dev A/B/C/D
  disagree once they're reviewing this at handoff, the fix is cheap to
  reverse before it's built on further.
- Each service owner (per the Dev A-D split) now owns their own
  `app/events.py` as part of their existing service folder - no new
  cross-service file to coordinate merges on, which is arguably a better
  fit for the 4-person ownership model than a shared file all four would
  need to touch.
- `packages/contracts/events/` gains 3 more schema files (`job.created`,
  `job.quoted`, `job.completed`) to match `payment.completed` - this is
  genuinely additive to `packages/contracts/`, no policy tension there.
- No Dockerfile changes needed under this design - each service already
  copies its own `app/` directory, which now includes `events.py`.
