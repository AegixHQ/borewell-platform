# Borewell Platform — Backend Integration Guide

**Audience:** the team building the real Customer/Contractor/Resource-Owner
frontend (mobile + desktop) in a separate repository, integrating against
this backend for the first time.

**Status of this document:** every shape below (request/response fields,
error format, role list, job status list) was read directly out of this
repo's source — `services/*/app/schemas.py`, `models.py`, `main.py` — not
recalled or guessed, and the gateway routing was verified against a real
running Traefik instance before this doc was written (see "Gateway" below).
If something here ever looks wrong against the live API, the code is the
source of truth, not this file — open an issue/PR to fix this doc rather
than silently working around the mismatch.

---

## 1. What's running, and where

Four backend services, each a standalone FastAPI app with its own database.
None of them serve any frontend — this repo's own frontend code
(`apps/web-app`, plus the dead scaffolds `apps/customer-app`,
`apps/contractor-app`, `apps/resource-owner-app`) is not what you're
integrating against architecturally; the real API surface is these 4
services, and `apps/web-app` is just one *client* of that same surface,
useful as a working reference implementation if you want to see a real
call site for any endpoint below.

| Service | Owns | Direct port (dev & prod) |
|---|---|---|
| `platform-spine` | Auth, job lifecycle | `8001` |
| `quotation` | Pricing rules, quotations | `8002` |
| `resource-network` | Resources, bookings, service areas | `8003` |
| `payments-data` | Payments, Razorpay integration | `8004` |

**In dev** (`docker-compose.yml`, `make up`), all 4 are reachable directly
at `http://localhost:800{1,2,3,4}`.

**In prod** (`docker-compose.prod.yml`), the same 4 ports are still exposed
directly on the VM — nothing about adding the gateway (below) removes
them — but there's also a single entry point.

---

## 2. Gateway — one base URL instead of four

`docker-compose.prod.yml` runs a Traefik gateway container on port `80`,
routing by path prefix to the correct backend service:

| Path prefix | Routed to |
|---|---|
| `/v1/auth`, `/v1/jobs` | `platform-spine` |
| `/v1/pricing-rules`, `/v1/quotations` | `quotation` |
| `/v1/resources`, `/v1/bookings`, `/v1/service-areas` | `resource-network` |
| `/v1/payments` (webhook included — see §6) | `payments-data` |

A request to any other path gets a real `404` from the gateway itself,
before it ever reaches a backend container.

**This means:** your frontend can treat the backend as **one base URL**
(`http://<vm-host>` in dev/staging, `https://<your-domain>` once TLS is
set up — see §7) and never needs to know which of the 4 services owns
which endpoint. Just call `{BASE_URL}/v1/jobs`, `{BASE_URL}/v1/payments`,
etc., and the gateway sends it to the right place.

**This routing was verified for real** — not just written and assumed
correct — using the actual Traefik v3.1.6 binary against the exact same
routing rules present in `docker-compose.prod.yml`'s Docker labels, with 4
stub servers standing in for the real services. Every path above was
confirmed to reach the correct backend, and an unmatched path was confirmed
to `404` at the gateway rather than falling through to any service.

**Mobile note:** if your mobile app can't easily switch base URLs between
"one gateway origin" and "raw multi-port," the gateway origin is the one
to use everywhere — it works identically for mobile and desktop/web,
unlike CORS (which only applies to browser clients — see §5).

---

## 3. Authentication

