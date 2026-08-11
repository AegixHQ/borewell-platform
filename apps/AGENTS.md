# AGENTS.md — frontend apps

Applies to `contractor-app`, `resource-owner-app`, `customer-app`, `shared-ui`.

- Never call a service directly — always through the gateway
  (`infra/gateway/`), so auth and routing stay centralized.
- Any API call from these apps must match a path that actually exists in
  `packages/contracts/openapi/*.yaml`. If a field or endpoint isn't there,
  it doesn't exist yet — don't build UI against an assumed shape.
- `shared-ui` is the only place for cross-app components. If you're about
  to copy a component into two apps' `src/`, put it in `shared-ui` instead.
