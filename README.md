# Borewell Platform

Location-aware digital platform connecting borewell contractors, resource owners
(rigs/equipment/labour), and customers. See `docs/rfc/0001-microservices-architecture.md`
for the full architecture decision and `STRUCTURE.md` for how this repo is allowed to grow.

## Services

| Service | Owner | Port (local) |
|---|---|---|
| platform-spine | Dev A | 8001 |
| quotation | Dev B | 8002 |
| resource-network | Dev C | 8003 |
| payments-data | Dev D | 8004 |

## Quick start

```bash
make up      # builds and starts all services + databases + redis
make test    # runs each service's test suite
make down    # stops everything and removes volumes
```

Each service exposes `/healthz` and `/readyz` once running, e.g. `curl localhost:8001/healthz`.

## Before you touch the top-level structure

Read `STRUCTURE.md` first. New services/apps are added by following the existing
template folders, not by renaming or restructuring what's already here.

## Contracts

`packages/contracts/` is the source of truth for all inter-service communication —
OpenAPI specs for synchronous calls, JSON Schema for events. Change contracts there
first, in a reviewed PR, before changing service code that depends on them.
