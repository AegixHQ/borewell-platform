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

The 4 backend services that run locally via `docker-compose.yml`, promoted
to a single cloud VM via `docker-compose.prod.yml`, plus a gateway
(Traefik) that didn't exist in earlier versions of this file - see
`docker-compose.prod.yml`'s header comment for the itemized diff against
the dev file. **This repo no longer builds or deploys a frontend** - the
real mobile + desktop frontend now lives in a separate repository and is
integrated against these 4 services over HTTP (see
`docs/BACKEND_INTEGRATION.md`, written for exactly that integration).
`apps/web-app` still exists in this repo as a working reference client,
but `docker-compose.prod.yml` does not build or run it - if you need it
running for some reason (demoing the reference implementation, say),
that's `docker-compose.yml` (dev), not this file.

## 2. Prerequisites

- A VM (or equivalent) with Docker + Docker Compose v2 installed. Any
  mainstream Linux distro works; nothing here is distro-specific.
- Minimum realistic sizing for a pilot: 2 vCPU / 4GB RAM. This runs 4
  Postgres instances, Redis, 4 FastAPI services, and the Traefik gateway -
  not heavy individually, but real headroom matters more than the
  absolute minimum that technically boots.
- A domain name pointed at the VM's IP, OR just the VM's public IP as an
  interim step (see `.env.prod.example`'s `PUBLIC_URL` comment - HTTPS is
  step 7 below, not required to get a first deploy running).
- Port 80 (and 443 once TLS is set up, step 7) reachable from the
  internet - this is the gateway's port, and per
  `docs/BACKEND_INTEGRATION.md` section 2, the one base URL whoever's
  building the separate frontend repo should be pointed at. Ports
  8001-8004 (the 4 services directly) also need to be reachable from
  wherever that frontend's traffic originates, since the gateway doesn't
  replace direct access, it supplements it (see that same doc section for
  why both exist).

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
`ALLOWED_ORIGINS` must both reflect where this VM is actually reachable at
- not `localhost`. `ALLOWED_ORIGINS` needs the real deployed origin of
whatever frontend is calling this backend from a browser context (the
separate frontend repo's deployed URL - native mobile isn't affected by
CORS at all, see `docs/BACKEND_INTEGRATION.md` section 5). Get this wrong
and the symptom is confusing from the frontend side: requests either get
a CORS error in the browser console or fail to connect, while this
backend's own logs and health checks look completely fine - because
CORS is enforced by the browser, not visible here at all. Unlike an
earlier version of this stack, there's no frontend build in this repo to
rebuild when this changes - `ALLOWED_ORIGINS` is read from the
environment at container start (not baked in at build time anywhere in
this repo anymore), so `docker compose -f docker-compose.prod.yml
--env-file .env.prod up -d` (no `--build` needed) is enough after editing
it.

### Razorpay setup (one-time, in the Razorpay Dashboard)

Do this **after** step 5 (the stack is up and `PUBLIC_URL` is actually
reachable), not before - registering a webhook URL against an address
that isn't serving traffic yet just means re-doing this step.

1. `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`: Dashboard → Settings → API
   Keys. Generate a **live** mode key pair for a real deployment, not a
   test-mode one - the two look similar (`rzp_live_...` vs
   `rzp_test_...`), so check the prefix before pasting into `.env.prod`.
2. Bring the stack up (step 5) so `<PUBLIC_URL>:8004` is reachable.
3. Dashboard → Settings → Webhooks → Add New Webhook. URL:
   `http://<PUBLIC_URL>:8004/v1/payments/webhook` (or through a reverse
   proxy once one exists - see step 7). Enable the `payment.captured` and
   `payment.failed` events at minimum - other events are safely ignored
   by the endpoint (see `services/payments-data/app/main.py`'s
   `razorpay_webhook` handler), so enabling more than these two is
   harmless, just unused.
4. Razorpay shows the webhook secret **once**, at creation time - copy it
   into `.env.prod`'s `RAZORPAY_WEBHOOK_SECRET` immediately. It cannot be
   retrieved again later from their dashboard; losing it means deleting
   and recreating the webhook.
5. Restart `payments-data` to pick up the new env vars:
   `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d payments-data`
   (no `--build` needed - only the environment changed, not the image).
