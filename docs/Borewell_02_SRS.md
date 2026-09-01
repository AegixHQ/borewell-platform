# Borewell Platform — Software Requirements Specification (SRS)

**Project:** Borewell Platform
**Scope:** MVP (see `Borewell_01_PRD_MVP.md` for scope boundary)
**Date:** August 23, 2026

---

## 1. Introduction

**Purpose:** Define testable functional and non-functional requirements for the MVP so implementation doesn't require guessing at behavior.

**Scope:** Customer request → quotation → approval → payment → job tracking → completion, for a single contractor.

**Definitions:**
- **Job** — the central record tracking one borewell project from lead to completion
- **Quotation** — a priced estimate generated for a job, versioned
- **Line item** — one component of a quotation (drilling, casing, labour, etc.)

---

## 2. User Roles & Permissions

| Role | Can do | Cannot do |
|---|---|---|
| **Customer** | Create a job request, view/approve/reject their own quotations, pay for their own jobs, view their own job status and history | View or act on any other customer's data; edit pricing rules; change job status directly |
| **Contractor** | View/manage all leads and jobs, configure pricing rules, generate/edit quotations, move job status forward, log actual costs, view margin data | Access another contractor's data (not applicable in single-contractor MVP, but the permission model must not assume single-tenancy permanently) |
| **Admin** | View all data for support purposes, resolve disputes | Edit financial records without an audit trail entry |

---

## 3. Functional Requirements

### 3.1 Authentication (FR-AUTH)
- **FR-AUTH-01:** The system shall allow a user to register with email + password.
- **FR-AUTH-02:** The system shall issue a JWT on successful login, scoped to the user's role.
- **FR-AUTH-03:** The system shall reject any API request with a missing, expired, or invalid token with a 401 response.
- **FR-AUTH-04:** The system shall enforce role-based access on every endpoint — a customer token shall not be able to call any contractor-only endpoint, and vice versa.

### 3.2 Job Creation & Lifecycle (FR-JOB)
- **FR-JOB-01:** The system shall allow a customer to create a job by submitting a location (lat/lng or address) and a job type (residential/agricultural/commercial).
- **FR-JOB-02:** The system shall assign a new job the status `lead` on creation.
- **FR-JOB-03:** The system shall only allow status transitions in the order defined in RFC 0001 §8 (`lead → site_location → requirement → estimation → price_calculation → quotation → customer_approval → booking → resource_allocation → drilling → progress → completion → payment → service_history`). Skipping a state shall be rejected.
- **FR-JOB-04:** The system shall allow only the contractor role to advance a job's status (customer actions like "approve quotation" trigger the transition, but the customer never sets status directly).
- **FR-JOB-05:** The system shall allow a customer to view the current status of their own jobs at any time.

### 3.3 Quotation Engine (FR-QUOTE)
- **FR-QUOTE-01:** The system shall generate a quotation using the contractor's configured base rates, resource rules, and commercial rules (RFC 0001 FR-K14).
- **FR-QUOTE-02:** The system shall express the estimated depth as a range (`min_ft`, `max_ft`), never a single fixed number.
- **FR-QUOTE-03:** The system shall label every quotation with a confidence level (`low`/`medium`/`high`) per RFC 0001 §6 — MVP always returns `low` unless the contractor has manually confirmed the estimate.
- **FR-QUOTE-04:** The system shall allow the contractor to edit any line item or the total before sending a quotation to the customer.
- **FR-QUOTE-05:** The system shall version a quotation on every edit; a customer shall only ever see the latest version unless a revision history is explicitly requested.
- **FR-QUOTE-06:** The system shall not allow a quotation total below the contractor's configured minimum job charge.

### 3.4 Payment (FR-PAY)
- **FR-PAY-01:** The system shall require a customer to approve a quotation before a payment can be initiated.
- **FR-PAY-02:** The system shall require an idempotency key on every payment-creation request.
- **FR-PAY-03:** The system shall not process two payments with the same idempotency key as two separate charges.
- **FR-PAY-04:** The system shall record payment status as `pending`, `completed`, or `failed`, and shall not advance a job's status to `payment`-complete states on a `failed` payment.

### 3.5 Job Tracking (FR-TRACK)
- **FR-TRACK-01:** The system shall allow the contractor to log progress notes and status updates on a job.
- **FR-TRACK-02:** The system shall notify the customer (in-app, at minimum) on every job status change.
- **FR-TRACK-03:** The system shall allow the contractor to record actual depth and actual cost when marking a job `completion`.
- **FR-TRACK-04:** The system shall compute and display quoted-vs-actual cost variance once actual cost is logged.

---

## 4. Business Rules

