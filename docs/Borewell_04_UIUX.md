# Borewell Platform — UI/UX Document

**Project:** Borewell Platform
**Scope:** Customer App + Contractor App (MVP). Resource Owner App is noted but not detailed — it's Phase 1, per the PRD.
**Date:** August 23, 2026

---

## 1. Design Principles

1. **Simple over comprehensive.** A customer requesting a borewell has no domain knowledge — every screen should be understandable without explanation.
2. **Trustworthy, not flashy.** This handles money and a physical construction project; the design should read as credible and calm, not playful.
3. **Efficient for repeated daily use.** The contractor uses this tool every day — the Contractor App optimizes for speed of repeated tasks (quoting, status updates) over first-impression polish.
4. **Never hide the estimate's uncertainty.** Depth ranges and confidence labels are a design requirement, not a footnote — see §7.

---

## 2. Users & Context of Use

| App | Primary device | Context |
|---|---|---|
| Customer App | Mobile, often on average mobile data | Used a handful of times per job — request, check status, pay. Low tolerance for friction. |
| Contractor App | Desktop/tablet primarily | Used many times daily — needs to be fast for repeat tasks, not just first-time-friendly. |

---

## 3. Navigation & Information Architecture

**Customer App** — linear, bottom-nav for the few persistent destinations:
```
Bottom nav: [Home] [My Jobs] [Profile]
Home → Request flow (Location → Quote → Approve → Pay)
My Jobs → list → Job Detail (status/tracking)
```

**Contractor App** — sidebar, since there's more to navigate and it's used on larger screens:
```
Sidebar: Dashboard | Leads | Jobs | Pricing Rules | Settings
```

---

## 4. Screens & User Flows

### 4.1 Customer App

| Screen | Purpose | Key elements | Primary action |
|---|---|---|---|
| **Location Entry** | Start a request | Map/address input, job-type selector | "Get Estimate" |
| **Quotation Display** | Show the price | Depth range + confidence badge, itemized cost list, total | "Approve & Pay" / "Request Changes" |
| **Payment** | Collect payment | Amount, payment method selection | "Pay Now" |
| **Job Tracking** | Show live status | Status stepper (matches job lifecycle stages), last update timestamp | (passive screen, pull-to-refresh) |
| **Job History** | Past jobs | List of completed jobs with final cost | Tap → read-only job detail |

**Primary flow:**
```
Location Entry → Quotation Display → Payment → Job Tracking → (on completion) Job History
```

### 4.2 Contractor App

| Screen | Purpose | Key elements | Primary action |
|---|---|---|---|
| **Dashboard** | Daily overview | New leads count, active jobs list, jobs awaiting action | Tap a lead/job → detail |
| **Lead Detail / Quotation Generator** | Turn a lead into a quote | Location + job type (from customer), auto-generated line items (editable), total | "Send Quotation" |
| **Pricing Rules** | Configure the quotation engine | Base rates, margin %, minimum charge, surcharges (form-based, not code) | "Save Rules" |
| **Job List** | All jobs, filterable by status | Table: customer, location, status, value | Tap a row → Job Detail |
| **Job Detail / Progress** | Track and update one job | Status stepper (contractor-editable), notes field, "mark next stage" button | Advance status |
| **Job Completion** | Close out a job | Actual depth input, actual cost input, computed variance | "Mark Complete" |
| **Margin Summary** | See quoted vs. actual | Simple table/list, not a full dashboard in MVP | (read-only) |

---

## 5. Components

Shared across both apps via `apps/shared-ui`:

- **Status badge** — one visual style per job-lifecycle stage, consistent color coding (see §11)
- **Stepper** — shows job progress as a horizontal/vertical sequence of stages
- **Itemized cost list** — line items + total, used in both the quotation display and the completion screen
- **Form input group** — label + input + inline validation message, consistent across every form in both apps
- **Data table** (Contractor App only) — sortable, used for Job List and Leads

---

## 6. Interactions & Forms

- Every form validates inline, not just on submit — a phone number or amount error shows immediately after the field loses focus, not after a failed submission.
- Required fields are marked, not just implied.
- The "Send Quotation" and "Mark Complete" actions require a confirmation step (not a silent single tap) — both are consequential and hard to walk back.

---

## 7. Loading, Error, and Empty States

| State | Where | Treatment |
|---|---|---|
| **Loading** | Quotation generation | Skeleton or spinner with the message "Calculating your estimate..." — never a blank screen |
| **Empty** | Contractor Dashboard, no leads yet | Friendly empty state explaining what will appear here, not just a blank list |
| **Empty** | Customer Job History, no past jobs | "Your completed jobs will appear here" |
| **Error** | Payment fails | Clear message + "Try Again" — never a generic "Something went wrong" with no next step |
| **Error** | Quotation generation fails (e.g. pricing rules incomplete) | Contractor-side error naming exactly what's missing (e.g. "Set a base drilling rate before generating quotes") |
| **Uncertainty (not technically an "error")** | Every quotation display | Depth range shown as a range with a visible confidence badge (low/medium/high) and one line explaining actual depth may vary — this is a required element, not optional polish |

---

## 8. Responsive Behavior

- **Customer App:** mobile-first, single-column at all breakpoints; this app is not expected to be used on desktop, so desktop layout is not a design priority for MVP.
- **Contractor App:** responsive from tablet up; sidebar collapses to a top bar below ~768px; data tables become stacked cards on narrow viewports rather than horizontally scrolling.

---

## 9. Accessibility

- Minimum contrast ratio: WCAG AA (4.5:1 for body text).
- Minimum touch target: 44×44px on all interactive elements (Customer App especially, given mobile-first + potentially older or less tech-familiar users).
- Base font size: 16px minimum for body text — no shrinking below this for density's sake.
- All icons paired with text labels or `aria-label`s — never icon-only for a primary action.
- Form errors announced to screen readers, not just shown visually.

---

## 10. Typography

- **Typeface:** a clean, highly legible sans-serif (e.g. Inter or similar) — optimized for readability at small sizes on mobile data-constrained devices, not for personality.
- **Scale:**

| Style | Size | Weight |
|---|---|---|
| H1 (screen title) | 24px | 600 |
| H2 (section header) | 18px | 600 |
| Body | 16px | 400 |
| Caption/meta | 13px | 400 |

---

## 11. Color Palette

Trustworthy, not decorative — this handles money and physical infrastructure work:

| Role | Color direction | Usage |
|---|---|---|
| Primary | Deep blue/teal | Primary actions, active nav state |
| Secondary/accent | Earth tone (ochre/terracotta) | Subtle accents only — reflects the drilling/groundwater domain without being literal |
| Success | Green | Completed jobs, "Available" status |
| Warning | Amber | In-progress states, "low confidence" estimate badge |
| Error | Red | Failed payments, validation errors |
| Neutral | Grey scale | Body text, borders, backgrounds |

Exact hex values are a Phase-1 design-system task, not blocking MVP implementation — the above is enough to start building without inconsistent ad-hoc color choices.

---

## 12. Spacing System

4px base unit, standard scale: 4 / 8 / 12 / 16 / 24 / 32 / 48px. Applied consistently for padding/margins across both apps via `shared-ui` so spacing doesn't drift between screens built by different devs.
