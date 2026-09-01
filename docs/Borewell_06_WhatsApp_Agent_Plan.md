# Borewell Platform — WhatsApp Agent Build Plan

**Project:** Borewell Platform
**Component:** `whatsapp-agent` (new service — addendum to `Borewell_05_Development_Plan.md`)
**Depends on:** `Borewell_02_SRS.md`, `Borewell_03_Architecture.md`, `Borewell_04_UIUX.md`, `Borewell_05_Development_Plan.md`
**Date:** August 29, 2026

---

## 0. Scope, Stated Plainly

This plan assumes the following, confirmed over the course of scoping this component. If any of it is wrong, the sprint numbering below needs to shift, so check this section first:

- **The App (Contractor App) is the one app in this system, and it's contractor-only.** It remains the owner's dashboard for everything — leads, quotes, jobs, pricing rules — regardless of which channel a customer used to arrive.
- **WhatsApp is the customer's interface, full stop.** It covers what `Borewell_04_UIUX.md` §4.1 scoped for a dedicated Customer App — location + job-type intake, quotation display, approve/reject, payment, tracking — delivered as a chat instead of app screens.
- **Practical consequence:** the "Customer App" frontend row in `Borewell_05_Development_Plan.md` Milestone 3 is superseded by this component. There's no separate Customer App to build. If a dedicated customer app is still wanted eventually, this plan doesn't block that later — it just means it isn't on the critical path right now.
- **"Almost all services, though basic"** means breadth over polish: every step of the customer journey gets covered, but each one stays a simple chat interaction, not a native-app-grade UI recreated inside WhatsApp.
- **Written for one developer, sequentially.** Development Plan §2 labels work as Dev A/B/C/D for organizational clarity; there's no parallel team here, so the sprints below are ordered for a single person, not four.

---

## 1. Dependency Reality Check

| Backend service | Status | Blocks |
|---|---|---|
| `platform-spine` | Shipped, tested | Nothing — WhatsApp intake can start immediately |
| `quotation` | Shipped, tested | Nothing — WhatsApp quoting can start immediately |
| `resource-network` | Not started | Doesn't block WhatsApp at all (manual assignment stays manual either way) |
| `payments-data` | Not started | Blocks Sprint W5 (payment close) specifically — nothing else |

This is the load-bearing fact for the whole plan: four of six WhatsApp sprints need nothing that doesn't already exist. Only the payment sprint has a hard dependency.

---

## 2. The New Component

`whatsapp-agent` — same stack as the rest of the platform (FastAPI, same Docker Compose, same CI pattern, same `AGENTS.md`/contract-check discipline), so it costs nothing extra to maintain alongside the other four services.