JWT-based, issued only by `platform-spine`, verified independently by all
4 services (no per-request callback between services — a network partition
affecting `platform-spine` doesn't take the other 3 down).

### Register

```
POST /v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "at-least-8-chars",
  "phone": "+919841234567",   // optional
  "role": "customer"           // optional, defaults to "customer"
}
```

Valid self-registration `role` values: `customer`, `contractor`, `resource_owner`.
`admin` is **rejected with `422`** — it is created out-of-band
(`BOOTSTRAP_ADMIN_*` env vars or `python -m app.bootstrap create-user`).
In production `contractor` is also closed by default
(`ALLOW_PUBLIC_CONTRACTOR_REGISTRATION=0`) and returns `403`; only build a
public contractor sign-up screen if the operator has enabled it. Passwords
must be 8–72 **bytes** (`422` otherwise).

**Response — `201`:**
```json
{ "access_token": "eyJ...", "role": "customer" }
```

**`409`** if the email is already registered (`{"error": {"code":
"EMAIL_TAKEN", ...}}` — see §4 for the full error shape).

### Login

```
POST /v1/auth/login
Content-Type: application/json

{ "email": "user@example.com", "password": "..." }
```

Same `201`-shaped response as register (`access_token`, `role`). Wrong
email and wrong password are indistinguishable (`401`).

**Rate limits:** login and register are limited per client IP (`429`
with a `Retry-After` header). Show a "try again in N seconds" message
rather than retrying in a loop.

### Using the token

Every other endpoint on every service requires:

```
Authorization: Bearer <access_token>
```

- Missing, malformed, or expired token (or one without `exp`/`sub`/`role`) → `401`.
- Token valid but wrong role for the endpoint → `403`.
- Default expiry: 60 minutes (`JWT_EXPIRY_MINUTES`, server-configured).
  **There is no refresh-token flow in this MVP** — when a token expires,
  the frontend needs to send the user back through login. Build your
  session handling around that now rather than assuming silent refresh
  exists; SRS §7 notes this is a deliberate "Phase 1 concern, not
  MVP-blocking," so it may change later, but don't build against a refresh
  endpoint that doesn't exist yet.
- The JWT payload carries `sub` (user id) and `role`. Nothing else — don't
  decode it client-side for user profile info (name, email); there isn't
  any in there.

---

## 4. Error format

Every error from every service follows the same shape:

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "Human-readable explanation.",
    "trace_id": "a-uuid"
  }
}
```

`trace_id` is also echoed back on every response (success or error) as the
`X-Trace-Id` header — useful to hand back to the backend team when
reporting an integration bug, since it lets them grep logs directly.

Validation errors (missing/malformed fields) come back as `422` with
`code: "VALIDATION_ERROR"` and FastAPI's own field-level detail in
`message`.

Status codes worth handling in a client:

| Status | `code` | Meaning |
|---|---|---|
| `409` | `QUOTATION_STATE_CONFLICT` | Quotation was superseded by a newer version, or already decided the other way. Refetch and show the latest. |
| `409` | `ALREADY_PAID` | That quotation already has a completed payment. |
| `409` | (idempotency) | The `Idempotency-Key` was already used for a different customer/request. Use a fresh key (max 128 chars). |
| `413` | — | Request body over 1 MiB. |
| `429` | — | Rate limited (login/register); honour `Retry-After`. |
| `500` | `INTERNAL_ERROR` | Unhandled error; report the `trace_id`. |

A quotation's `status` can also read `superseded` (a newer version exists).
Only the latest version can be approved, rejected or paid.

---

## 5. CORS (browser clients only — not mobile)

If your frontend includes a web/desktop build that runs in an actual
browser (Electron counts as a browser context for this), its origin needs
to be in the backend's `ALLOWED_ORIGINS` env var, or the browser will block
the requests with a CORS error before they even show up in this backend's
logs — that's a browser-enforced rule, invisible to the server.

`ALLOWED_ORIGINS` is a comma-separated list, set once and shared by all 4
services (each service's `docker-compose.prod.yml` block reads the same
`.env.prod` value). **Add your frontend's real deployed origin(s) to that
list** — `http://localhost:5173` (Vite's default) only covers local dev of
*this* repo's own scaffold apps, not your separate frontend repo's dev
server or its deployed URL. Coordinate with whoever holds `.env.prod` to
get your origin added before you start hitting CORS walls in a browser
build.

**Native mobile apps are not affected by this at all** — CORS is a
browser-only mechanism. If you're building React Native / Flutter / native
iOS-Android, skip this section entirely.

---

## 6. Payments — Razorpay, and what your frontend actually needs to know

The backend owns the entire Razorpay integration — order creation, webhook
verification, idempotency. Your frontend's job is narrower than it might
look:

1. `POST /v1/payments` with the approved quotation's total → creates a
   `pending` payment record. There is one live payment per quotation:
   calling it again while one is pending returns that payment; after it is
   paid you get `409 ALREADY_PAID`. Send an `Idempotency-Key` and reuse it
   on retries (double-taps are safe).
