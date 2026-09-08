# Production Deployment Runbook

**Scope:** single-VM deployment, per `Borewell_03_Architecture.md` section 10
and the Development Plan's Milestone 5. This is deliberately the simplest
thing that actually works for a single-contractor pilot - no Kubernetes, no
managed orchestration, no blue-green deploy. Those get justified once there's
real multi-contractor load (Architecture doc section 12), not before.

If you're looking for local development instead, see the main `README.md` -
this document is for the pilot VM only.

---

## 1. What you're deploying

The same 4 backend services + frontend that run locally via `docker-compose.yml`,
promoted to a single cloud VM via `docker-compose.prod.yml`. Same containers,
same images, same code - the only things that change between dev and prod are
secrets, exposed ports, and the frontend's build (static/nginx instead of a
dev server). See `docker-compose.prod.yml`'s header comment for the itemized
diff against the dev file.

## 2. Prerequisites

- A VM (or equivalent) with Docker + Docker Compose v2 installed. Any
  mainstream Linux distro works; nothing here is distro-specific.
- Minimum realistic sizing for a pilot: 2 vCPU / 4GB RAM. This runs 4
  Postgres instances, Redis, 4 FastAPI services, and an nginx-served
  frontend - not heavy individually, but real headroom matters more than
  the absolute minimum that technically boots.
- A domain name pointed at the VM's IP, OR just the VM's public IP as an
  interim step (see `.env.prod.example`'s `PUBLIC_URL` comment - HTTPS is
  step 7 below, not required to get a first deploy running).
- Port 80 (and 443 once TLS is set up) reachable from the internet; ports
  8001-8004 reachable at minimum from wherever the frontend's browser
  traffic originates (see the CORS/URL note in step 4 below).

## 3. First-time server setup

```bash
# On the VM:
git clone <your-repo-url> borewell-platform
cd borewell-platform
git checkout main   # or whichever branch/tag you're deploying
```

No build tooling needs installing on the VM beyond Docker - every service's
`Dockerfile` handles its own dependencies inside the build.

## 4. Configure secrets and URLs

```bash
cp .env.prod.example .env.prod
```

Edit `.env.prod` and fill in every `CHANGE_ME`. The file itself documents
exactly how to generate each value (`openssl rand -base64 ...`) and why each
one exists - read it, don't skip past the comments.