6. Verify with a real test payment before considering this done - see
   step 6 below.

**Read before trusting any of the above against a real payment:** the
integration (`services/payments-data/app/gateway/razorpay_client.py`)
was built without live access to Razorpay's current documentation - it
follows their long-stable Orders API and webhook signature scheme, but
this should be checked against https://razorpay.com/docs/ once, by
someone with real dashboard access, before this handles real customer
money. See that file's own docstring for the same caveat in more detail.

## 5. Bring the stack up

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

This builds the 4 backend images (Traefik's image is pulled, not built -
it's the stock upstream image, no Dockerfile of its own in this repo) and
starts everything, including the gateway.
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
curl http://<your-domain-or-ip>/v1/jobs        # through the gateway - expect
                                                # a 401 (no token), not a
                                                # connection failure or 404;
                                                # a 401 means the gateway
                                                # correctly routed the
                                                # request to platform-spine,
                                                # which then correctly
                                                # rejected it for having no
                                                # Authorization header - that
                                                # IS the gateway working
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
generate quotation -> approve -> create payment -> create-order ->
**complete a real payment through Razorpay Checkout** -> confirm the
webhook actually landed (payment status shows `completed`, not stuck at
`pending`). This is the same manual pass the Development Plan's
Milestone 4 already calls for ("catches UX friction automated tests
don't detect") - a fresh deployment is exactly when it's worth
re-running once, not just trusting the health checks. Use a small real
amount for this first pilot check, or Razorpay's test mode
(`rzp_test_...` keys) if you want to verify the deploy without moving
real money yet - just remember to switch back to live keys in
`.env.prod` before a real customer uses this.

If the payment gets stuck at `pending` after a successful-looking
Razorpay checkout, check `docker compose -f docker-compose.prod.yml
--env-file .env.prod logs -f payments-data` for a webhook-related error
first - the most common causes are `RAZORPAY_WEBHOOK_SECRET` not matching
what's configured in the Razorpay dashboard (a stale/regenerated secret),
or the webhook URL registered in the dashboard not actually being
reachable from Razorpay's servers (check firewall/security group rules
for port 8004, or whatever port a reverse proxy in front of it uses).

## 7. HTTPS (do this before real customer data touches this VM)

Not automated here - deliberately, since certificate/domain setup is
specific to your registrar and hosting provider. The gateway
(`docker-compose.prod.yml`'s `gateway` service, Traefik) is where this
belongs once you're ready - Traefik has built-in ACME/Let's Encrypt
support, so this is a config addition to the existing `gateway` service
(a `certificatesResolvers` block plus a `websecure` entrypoint on 443),
not a new piece of infrastructure. The alternative - fronting the whole
VM with a CDN/proxy like Cloudflare that terminates TLS before traffic
reaches port 80 - also works and requires no gateway config changes at
all, just a DNS/proxy setup outside this repo. `docs/BACKEND_INTEGRATION.md`
section 7 has the same two options from the frontend-integrator's side,
if you need to coordinate this with whoever's building the separate
frontend repo. Once either is in place:
- Update `PUBLIC_URL` in `.env.prod` to the `https://` URL - this is read
  at container start by whichever services use it (see
  `.env.prod.example`'s own comment on that var for exactly which ones),
  not baked into any build, so a restart (not a rebuild) picks it up.
- The 4 direct backend ports (8001-8004) stay HTTP-only unless you
  explicitly front each of them too - most setups only need the gateway's
  port TLS-terminated, since that's the one meant to be the actual public
  entry point (see `docs/BACKEND_INTEGRATION.md` section 2).

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

- **Razorpay account setup and business verification** - creating the
  Razorpay account itself, KYC/business verification, and settlement
  bank account configuration are Razorpay-side onboarding steps with
  their own timeline (can take a few business days for a new business
  account) - not something this runbook or the code can do for you.
  Section 4's "Razorpay setup" subsection covers what happens once that
  account exists and has live API access.
- **Split payouts to resource owners** - the current integration handles
  customer-to-platform payment only (`payments-data` collects payment
  for a job; nothing routes any portion of it onward to a resource_owner
  automatically). `docs/adr/0004`'s "Consequences" section flags this as
  a real, undecided gap in the marketplace model, not an oversight here.
- **Automated backups** for the 4 Postgres volumes - a real, separate
  operational decision (frequency, retention, off-VM storage) that
  deserves its own consideration once there's real pilot data worth
  losing, not a default assumed into this runbook.
- **Zero-downtime deploys, managed orchestration, multi-VM** - explicitly
  deferred per Architecture doc section 10/12, same reasoning repeated
  throughout this document: don't solve a scale problem that doesn't
  exist yet.

---

## Security hardening notes

**Creating the first admin.** `POST /v1/auth/register` accepts `customer`,
`contractor` and `resource_owner` only - it cannot create an admin. Set
`BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` in `.env.prod`, restart
`platform-spine`, then **delete the password line**. It is create-only: an
existing account is never modified or promoted. Manual alternative:
`docker compose -f docker-compose.prod.yml exec platform-spine python -m app.bootstrap`.

**Auth rate limits.** Login is limited to 10/minute and registration to
10/hour per client IP (`RATE_LIMIT_LOGIN`, `RATE_LIMIT_REGISTER`). Counters
are in-process, so they are per replica - move to Redis before running more
than one `platform-spine` container. `RATE_LIMIT_TRUST_FORWARDED_FOR` must stay
`0` while ports 8001-8004 are reachable directly (a direct caller can forge
`X-Forwarded-For`). If you later route everything through Traefik and close
those ports, set it to `1`; with it left at `0` behind the gateway, all users
share Traefik's IP and therefore one shared limit.

**Containers run as an unprivileged user** (`borewell`, uid 10001), not root.

**Webhook replay window.** `POST /v1/payments/webhook` ignores (HTTP 200,
`ignored_stale`) events whose `created_at` is older than 25h
(`WEBHOOK_MAX_AGE_SECONDS`) or more than 5 minutes in the future. Razorpay
retries failed deliveries for 24h, so the window must stay above that. The real
replay protection is the status-based idempotency in the handler.

**Unhandled errors** are logged server-side as `request.failed` (with
traceback and `trace_id`) and returned to clients as
`{"error": {"code": "INTERNAL_ERROR", ...}}` with no internals.

**Contractor accounts.** Public sign-up for the `contractor` role is closed by
default (`ALLOW_PUBLIC_CONTRACTOR_REGISTRATION=0`) because a contractor can see
every customer's jobs and payments. Create the pilot contractor with
`docker compose -f docker-compose.prod.yml exec -it platform-spine python -m
app.bootstrap create-user --role contractor --email owner@example.com`
(prompts for the password; create-only - an existing account is never changed).

**Gateway-only mode.** Once every client goes through Traefik, set
`SERVICE_BIND_ADDR=127.0.0.1` (the service ports stop being reachable from
outside) and `RATE_LIMIT_TRUST_FORWARDED_FOR=1` (per-client rate limits behind
the gateway). Do both together: the second is only safe if the first holds.

**Optional `/metrics` token.** Set `METRICS_TOKEN` on a service to require
`Authorization: Bearer <token>`; give Prometheus the same value with
`authorization: { credentials_file: ... }` in `infra/monitoring/prometheus.yml`.
Unset, `/metrics` stays open (and reachable on the published ports).

See `SECURITY.md` for the full list of what was fixed and what remains.

**HTTPS (Let's Encrypt).** The base stack serves plain HTTP. For real users, add
the TLS overlay:

    docker compose -f docker-compose.prod.yml -f docker-compose.tls.yml \
      --env-file .env.prod up -d

Set `PUBLIC_DOMAIN` and `LETSENCRYPT_EMAIL` in `.env.prod` first, point the
domain's DNS A record at the VM, and keep ports 80 and 443 open (80 is used for
the certificate challenge and then redirects to HTTPS). Do a first run against
the staging CA (`LETSENCRYPT_CA_SERVER`, see `.env.prod.example`), then remove
that line, delete the `traefik_letsencrypt` volume, and start again for a real
certificate. Certificates renew automatically. Responses get HSTS (starts at one
day - raise `stsSeconds` in `infra/gateway/dynamic/tls-headers.yml` to a year
once HTTPS has worked for a few days), nosniff, frame-deny and no-referrer.
Then point the apps at `https://<PUBLIC_DOMAIN>` (EAS `production` profile) and
set `ALLOWED_ORIGINS` to the real web origin.
