# ADR-0001: Add a `tools/` top-level folder for developer tooling

**Status:** Proposed — needs sign-off from all 4 service owners per
STRUCTURE.md before this is Accepted
**Date:** August 11, 2026
**Owners involved:** Shrey Kumar (proposing) — Dev B, Dev C, Dev D sign-off
pending

## Context
Adding AI-agent guardrails surfaced a need for a contract-conformance
checker (`tools/contract-check/`) — a script that compares each service's
actual routes against its committed OpenAPI spec. It's cross-cutting (used
by all 4 services' CI) and isn't implementation code for any one service,
so it doesn't fit `services/`. It isn't config-only, so `infra/` doesn't fit
either (STRUCTURE.md is explicit that `infra/` excludes business/
implementation logic). `packages/contracts/` is explicitly schemas-only,
not implementation code.

## Decision
Propose a 6th top-level folder, `tools/`, for cross-cutting developer
tooling that isn't a service, an app, a contract, or infra config. First
occupant: `tools/contract-check/`.

## Consequences
- If accepted, `STRUCTURE.md`'s top-level folder table needs one row added
  for `tools/`, and this ADR becomes the historical record of why.
- This is genuinely additive — no existing folder is renamed or
  restructured to accommodate it.
- Until accepted by all 4 owners, treat `tools/` as provisional. Don't build
  a second unrelated thing into it before this ADR is ratified — that would
  be exactly the kind of quiet scope creep this repo's structure policy
  exists to prevent.
