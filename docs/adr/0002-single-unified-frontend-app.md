# ADR-0002: Consolidate 3 frontend apps into 1 unified app

**Status:** Accepted (product owner directive)
**Date:** 2026-09-05
**Owners involved:** Shrey Kumar (directed) — supersedes prior architecture
decision without further sign-off since it's an explicit product decision,
not an engineering tradeoff being proposed for review.

## Context

RFC 0001 §3 and the Architecture doc established three separate
deployable frontend apps (`contractor-app`, `customer-app`,
`resource-owner-app`), each a thin client over the shared backend, with
`apps/shared-ui` solving cross-app code duplication. This was pushed for
explicitly in this repo's history, including a direct pushback on a
request to build "one frontend that conditionally renders by role"
instead.

The product owner has now directed the opposite: **one single app**, with
one login/register flow. The user selects their role at registration; on
login, the role is returned by the backend automatically (not re-entered),
and the app renders the correct dashboard view based on that role.

## Decision

- Collapse `contractor-app`, `customer-app`, `resource-owner-app` into a
  single app: `apps/web-app`.
- Register screen: email, password, phone (optional), and an explicit role
  selector (customer / contractor / resource_owner). Calls platform-spine's
  real `POST /v1/auth/register`.
- Login screen: email, password only. Role is never asked for at login -
  it comes back in platform-spine's real `POST /v1/auth/login` response
  and is decoded from the JWT for routing.
- Post-login: a single router within `web-app` renders the correct
  dashboard component (`CustomerDashboard`, `ContractorDashboard`,
  `ResourceOwnerDashboard`) based on the decoded role. All three are
  React components in the same bundle, not separate deployable apps.
- The 3 old app folders are marked deprecated (README + package.json
  `"private": true` retained, removed from default `make`/CI targets) but
  not deleted outright, so the working `resource-owner-app` login logic
  that predates this ADR isn't destroyed - `apps/web-app` is built by
  generalizing that same pattern, not by starting over.
- `apps/shared-ui`'s `login()` / `decodeJwtPayload()` helpers are reused
  as-is; they were never role-specific to begin with.

## Consequences

- Real security enforcement doesn't change at all: it was always server-
  side (`require_role()` in each service), never the frontend's job. This
  ADR is purely a client presentation-layer decision.
- `apps/AGENTS.md` needs updating: its "never call services directly"
  and "shared-ui is the only shared code" rules still hold; its framing
  of "3 apps" needs to become "1 app, N role-based views."
- Anyone picking up frontend work should build inside `apps/web-app` going
  forward, not the 3 deprecated folders.
- If a future need arises to re-split (e.g. a role's UI diverges enough
  that shipping it as part of one bundle becomes awkward), that reversal
  would itself need its own ADR - this is not assumed to be final for all
  time, just the current direction.
