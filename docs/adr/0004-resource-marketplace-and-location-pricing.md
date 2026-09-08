# ADR-0004: Multi-owner resource marketplace + pilot location-aware pricing

**Status:** Accepted (client-directed scope expansion beyond the original MVP docs)
**Date:** 2026-09-07
**Owners involved:** Shrey Kumar (solo at time of writing) - flagging for
Dev A/B/C/D review at handoff, same as ADR-0003, since this changes a
core data-ownership model all four inherit.

## Context

The original PRD/SRS/Architecture docs (`Borewell_01`-`04`) scoped this as
a **single-contractor pilot**: one contractor runs leads/quotes/jobs, and
"Resource Owner" is explicitly out-of-scope ("contractor coordinates with
them manually outside the app" - PRD section 2). `resource-network`'s
`Resource.contractor_id` reflected that: a contractor's own rig
inventory, CRUD-only, no matching.

The client has since described the actual intended product differently:
**a multi-rig-owner marketplace** - "like Zomato, but for drilling
vehicles." Resource owners register independently, list their own
equipment, and log into their own dashboard. Contractors search across
*all* owners' available resources near a customer's address and send a
booking request; the owner accepts or rejects it. This is a materially
different ownership and access-control model, not an incremental feature
- it's the reason this ADR exists rather than a smaller change note.

A first pass at this work (same session, prior to this pivot being
stated) built `POST /v1/resources/match` scoped to
`contractor_id == claims["sub"]` - explicitly *not* a marketplace search,
with a comment saying so and reasoning that cross-contractor visibility
raised access-control questions nobody had decided yet. Those questions
are now decided by this ADR. That work is superseded, not layered under -
see "What changed" below.

Separately, in the same session: the client asked for quotation pricing
that varies by the customer's actual location (water table depth), for a
pilot set of Madurai district villages (Virudhunagar and others). This
was flagged as crossing two things the PRD explicitly deferred
("Automated resource matching/ranking" and "Location intelligence
(groundwater/geological reference data integration)" - PRD section 10).
The client confirmed this is a deliberate scope decision, not something
to build around quietly - hence this ADR (initially told not to bother
with one; written anyway, since retrofitting docs later is exactly the
drift-inducing pattern this project has repeatedly caught and fixed).

## Decision

### 1. Resource ownership: `Resource.owner_id`, not `contractor_id`

`platform-spine` already had `resource_owner` as a first-class
registerable/loginable role (`ROLES = ("customer", "contractor", "admin",
"resource_owner")`) - that part of the role system was already correct
and needed no change. What was missing was entirely in
`resource-network`'s data model and access rules.

Clean replace, not a data migration: confirmed with the client that no
real production data exists yet, so `resources.contractor_id` was
renamed to `owner_id` directly in the (still-uncommitted, unpushed)
migration rather than adding a second migration on top of a column that
was never live.

### 2. Booking flow: request -> accept/reject, not passive listing

A contractor does not "grab" a resource directly off the match results.
`POST /v1/bookings` creates a `pending` request; only `POST
/v1/bookings/{id}/accept` (owner-only, must own the resource) moves the
resource to `reserved`. One active (`pending` or `accepted`) request per
resource at a time, enforced at the endpoint (409 `RESOURCE_ALREADY_
REQUESTED`), to prevent two contractors both booking the same rig.

`accept` re-checks the resource is still `available` at accept time (not
just at request time) and fails with 409 `RESOURCE_NO_LONGER_AVAILABLE`
if not - closes the window where an owner marks a resource `in_use` for
something else between a request landing and the owner responding to it.

### 3. `POST /v1/resources/match` is now genuinely cross-owner

Searches all resource owners' `available` resources with a location set,
ranked by real Haversine distance (not the flat "your own resources
only" scope from the superseded first pass). Contractor-only - this is
the contractor's search tool. `resource_owner` cannot call it (403) -
matches the role split: owners manage their fleet via `/v1/resources`,
contractors search the marketplace via `/v1/resources/match` and book
via `/v1/bookings`.

Distance ranking only for this pass, per the client's explicit choice
("give a few options based on distance and relevance similar to gmaps")
- no rating/relevance signal exists yet to blend in; that's real future
work, not deferred by oversight.

### 4. Location-aware quotation pricing: pilot service areas, contractor-edited

`resource-network` gains a `service_areas` table: a handful of Madurai
district villages (Virudhunagar and others, expandable later per the
client's framing), each with a contractor/admin-edited
`estimated_water_depth_ft` + `confidence_band_ft`. `source` field defaults
to `"contractor_estimate"`, with room for a real value (e.g. `"cgwb_api"`)
once a real groundwater data provider is integrated - the client
confirmed this is deliberately deferred (no specific provider chosen yet,
and provider selection has real cost/vendor implications outside what
this session can decide unilaterally).

`quotation` service calls `GET /v1/service-areas/lookup` at generation
time via a new `location_client.py` (same HTTP-client pattern as the
existing `job_client.py`). Two-tier estimation
(`app/estimation/engine.py`):
- **Match found:** use the area's depth estimate, confidence = `"medium"`
  (a real location-specific number, but still a manual village-level
  estimate, not a verified per-site measurement - `"high"` would
  overstate it).
- **No match** (outside every configured area's radius, or the lookup
  service is unreachable): fall back to the contractor's flat
  `assumed_depth_ft`, confidence = `"low"` - byte-for-byte the original
  pre-pilot MVP behavior. This is the expected, common outcome outside
  pilot villages, not a degraded path.

The lookup **fails open**, unlike `job_client.fetch_job` (which fails
closed - a job must be provable to exist before quoting). A resource-
network outage must never block quotation generation; the flat-assumption
fallback is a fully correct MVP behavior on its own.

### What changed from the pre-pivot first pass (same session)

- `Resource.contractor_id` -> `owner_id`; `create/list/get/update
  resource` moved from `require_role("contractor")` to
  `require_role("resource_owner")`.
- `POST /v1/resources/match` moved from "your own resources" to "all
  owners' available resources," and its caller role stayed `contractor`
  (unchanged - it was always meant to be the contractor's tool, just
  scoped wrong).
- Added `BookingRequest` model + `/v1/bookings`,
  `/v1/bookings/{id}/accept`, `/v1/bookings/{id}/reject` - none of this
  existed in the first pass; a contractor finding a resource had no way
  to actually engage the owner.
- Test suites (`test_resources.py`, `test_matching.py`) rewritten, not
  patched - the access-control model the old tests encoded is no longer
  correct (e.g. `test_resource_owner_cannot_create_resource_yet` is now
  backwards: a resource_owner is exactly who *can* create one).

## Consequences

- **Frontend work still owed:** `apps/web-app/src/dashboards/
  ResourceOwnerDashboard.jsx` is still the placeholder from Milestone 3 -
  registration/login already routes there (role selector + dashboard
  mapping were already wired), but the actual screens (list own
  resources, view/accept/reject incoming booking requests) are not yet
  built. `ContractorDashboard.jsx` also needs a new flow: enter customer
  address -> call `/v1/resources/match` -> pick a result -> `POST
  /v1/bookings` -> see request status. Not done as part of this ADR's
  backend pass; flagged as the immediate next task.
- **Access-control surface genuinely widened**, as flagged before this
  ADR was written: a contractor now sees another party's resource's exact
  `hourly_rate` and `vehicle_type` via `/v1/resources/match`. This is the
  client's explicit intent (a real marketplace needs price transparency
  to let a contractor choose), not an oversight - noting it here so it's
  a recorded decision, not a silent widening.
- **`docs/rfc/0001-microservices-architecture.md` and the four
  `Borewell_0X` docs are now stale** on this point specifically (single-
  contractor resource ownership, no matching/booking, no location
  intelligence) - this ADR is the source of truth where it conflicts with
  those documents, per the same precedent as ADR-0002/0003. Full doc
  retrofit not done in this pass (explicitly deferred per the client),
  but should happen before this goes to a 4-person team, per
  STRUCTURE.md's own reasoning for why ADRs exist.
- **No payment/commission model decided yet** for how a resource owner
  gets paid via the platform (vs. the contractor paying the owner
  directly, outside the app, same as today's manual coordination). Out of
  scope for this ADR - `payments-data` still only handles
  customer-to-platform payment, not any owner payout. Flagging so it's
  not assumed solved.
