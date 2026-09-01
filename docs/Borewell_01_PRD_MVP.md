# Borewell Platform — Product Requirements Document (MVP)

**Project:** Borewell Platform
**Version:** MVP scope
**Date:** August 23, 2026

---

## 1. Problem Statement

Borewell contractors currently run quoting, scheduling, and job coordination manually — phone calls, WhatsApp, and spreadsheet-based costing. Customers have no transparency into pricing or job progress. Nobody captures structured job data, so every quote starts from scratch, and contractors don't reliably know their margin until well after a job closes.

## 2. Target Users

| User | Role in MVP |
|---|---|
| **Customer** | Requests a borewell, receives a quote, pays, tracks the job |
| **Contractor** | Runs the business: manages leads, generates quotes, tracks jobs, logs costs |
| **Resource Owner** (rig/equipment/labour) | *Out of MVP scope* — contractor coordinates with them manually outside the app |

## 3. Goals & Objectives

- Give the contractor one place to capture a lead, generate a price, and track a job to completion
- Give the customer a transparent, simple request-and-quote experience
- Replace guesswork costing with a configurable rules-based quotation engine
- Establish the data foundation (job records with quoted vs. actual cost) that later phases build on

## 4. Core Features (MVP)

**Customer-facing:**
- Submit a service request with location
- Receive a quotation (estimated depth + itemized cost)
- Approve the quotation and pay
- Track job status

**Contractor-facing:**
- Lead capture
- Configurable quotation engine (base rates, margin, surcharges)
- Manual resource assignment and job scheduling
- Job progress tracking
- Actual-cost logging and a quoted-vs-actual margin view

## 5. MVP Scope

| In scope | Out of scope (later phases) |
|---|---|
| Full job lifecycle: lead → quote → approval → booking → tracking → completion → payment | Resource Owner App / automated resource matching |
| Rule-based quotation engine with a flat/assumed depth estimate | Historical-data-driven depth estimation |
| Single-flow customer payment | Split payments/payouts to resource owners |
| Manual resource assignment by the contractor | Ranked resource-matching suggestions |
| Basic status notifications | Analytics dashboards, location intelligence layer |

## 6. User Stories

| ID | Story | Priority |
|---|---|---|
| US-01 | As a **customer**, I want to submit my location and job type, so I can get a price without calling anyone. | Must |
| US-02 | As a **customer**, I want to see an itemized cost breakdown, so I understand what I'm paying for. | Must |
| US-03 | As a **customer**, I want to approve or reject a quotation, so I control whether the job proceeds. | Must |
| US-04 | As a **customer**, I want to pay through the app, so I don't need a separate payment step. | Must |
| US-05 | As a **customer**, I want to see the current status of my job, so I know what's happening without calling the contractor. | Should |
| US-06 | As a **contractor**, I want incoming requests to appear as leads, so nothing gets lost in a phone call. | Must |
| US-07 | As a **contractor**, I want to configure my own pricing rules (base rates, margin, minimum charge), so quotes reflect my actual business, not a generic formula. | Must |
| US-08 | As a **contractor**, I want the system to generate a quotation automatically from my rules, so I don't calculate it by hand every time. | Must |
| US-09 | As a **contractor**, I want to move a job through its stages (booked → drilling → complete), so I have one accurate record instead of scattered notes. | Must |
| US-10 | As a **contractor**, I want to log the actual cost of a completed job, so I can see whether I quoted it correctly. | Must |
| US-11 | As a **contractor**, I want to see quoted margin vs. actual margin per job, so I know if my pricing rules need adjusting. | Should |
| US-12 | As a **contractor**, I want to see a list of my active and past jobs, so I can find any job quickly. | Should |

## 7. Success Metrics

- Time from lead capture to quotation delivered (target: minutes, not hours)
- Quote-to-booking conversion rate
- % of completed jobs with actual cost logged (data completeness — needed for every later phase)
- Quoted-vs-actual cost variance, tracked per job (this is the number that tells the contractor if the MVP is actually useful)

## 8. Assumptions

- Single contractor pilot to start (Chennai / Tamil Nadu)
- Currency: INR
- Contractor has internet access for job management; customer request flow works over basic mobile data
- Depth estimation in MVP is a flat/contractor-configured assumption, not a real geological estimate — this is explicit, not hidden (see SRS §8 for how this is surfaced to the customer)

## 9. Risks

| Risk | Mitigation |
|---|---|
| Contractor doesn't trust the system's price enough to send it as-is | Every quotation is editable before sending; system proposes, contractor confirms |
| Customer distrust of paying through an unfamiliar app | Clear, itemized pricing; payment via a recognized gateway, not a custom flow |
| Flat depth estimate is materially wrong for a specific site | Depth is always shown as a range with a disclaimer, and the contractor can override the estimate manually before quoting |
| Low usage during pilot makes it hard to judge if this is working | Success metrics (§7) are tracked from day one, not added later |

## 10. Out-of-Scope Features (explicit)

- Resource Owner App and any rig/equipment self-service portal
- Automated resource matching/ranking
- Split payments and automated payouts
- Historical-job-based or ML-based depth estimation
- Location intelligence (groundwater/geological reference data integration)
- Analytics dashboards beyond the basic margin view in US-11
- Multi-contractor / multi-tenant support

These are deliberately deferred — see `docs/rfc/0001-microservices-architecture.md` §7 for when they're picked back up.

## 11. Acceptance Criteria (MVP-level)

The MVP is done when:
1. A customer can go from "submit location" to "job marked complete" entirely through the app, with a contractor performing only the steps that are explicitly manual (resource coordination, drilling execution).
2. Every job has both a quoted cost and an actual cost recorded by completion.
3. A contractor can configure their own pricing rules without needing a developer to change code.
4. All 12 user stories in §6 pass their corresponding acceptance criteria in the SRS.
