# STRUCTURE.md — Skeleton Stability Policy

This is the single source of truth for how this repo's top-level structure works,
and the rule for how it is allowed to grow. The goal: new services, apps, or
capabilities are always **additive** — nothing here should ever require renaming
or moving what already exists.

## The five top-level folders

| Folder | Contains | Does NOT contain |
|---|---|---|
| `services/` | One folder per backend microservice | Frontend code, infra config |
| `apps/` | One folder per frontend application, plus `shared-ui` | Backend/business logic |
| `packages/contracts/` | OpenAPI specs and event schemas — the only integration surface between services | Implementation code |
| `infra/` | Gateway/deploy/local-dev configuration | Business logic |
| `docs/` | RFCs and ADRs — the historical record of every structural decision | Code |

## The rule that keeps this stable

Every service folder follows the exact same internal template:

```
services/<name>/
├── app/
├── tests/
├── alembic/
├── Dockerfile
└── pyproject.toml
```

A new service is a new folder following this template. Adding one is never a
reason to touch an existing service's folder.

Every frontend app follows the same principle: `apps/<name>/` with its own
`src/`, `package.json`. `shared-ui` is the only shared frontend code and lives
at `apps/shared-ui/`.

## What "never changes" actually means here

No repo skeleton can be literally permanent forever — a genuinely new category
of thing (e.g. a mobile client, a data warehouse) might eventually justify a
new top-level folder. What this policy guarantees is narrower, and it is
achievable:

1. **Existing folders are never renamed or moved** to accommodate something new.
2. **New capabilities are added as new folders** following the existing
   template, never by restructuring what's already there.
3. **Any exception to points 1–2 requires an ADR** in `docs/adr/` (see the
   template) and sign-off from all 4 service owners. It does not happen as a
   side effect of a feature PR.

## When you're tempted to break this

If a new feature doesn't fit cleanly into `services/` or `apps/`, that's a
signal to write an ADR and discuss it as a team decision — not to quietly
bend an existing folder's purpose to fit. Structural changes should be rare,
deliberate, and documented. This policy makes them expensive on purpose,
because the cost of an undocumented restructure (merge conflicts across all
4 devs' branches, broken CI paths, broken contract references) is much
higher than the cost of writing one ADR.
