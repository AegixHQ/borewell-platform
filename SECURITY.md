# Security

Audit round 2, October 2026. Round 1 (admin self-registration, auth rate
limits, non-root containers, webhook replay window, unhandled-error logging)
is in the previous commit; this file covers everything since, and what is
**deliberately not fixed** - read that part before going public.

## Fixed in this round

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | High | `approve`/`reject` set `status` on any quotation row without checking it was the **latest version** or what state it was in. A customer could approve an old, cheaper version after the contractor revised the price (and then pay it), or flip an approved quotation to rejected after paying. SRS section 8 / BR-06 required this to be refused. | Older versions read as `superseded` (derived, so versioning stays append-only) and cannot be approved, rejected, or paid. Approved is binding; same-decision replays are idempotent. |
| 2 | High | Anyone could self-register as `contractor` and then list **every customer's jobs and payments** (the data model is single-contractor). | `ALLOW_PUBLIC_CONTRACTOR_REGISTRATION=0` closes it - **default closed in `docker-compose.prod.yml`**. Operators create contractors with `python -m app.bootstrap create-user` (prompts for the password). |
| 3 | Medium | A replayed idempotency key returned the stored payment to **whoever sent it**, even another customer, or for a different quotation/amount. | Replay only for the same customer and same request; otherwise 409. Key length capped at 128. |
| 4 | Medium | A fresh idempotency key could open a **second charge** for an already-paid or in-checkout quotation; a double-tap sends two such requests at once. | One live payment per quotation: paid -> 409 `ALREADY_PAID`; pending -> that payment is returned. A Postgres advisory lock serialises concurrent creates. Measured on real Postgres, 20 simultaneous requests: **16 payment rows before, 1 after.** |
| 5 | Medium | Passwords over 72 bytes made bcrypt 5 raise: an unauthenticated 500 (plus traceback log spam) on register and login. | Rejected at registration (422, counted in bytes); login returns a normal 401. |
| 6 | Medium | Login skipped bcrypt for unknown emails (~1 ms vs ~280 ms), revealing which emails have accounts. | One bcrypt check is always spent; unknown email and wrong password are indistinguishable. |
| 7 | Medium | Native app: with no backend URL configured it silently ran the **demo backend** (any email, no password, fake payments) - including in a store build. Release builds also accepted `http://`. | Release builds never fall into demo mode, require all four URLs and `https://` (`EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1` opts a LAN test build out). Throws at startup. |
| 8 | Low-Med | `GET /v1/service-areas` was unauthenticated while `/lookup` beside it required a login. | Any authenticated role. |
| 9 | Low-Med | No request-body cap; phone, labels, notes, names, `line_items` unbounded (a 10-digit phone followed by 1 MB of spaces passed validation). | 1 MiB body cap (413; `MAX_REQUEST_BODY_BYTES`), bounded text fields, `line_items` <= 50. |
| 10 | Low | `/metrics`, `/docs`, `/openapi.json` readable by anyone on every service. | Docs off in prod (`ENABLE_API_DOCS=0`). Optional `METRICS_TOKEN`. `SERVICE_BIND_ADDR=127.0.0.1` closes the direct ports. |
| 11 | Low | JWT decode did not require `exp`/`sub`/`role`. | All three required in every service. |
| 12 | Low | Dev compose published Postgres and Redis on all interfaces with default credentials. | Bound to `127.0.0.1`. |
| 13 | Low | CI: default token permissions, no dependency monitoring, no security scan. | `permissions: contents: read` on every workflow, Dependabot, weekly `ci-security.yml` (bandit, pip-audit, npm audit). |

Checked and clean: no committed secrets in git history; `pip-audit` and
`bandit` (medium+) clean; every route's auth requirement and ownership check
reviewed (customer data scoped to its owner on jobs, quotations, payments);
HS256 pinned; bcrypt; no raw SQL; CORS credentials off.

## Known and deliberately NOT fixed

1. **TLS is opt-in, not on by default.** `docker-compose.tls.yml` adds Let's
   Encrypt HTTPS, an HTTP->HTTPS redirect and security headers. The flags were
   checked against the real Traefik 3.1.7 binary (redirect and headers confirmed),
   but the compose merge and the live certificate issuance have not been run -
   do the staging-CA run described in `docs/deployment/PRODUCTION.md` first.
   Until you use the overlay, passwords and tokens cross the network in clear.
   **Do not let a real customer on before it is on.**
2. **A contractor still sees all customers' data.** Closing sign-up (#2) limits
   *who* can be one; it is not tenancy. Before a second contractor exists, jobs
   and payments need a `contractor_id` scope on every read.
3. **Traefik mounts `/var/run/docker.sock`.** A compromise of the gateway is a
   compromise of the host. Put a socket proxy in front, or switch to the file
   provider. Not changed: it needs testing against a live Docker host.
4. **Redis has no password** (internal network only). Any container that can
   reach it can forge `payment.completed`. Low while all services are trusted,
   since they already share one `JWT_SECRET`.
5. **Rate-limit counters are per process** (and the keying rules in
   `docs/deployment/PRODUCTION.md` apply). Move to Redis before running more
   than one `platform-spine` container.
6. **No token revocation or refresh**; a token lives for `JWT_EXPIRY_MINUTES`
   (default 60) whatever happens to the account.
7. **Registration reveals whether an email exists** (409). Accepted; it is
   rate limited. Fixing it properly needs email verification.
8. **Python dependencies are unpinned ranges with no lockfile**, so each image
   build takes whatever is newest. Dependabot (above) tells you about
   problems; a lockfile would make builds reproducible.
9. **Native app dev-tooling advisories** (11, all in Expo's build-time config
   plugins; npm's "fix" is a downgrade to Expo 46). None ships in the app. The
   CI job fails on critical.

## Operator checklist for the pilot

- [ ] TLS on: `docker-compose.tls.yml`, staging-CA run first (item 1 above)
- [ ] `.env.prod`: strong `JWT_SECRET`, `BOOTSTRAP_ADMIN_*` set once then **removed**
- [ ] Pilot contractor created via `create-user`; `ALLOW_PUBLIC_CONTRACTOR_REGISTRATION` stays `0`
- [ ] If clients go through Traefik only: `SERVICE_BIND_ADDR=127.0.0.1` **and** `RATE_LIMIT_TRUST_FORWARDED_FOR=1`
- [ ] Razorpay live keys only after test-mode end-to-end passes
- [ ] Release app built with EAS `production` profile (https URLs, `EXPO_PUBLIC_DEMO=0`)
