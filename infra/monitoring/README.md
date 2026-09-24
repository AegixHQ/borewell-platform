# Monitoring — Prometheus + Grafana

## What this is

Real metrics, not just logs. `infra/backup/` and the structured JSON
logging (`services/*/app/logging_config.py`) tell you *what happened* on
a specific request; this tells you *the shape of things over time* —
request rate, error rate, latency — the kind of thing you actually want
on a dashboard rather than grepped out of logs by hand.

**Verified before being added to this repo**, not just written and
assumed correct:
- `infra/monitoring/prometheus.yml` checked with the real `promtool`
  binary (`promtool check config` — Prometheus's own validator).
- The full pipeline — a real FastAPI service exposing `/metrics`, a real
  Prometheus scraping it, a real PromQL query against Prometheus's own
  API — run end-to-end in this environment: `up{job="..."}` came back
  `1`, and `http_requests_total` showed the exact real requests made
  during the test, correctly labeled.
- The exact metric label format (`status="2xx"`/`"4xx"`, bucketed —
  not literal status codes) was confirmed by reading real `/metrics`
  output before the dashboard's PromQL queries were written against it,
  not guessed from the library's docs.

What was **not** tested against the real multi-container stack: Grafana
itself rendering the dashboard with real data (no Docker daemon in the
environment this was built in — same limitation noted for the gateway
work in `docs/deployment/PRODUCTION.md`). The dashboard JSON is valid
JSON, uses Grafana's standard schema version, and its queries are proven
correct against the real metric format above — but actually opening
Grafana and seeing the panels populate is the one step still owed on
your real VM.

## What each service does

| Service | Role |
|---|---|
| `platform-spine`, `quotation`, `resource-network`, `payments-data` | Each exposes `GET /metrics` (Prometheus exposition format) — added via `prometheus-fastapi-instrumentator`, request count/latency/status broken down per endpoint |
| `prometheus` | Scrapes all 4 `/metrics` endpoints every 15s, stores the time series |
| `grafana` | Queries Prometheus, renders the dashboard |

`/metrics` is deliberately excluded from each service's OpenAPI contract
(`include_in_schema=False` in the code, plus an entry in
`tools/contract-check/check_contract.py`'s `IGNORED_PATHS`) — it's
operational surface scraped from inside the Docker network, not a
business endpoint any frontend calls.

## First-time setup

1. Set `GRAFANA_ADMIN_PASSWORD` in `.env.prod` (see `.env.prod.example`).
2. Bring the stack up as usual — `prometheus` and `grafana` start
   alongside the 4 backend services:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```
3. Open `http://<your-domain-or-ip>:3000`, log in as `admin` with the
   password from step 1.
4. The "Borewell Platform — Backend Overview" dashboard should already
   be there — provisioned automatically on first boot
   (`infra/monitoring/grafana/provisioning/`), not something to build by
   hand in the UI.

## The starter dashboard

`infra/monitoring/grafana/dashboards/borewell-overview.json` — 5 panels:

- **Service up/down** — is each of the 4 services actually reachable by
  Prometheus right now
- **Request rate by service** — requests/second, per service
- **Error rate — 5xx responses** — the one panel worth an alert on (see
  below); a real bug in your own code, not a customer's 401 or 404
- **p95 request latency by service** — is something getting slow before
  it breaks outright
- **Requests by status class** — 2xx/4xx/5xx breakdown across all 4
  services combined

This is a deliberately small starting point, not a finished operations
dashboard — add panels as you learn what you actually want to watch
(e.g. `payments-data`'s Razorpay-specific error codes, once you've been
running long enough to know which ones matter in practice). Edit the
JSON file directly and restart Grafana (or wait ~30s — see
`grafana/provisioning/dashboards/dashboards.yml`'s
`updateIntervalSeconds`), or edit in Grafana's UI and export back to
this file to keep it version-controlled rather than living only in
Grafana's own database.

## Alerting — not set up yet, and here's the honest gap

Grafana can send alerts (Slack, email, a webhook) when a query crosses a
threshold — e.g. 5xx rate above zero for 5 minutes. **This is not
configured** in what's here; the dashboard shows you the data, but
nothing pages you automatically yet. Worth doing once you've picked
where alerts should actually go (see the "Costs & time" section this
accompanies for what a Slack/email alert costs — usually nothing extra
on top of what's already free-tier). Grafana's own alerting UI
(Alerting → Alert rules, built into the version pinned here) is the
place to add this when ready; it can query the same Prometheus
datasource already provisioned, no new infrastructure needed.

## Resource footprint

Both containers are lightweight at this data scale (4 services, 15s
scrape interval, a single-contractor pilot's real request volume) —
Prometheus and Grafana together add meaningfully less load than any one
of the 4 Postgres instances already running. Not something to worry
about at this scale; revisit only if this VM's overall resource usage
becomes a real constraint, same "not needed yet" posture as
Architecture doc section 12 takes toward Kubernetes.