**The one thing worth getting right the first time:** `PUBLIC_URL` and
`ALLOWED_ORIGINS` must both reflect where this VM is actually reachable at -
not `localhost`. If you deploy with the wrong value here, the symptom is
confusing: the frontend loads, but every API call from the browser fails
with a CORS error or connects to nothing, because the frontend's JavaScript
was built with the wrong backend URLs baked in (Vite bakes `VITE_*_URL` at
*build* time, not read at container start - see
`apps/web-app/Dockerfile`'s comment). If you get this wrong, you must
rebuild the `web-app` image (`docker compose -f docker-compose.prod.yml
--env-file .env.prod up -d --build web-app`), not just restart it.

## 5. Bring the stack up

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

This builds all 5 images (4 backend + frontend) and starts everything.
First run will take a few minutes (Postgres image pulls, Python/Node
dependency installs inside each build). Subsequent deploys are faster -
Docker layer caching means only what actually changed gets rebuilt.

**Migrations run automatically.** Every backend service's `Dockerfile`
runs `alembic upgrade head` as part of its container's startup command,
before the API server starts (see any `services/*/Dockerfile` - this was
a deliberate MVP decision, not an oversight: "if this fails, the
container fails to start rather than serving against a stale/missing
schema"). You do not need a separate migration step for a fresh deploy.

## 6. Verify

```bash
curl http://<your-domain-or-ip>:8001/healthz   # platform-spine
curl http://<your-domain-or-ip>:8002/healthz   # quotation
curl http://<your-domain-or-ip>:8003/healthz   # resource-network
curl http://<your-domain-or-ip>:8004/healthz   # payments-data
curl http://<your-domain-or-ip>/               # web-app (should return the HTML shell)
```

All 4 backend `/healthz` checks return `{"status": "ok"}` immediately -
they don't touch the database. `/readyz` on each service does check DB
connectivity (`SELECT 1`) if you want a stricter check:

```bash
curl http://<your-domain-or-ip>:8001/readyz
```

Then do one real, manual walkthrough: register a customer, register a
contractor, register a resource_owner, and run through create job ->
list a resource -> nearby-search -> booking request -> accept ->
generate quotation -> approve -> create payment. This is the same
manual pass the Development Plan's Milestone 4 already calls for
("catches UX friction automated tests don't detect") - a fresh
deployment is exactly when it's worth re-running once, not just trusting
the health checks.

## 7. HTTPS (do this before real customer data touches this VM)

Not automated here - deliberately, since certificate/domain setup is
specific to your registrar and hosting provider. The standard, low-effort
approach for a single VM: [Caddy](https://caddyserver.com/) or
`certbot` + nginx in front of the `web-app` container, terminating TLS
and reverse-proxying to port 80. Once that's in place:
- Update `PUBLIC_URL` in `.env.prod` to the `https://` URL.
- Rebuild `web-app` (see the note in step 4 - build-time env, not runtime).
- Consider also fronting ports 8001-8004 the same way, rather than
  leaving raw HTTP API ports exposed once a proper reverse proxy exists -
  this is the natural point where `infra/gateway/` (currently a
  documented placeholder - see `apps/AGENTS.md` and
  `apps/shared-ui/src/platform.js`'s "KNOWN DEVIATION" comment) stops
  being deferred and becomes worth actually building.

## 8. Redeploying (after a code change)

```bash
cd borewell-platform
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

`--build` only rebuilds images whose inputs actually changed (Docker
layer caching) - this is safe to run on every deploy, not just when you
know something changed.

## 9. Rollback

Per Architecture doc section 6 (Deployment Plan): "Rollback for the pilot
is simply redeploying the previous image tag; anything more elaborate
would be solving a problem that doesn't exist yet at this scale."

```bash
git checkout <previous-commit-or-tag>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

There is no blue-green or canary mechanism here on purpose - a few
seconds of downtime during a redeploy is an acceptable tradeoff at this
scale, and building around avoiding it would be exactly the kind of
premature complexity Architecture doc section 12 warns against.

**One real caveat on rollback:** if the redeploy you're rolling back
*added* a database migration, rolling back the code does not roll back
the schema - Alembic migrations only run forward
(`alembic upgrade head`) automatically. If a rollback needs the schema
to go backward too, that's a manual `alembic downgrade` run inside the
affected service's container, and should only be done with a real
understanding of what data that migration's `downgrade()` will touch -
check the specific migration file in `services/<name>/alembic/versions/`
before running it against real data.

## 10. Logs & basic troubleshooting

Per Architecture doc section 11 (MVP scope - no dashboards/tracing yet,
deliberately deferred to RFC 0001 section 7 Sprint 9+):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f                # everything
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f platform-spine # one service
```

Every service logs structured JSON to stdout - this is sufficient to
know if something is broken at pilot scale, per that same section.

## 11. What this runbook deliberately does not cover

- **Payment gateway (Razorpay) integration** - not built yet
  (`payments-data`'s `confirm`/`fail` endpoints are still admin-only
  placeholders). `.env.prod.example` has reserved-but-commented lines for
  when this lands.
- **Automated backups** for the 4 Postgres volumes - a real, separate
  operational decision (frequency, retention, off-VM storage) that
  deserves its own consideration once there's real pilot data worth
  losing, not a default assumed into this runbook.
- **Zero-downtime deploys, managed orchestration, multi-VM** - explicitly
  deferred per Architecture doc section 10/12, same reasoning repeated
  throughout this document: don't solve a scale problem that doesn't
  exist yet.