2. `POST /v1/payments/{payment_id}/create-order` → returns a Razorpay
   order, including `razorpay_key_id` (Razorpay's **public** key — this is
   meant to be seen by the client, unlike the secret). Reopening this
   endpoint for the same payment reuses the existing order rather than
   creating a duplicate.
3. Your frontend mounts Razorpay's Checkout SDK using that `key_id` and
   `order_id` — **your frontend never needs its own copy of any Razorpay
   key**, dev or prod. The backend hands you the right one dynamically
   based on whichever key it's configured with server-side.
4. Razorpay's webhook (not your frontend) is what actually confirms
   payment completion on the backend — your frontend doesn't need to call
   anything else to "finish" a payment; poll `GET /v1/jobs/{job_id}` (or
   `GET /v1/payments/{payment_id}`) to see the status update once the
   webhook lands, typically within seconds.

**Practical consequence for you:** switching this backend from Razorpay
test-mode to live-mode keys is a pure server-side env-var change with zero
frontend code changes required — your integration code doesn't hardcode or
branch on which mode is active, because it never sees the secret key at
all, only whatever public `key_id` the backend hands back in step 2.

---

## 7. TLS / HTTPS

The default gateway serves plain HTTP on port `80`. HTTPS is an **opt-in
overlay**, `docker-compose.tls.yml` (Let's Encrypt via Traefik, HTTP→HTTPS
redirect, HSTS, `nosniff`, frame-deny). It needs a real domain pointed at the
VM; see `docs/deployment/PRODUCTION.md` §7. Fronting the VM with a CDN/proxy
that terminates TLS (e.g. Cloudflare) is an equally valid alternative.

Until one of these is in place, treat any real (non-development) traffic as
**not safe for production credentials/payment data over the wire**. The native
app's release builds refuse `http://` URLs unless built with
`EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1` (the EAS `lan` profile).

---

## 8. Job lifecycle — the one state machine everything hangs off

```
lead → site_location → requirement → estimation → price_calculation →
quotation → customer_approval → booking → resource_allocation →
drilling → progress → completion → payment → service_history
```

- Statuses only move forward, one step at a time — skipping a stage is
  rejected by the backend (`400`), so don't build frontend logic that
  assumes you can jump a job straight to `completion`.
- Only the `contractor` role can advance a job's status directly
  (`PATCH /v1/jobs/{job_id}/status`) — customer actions like "approve
  quotation" trigger a transition as a side effect of a different
  endpoint, not by the customer calling this one directly.
- `GET /v1/jobs/{job_id}` works for the owning customer, the assigned
  contractor, or `admin` — a customer requesting someone else's job gets
  `403`, not `404` (so don't rely on `404` to mean "doesn't exist" from a
  customer token's perspective).

---

## 9. Pagination (optional, additive)

`GET /v1/jobs`, `GET /v1/resources`, and `GET /v1/bookings` accept optional
`?limit=N&offset=N` query params (`limit`: 1-200, `offset`: ≥0, both
optional). **Omit them and you get exactly what you got before this
existed** — the full list, unpaginated — so there's no obligation to use
this on day one. Reach for it once a real contractor's job history or a
real resource owner's booking queue gets large enough that fetching
everything on every screen load stops making sense; verified server-side
that pages don't overlap and every row is returned exactly once across
pages.

---

## 10. Where to look for anything not covered here

This doc covers the integration surface, not the full API reference. For
exact request/response shapes of a specific endpoint not detailed above:

- Each service's `packages/contracts/openapi/<service>.yaml` is the
  contract-first source of truth — written before implementation, checked
  in CI (`tools/contract-check/`), so it cannot silently drift from the
  real code.
- Each service also serves live interactive docs at `/docs` (Swagger UI)
  when running — `http://localhost:8001/docs`, etc. — generated directly
  from the same FastAPI app, so it's always in sync with what's actually
  deployed.
- `apps/web-app/src/` (specifically `apps/shared-ui/src/platform.js` for
  the API call helpers) is a real, working reference client if you want to
  see an existing integration for any specific flow — resource matching
  and booking requests in particular, since those involve a few chained
  calls that are easier to read as working code than to describe in prose.
