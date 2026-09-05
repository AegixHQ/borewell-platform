# Deprecated

Superseded by `apps/web-app` per `docs/adr/0002-single-unified-frontend-app.md`.

This folder is kept (not deleted) because it contains working reference
code - particularly `resource-owner-app`'s original login+role-gate
logic, which `web-app` generalizes rather than reimplements from scratch.

Do not build new features here. Build in `apps/web-app` instead.