- **Owns:** a small Postgres table for conversation/escalation records (audit trail, matching SRS §9's principle that financial actions get a trace ID) and a Redis-backed session cache for in-flight conversation state — Redis is already in the stack.
- **Calls, never duplicates:** every job/quote/payment action goes through the real endpoint in `platform-spine` / `quotation` / `payments-data`. The agent is a client of those contracts, exactly like the Contractor App is — never a second source of truth.
- **Exposes:** one webhook (`POST /webhook`, `GET /webhook` for Meta's verification handshake) plus the standard `/healthz`/`/readyz`. Document it in `packages/contracts/openapi/whatsapp-agent.yaml` before writing the handler — same contract-first rule as everything else.

---

## 3. Sprints

| Sprint | What ships | Depends on | DoD |
|---|---|---|---|
| **W0 — Channel + status pings** | Meta Business verification, WhatsApp number, approved templates (job created / quote ready / status changed / payment confirmed); a worker subscribing to the existing `job.created` / `job.quoted` / `job.completed` / `payment.completed` Redis events (Architecture §7) and sending the matching template | Nothing new — events already exist | A real status change in the system produces a real WhatsApp message, with zero LLM involved |
| **W1 — Conversational core + intake** | LLM integration with tool use; system prompt scoped to borewell services only, written to ask for what FR-JOB-01 needs conversationally rather than dump a form; session state in Redis keyed by phone number; first tool: `create_job` → real `POST /v1/jobs` | `platform-spine` (done) | A WhatsApp conversation produces a real Job row, `source: whatsapp` |
| **W2 — Quotation + approve/reject** | Tool: `get_quotation`; quote sent as a WhatsApp message with itemized costs and the depth-range + confidence badge (UIUX §7's disclosure — non-negotiable in any channel); approve/reject as WhatsApp interactive buttons wired to the real approve/reject endpoints | `quotation` (done), W1 | Full lead → quote → approve/reject loop, entirely in WhatsApp, against real services |
| **W3 — Escalation + guardrails** | Escalation triggers (explicit ask, repeated tool failure, off-topic after redirect); escalation flag on the job record, surfaced as a filter in the Contractor App's existing Job List — not a separate inbox; a fixed set of scripted conversation tests (out-of-area location, price haggling, off-topic, "just estimate it without checking") run against real model output | W1, W2 | Agent never computes a price or status itself — always via tool call, verified by a test that tries to get it to; escalated conversations are visible in the one dashboard |
| **W4 — Structured intake + media** | Location/job-type capture migrated from free text to a WhatsApp Flow (native multi-step form — removes a class of misparse bugs); curated media set — depth/confidence explainer, a couple of rig/site photos — sent at the right conversational moments | W1 | Intake uses a Flow, not parsed prose; at least one illustrative image sent per conversation |
| **W5 — Payment close** *(blocked)* | Tool: `create_payment` → real idempotent `payments-data` endpoint; payment message via gateway partner (Razorpay has a first-party WhatsApp integration in India); payment confirmation advances job status (BR-03) | `payments-data` must exist first | A customer goes from first message to `completed` payment entirely in WhatsApp, matching FR-PAY-01 through 04 exactly |
| **W6 — Pilot + hardening** | Message-cost monitoring (per-message billing applies to every template send), basic abuse/rate limiting on the webhook; folds into the existing Milestone 5 pilot | W0–W5, core Milestone 4 | One real job goes lead-to-paid through WhatsApp with a real contractor and real customer |

**Sequencing relative to the core plan:** W0–W2 need nothing you haven't already shipped, so they can run before or alongside `resource-network` — your call, based on what the client wants to see first. W3–W4 want W1/W2 done. W5 has a hard gate: it cannot start until `payments-data`'s Milestone 1 row (Development Plan) is complete. W6 rides on the existing Milestone 5 pilot rather than being a separate event.

---

## 4. Definition of Done — additions specific to this component

On top of Development Plan §4 (all six points still apply):

7. **DoD for any conversational sprint means a real message sent and received against a real WhatsApp test number** — not a mocked webhook payload replayed locally. Same "no unverified 'should work' claims" rule from `AGENTS.md`, applied to a channel where it's easier to fool yourself.
8. **The scripted conversation eval set (Sprint W3) passes before any conversational sprint counts done**, not just its unit tests. Tool-calling functions get unit tests like any pure function, but the conversation *around* them needs its own pass/fail set — there's no single `assert equals` for a chat.

---

## 5. Testing Strategy — additions specific to this component

- **Unit tests:** every tool function (`create_job`, `get_quotation`, `create_payment`, etc.) tested the same way as the pricing and state-machine logic already is — pure inputs and outputs, no model in the loop.
- **Conversation eval set:** a fixed list of scripted scenarios (happy path, out-of-service-area location, price haggling, off-topic request, attempted price override) run against actual model output on every change to the system prompt or tool list — the equivalent of the contract-check tool, but for behavior instead of endpoints.
- **Contract tests:** the existing `tools/contract-check/` run against `whatsapp-agent.yaml` too, so the webhook contract can't silently drift the way any other service's could.
- **Manual walkthrough:** one real conversation on a real test number before signing off each sprint's DoD — cheap, and it catches UX friction automated tests miss, same rationale as Development Plan §5's Milestone 4 pass.

---

## 6. Rollout

Use a WhatsApp test/sandbox number through W0–W4. Move to the verified business number only once W3's guardrails are in and passing — no reason to expose an unguarded agent to a real customer's phone number before escalation and off-topic handling exist. W6's pilot then folds directly into the core plan's Milestone 5, rather than being a second separate pilot event.

---

## 7. Open Decisions

Carried over, still unresolved:

- Is this part of the current client engagement, or a separate proposal on top of the quoted fee?
- Who is "a human assistant" if it's not the contractor — a real second role, or the contractor wearing a second hat during the pilot?
- Direct Meta Cloud API vs. a thin BSP (e.g. 360dialog) vs. a full BSP (Gupshup / AiSensy / Interakt) for platform access.

New, raised by this plan:

- Confirm the Milestone 3 Customer App supersession in §0.