| ID | Rule |
|---|---|
| BR-01 | A quotation total is never below the contractor's configured minimum job charge (see FR-QUOTE-06). |
| BR-02 | A job cannot enter `booking` status until its quotation has customer approval on record. |
| BR-03 | A job cannot enter `payment`-complete status without a `completed` payment record. |
| BR-04 | Margin is calculated as `total_estimate − expected_cost` at quote time, and `actual_revenue − actual_cost` at completion; both are stored, never overwritten. |
| BR-05 | Depth overage (actual depth beyond the quoted max) is priced at the contractor's configured per-foot overage rate, applied transparently and shown to the customer at completion, not silently added. |
| BR-06 | Once a customer approves a quotation, further edits create a new version requiring re-approval — the contractor cannot silently change an approved price. |

---

## 5. Data Requirements

| Entity | Key Fields | Constraints |
|---|---|---|
| **Customer** | id, name, phone, email, address | phone required and unique; email optional |
| **Contractor** | id, business_name, service_area, pricing_config | pricing_config is a structured object, not free text |
| **Job** | id, customer_id, contractor_id, location (lat/lng), job_type, status, created_at | status must be one of the defined lifecycle states |
| **Quotation** | id, job_id, version, line_items[], estimated_depth_range, confidence, total, status | version increments on every edit; status: draft/sent/approved/rejected |
| **Payment** | id, job_id, amount, idempotency_key, status, created_at | idempotency_key unique per payment attempt |
| **Job Completion Record** | job_id, actual_depth_ft, actual_cost, completed_at | only writable once, by the contractor |

---

## 6. Validation Rules

| Field | Rule |
|---|---|
| Location (lat/lng) | Must be valid coordinates; reject 0,0 or out-of-range values |
| Phone number | Must match a valid Indian mobile number format (+91 and 10 digits) |
| Email | Standard email format, when provided |
| job_type | Must be one of the enum values (`residential`, `agricultural`, `commercial`) — reject anything else |
| Quotation total | Must be > 0 and ≥ contractor's minimum job charge |
| Payment amount | Must exactly match the approved quotation total (or a defined milestone portion of it) — reject mismatches rather than silently accepting a different amount |
| idempotency_key | Required on every payment POST; reject requests missing it |

---

## 7. Authentication & Authorization

- JWT-based auth, issued by the `platform-spine` service (RFC 0001 §2).
- Tokens carry role (`customer`/`contractor`/`admin`) and are validated locally by each service — no per-request callback (RFC §5).
- Token expiry: short-lived access token; refresh flow is a Phase 1 concern, not MVP-blocking, but the token format should not preclude adding it later.
- Every endpoint declares its required role explicitly; there is no "default allow."

---

## 8. Error Handling & Edge Cases

All errors follow the shared format from RFC 0001 §5: `{"error": {"code": "...", "message": "...", "trace_id": "..."}}`.

| Edge case | Expected behavior |
|---|---|
| Customer submits a duplicate job request for the same location within a short window | Accepted as a new job — the system does not guess intent; the contractor sees both leads and can merge/reject manually |
| Payment request retried after a network timeout | Idempotency key ensures no double charge (FR-PAY-03) |
| Customer tries to approve a quotation that's already been superseded by a new version | Rejected with a clear error; customer is shown the latest version |
| Contractor tries to skip a job status (e.g. `lead` straight to `completion`) | Rejected per FR-JOB-03 |
| Contractor edits pricing rules while a quotation is mid-generation | The quotation in progress uses the rules as they were at generation start; the new rules apply to the next quotation only |
| Job is cancelled after payment | Out of MVP scope for automated refund logic — flagged as a manual process for the pilot, not silently unhandled |

---

## 9. Security Requirements

- All traffic over HTTPS.
- Passwords hashed (never stored plaintext or reversibly encrypted).
- Payment data handled via a compliant payment gateway — the platform never stores raw card/bank details.
- PII (customer contact info, address) accessible only to the customer themself, the assigned contractor, and admin.
- Every financial mutation (payment, quotation approval) is logged with a trace ID for audit purposes (RFC 0001 §5).

---

## 10. Performance Requirements

- Quotation generation: near-instant from the customer's perspective (target: a few seconds, per RFC 0001 §10).
- API response time: standard CRUD operations should respond well within what feels instant to a mobile user on average Indian mobile data conditions.
- MVP is scoped to single-contractor load — no defined concurrent-user target yet; the architecture (stateless services, DB-per-service) does not block scaling later (see Architecture doc §12).

---

## 11. Acceptance Criteria

| Requirement group | Acceptance test |
|---|---|
| FR-AUTH | A user with a customer token cannot successfully call any contractor-only endpoint (verified by an automated test, not manual inspection) |
| FR-JOB | Attempting an out-of-order status transition returns an error and the job's status is unchanged |
| FR-QUOTE | A generated quotation never has a total below the configured minimum, and always includes a depth range + confidence label |
| FR-PAY | Submitting the same payment request twice with the same idempotency key results in exactly one `completed` payment record |
| FR-TRACK | Marking a job `completion` without actual cost logged is rejected; with it logged, the variance calculation matches `actual − quoted` exactly |
