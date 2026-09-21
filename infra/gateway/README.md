# Gateway

Single entry point for the backend, in front of all 4 services. Routes
requests to the correct service and validates JWTs issued by
`platform-spine` before forwarding. See RFC 0001 §5 for the reasoning.

**This is now real, not a placeholder** - implemented as a Traefik service
in `docker-compose.prod.yml`, with routing rules defined via Docker
labels on each backend service (not the `traefik.yml` file in this
folder - see below). Verified against a real running Traefik instance;
see `docs/BACKEND_INTEGRATION.md` section 2 for the routing table and
`docker-compose.prod.yml`'s `gateway` service + each backend service's
`labels:` block for the actual implementation.

`traefik.yml` in this folder is the original placeholder config, now
**unused and historically inaccurate** (it routes `/platform-spine/*`
etc., which never matched any real endpoint - the actual services use
`/v1/auth`, `/v1/jobs`, `/v1/quotations`, and so on). Kept only so the
git history of this decision stays visible; do not use it as a reference
for the real routing rules - use `docker-compose.prod.yml`'s labels or
`docs/BACKEND_INTEGRATION.md` instead.
