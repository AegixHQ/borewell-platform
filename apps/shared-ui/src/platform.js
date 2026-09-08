/**
 * Job/quotation/payment API calls shared across the app(s). Same rationale
 * as auth.js for living in shared-ui rather than apps/web-app/src directly.
 *
 * Deliberately plain fetch, no React Query / axios / client-side cache -
 * matching Architecture doc section 3's explicit call: "component state +
 * fetch... adding [a state library] before there's a real cross-screen
 * state-sharing problem would be exactly the kind of unnecessary
 * complexity AGENTS.md warns against." Same reasoning applies to a data-
 * fetching library at this scale (a handful of screens, no cache
 * invalidation problem yet).
 *
 * Every function takes the service's base URL as its first argument (same
 * convention as login/registerAccount in auth.js) and the caller's JWT as
 * its last - nothing here reads environment variables or session state
 * directly, so these functions stay pure and testable.
 *
 * Amount fields: several of these cross the money-precision fix from this
 * session's backend work. total_estimate/amount come back from the API as
 * numeric STRINGS (e.g. "95450.00"), not JSON numbers - both quotation and
 * payments-data serialize Decimal that way deliberately, to avoid the
 * float round-trip that caused the original Bug 2 gap (see those
 * services' app/schemas.py and packages/contracts/openapi/*.yaml). Treat
 * these fields as display strings; do not coerce them to Number() for
 * anything that gets sent back to the API (job_id/quotation_id pairing
 * and the amount itself) - pass the string straight through unchanged so
 * the exact-match check on the backend has something exact to compare
 * against.
 */

// KNOWN DEVIATION from this folder's own AGENTS.md ("Never call a service
// directly - always through the gateway"): infra/gateway/traefik.yml is a
// placeholder (its own comment: "Fill in once a real gateway is chosen"),
// has no upstream service targets defined, and isn't wired into
// docker-compose.yml at all - there's currently nothing listening to
// route through. App.jsx's login/register calls already called
// platform-spine directly before any of this file existed; these three
// constants just centralize that same pattern (previously copy-pasted per
// dashboard file) rather than inventing a new one. Building the frontend
// against a gateway that doesn't run would produce something that
// doesn't work at all, which is worse than a documented shortcut.
// Swap these three fetches for one gateway base URL once infra/gateway/
// is real - every call in this file already goes through request(), so
// that swap is a one-line change per constant, not a rewrite.
export const PLATFORM_SPINE_URL =
  import.meta.env.VITE_PLATFORM_SPINE_URL || "http://localhost:8001";
export const QUOTATION_URL =
  import.meta.env.VITE_QUOTATION_URL || "http://localhost:8002";
export const RESOURCE_NETWORK_URL =
  import.meta.env.VITE_RESOURCE_NETWORK_URL || "http://localhost:8003";
export const PAYMENTS_URL =
  import.meta.env.VITE_PAYMENTS_URL || "http://localhost:8004";

async function request(baseUrl, path, { method = "GET", token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(data?.error?.message || `Request failed (${response.status})`);
    err.code = data?.error?.code;
    err.status = response.status;
    throw err;
  }
  return data;
}

// --- platform-spine: jobs ---

export async function createJob(platformSpineUrl, token, { lat, lng, jobType }) {
  return request(platformSpineUrl, "/v1/jobs", {
    method: "POST",
    token,
    body: { location: { lat, lng }, job_type: jobType },
  });
}

export async function listMyJobs(platformSpineUrl, token) {
  return request(platformSpineUrl, "/v1/jobs", { token });
}

export async function getJob(platformSpineUrl, token, jobId) {
  return request(platformSpineUrl, `/v1/jobs/${jobId}`, { token });
}

export async function updateJobStatus(platformSpineUrl, token, jobId, newStatus) {
  return request(platformSpineUrl, `/v1/jobs/${jobId}/status`, {
    method: "PATCH",
    token,
    body: { status: newStatus },
  });
}

// --- quotation: pricing rules (contractor only) ---

export async function upsertPricingRule(quotationUrl, token, rule) {
  return request(quotationUrl, "/v1/pricing-rules", {
    method: "POST",
    token,
    body: rule,
  });
}

export async function listPricingRules(quotationUrl, token) {
  return request(quotationUrl, "/v1/pricing-rules", { token });
}

// --- quotation: generation (contractor only) ---

export async function generateQuotation(quotationUrl, token, { jobId, lat, lng, jobType }) {
  return request(quotationUrl, "/v1/quotations", {
    method: "POST",
    token,
    body: { job_id: jobId, location: { lat, lng }, job_type: jobType },
  });
}

// --- quotation ---

// 404 (QUOTATION_NOT_FOUND) is an expected, common case here - a job that
// was just created has no quotation yet, until the contractor generates
// one. Callers should catch this and treat it as "not quoted yet", not as
// an error to surface - see CustomerDashboard's polling loop.
export async function getLatestQuotationForJob(quotationUrl, token, jobId) {
  return request(quotationUrl, `/v1/quotations/job/${jobId}/latest`, { token });
}

export async function approveQuotation(quotationUrl, token, quotationId) {
  return request(quotationUrl, `/v1/quotations/${quotationId}/approve`, {
    method: "POST",
    token,
  });
}

export async function rejectQuotation(quotationUrl, token, quotationId) {
  return request(quotationUrl, `/v1/quotations/${quotationId}/reject`, {
    method: "POST",
    token,
  });
}

// --- payments-data ---

export async function createPayment(
  paymentsUrl,
  token,
  { jobId, quotationId, amount, idempotencyKey }
) {
  // amount is passed through as whatever string/number the caller already
  // has from the quotation response - see this file's header comment on
  // why coercing it would be a mistake.
  return request(paymentsUrl, "/v1/payments", {
    method: "POST",
    token,
    body: {
      job_id: jobId,
      quotation_id: quotationId,
      amount,
      idempotency_key: idempotencyKey,
    },
  });
}

export async function getPayment(paymentsUrl, token, paymentId) {
  return request(paymentsUrl, `/v1/payments/${paymentId}`, { token });
}

// --- resource-network: resources (owned by resource_owner) ---

export async function createResource(resourceNetworkUrl, token, resource) {
  // resource: { resource_type, name, notes?, lat?, lng?, hourly_rate?, vehicle_type? }
  return request(resourceNetworkUrl, "/v1/resources", {
    method: "POST",
    token,
    body: resource,
  });
}

export async function listMyResources(resourceNetworkUrl, token, statusFilter) {
  const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  return request(resourceNetworkUrl, `/v1/resources${query}`, { token });
}

export async function updateResource(resourceNetworkUrl, token, resourceId, updates) {
  return request(resourceNetworkUrl, `/v1/resources/${resourceId}`, {
    method: "PATCH",
    token,
    body: updates,
  });
}

// --- resource-network: marketplace search (contractor only) ---

export async function matchResources(
  resourceNetworkUrl,
  token,
  { lat, lng, resourceType, maxResults }
) {
  return request(resourceNetworkUrl, "/v1/resources/match", {
    method: "POST",
    token,
    body: {
      lat,
      lng,
      resource_type: resourceType,
      max_results: maxResults || 5,
    },
  });
}

// --- resource-network: booking requests ---

export async function createBookingRequest(
  resourceNetworkUrl,
  token,
  { resourceId, jobId, message }
) {
  return request(resourceNetworkUrl, "/v1/bookings", {
    method: "POST",
    token,
    body: { resource_id: resourceId, job_id: jobId, message },
  });
}

export async function listBookings(resourceNetworkUrl, token, statusFilter) {
  const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  return request(resourceNetworkUrl, `/v1/bookings${query}`, { token });
}

export async function acceptBooking(resourceNetworkUrl, token, bookingId) {
  return request(resourceNetworkUrl, `/v1/bookings/${bookingId}/accept`, {
    method: "POST",
    token,
  });
}

export async function rejectBooking(resourceNetworkUrl, token, bookingId) {
  return request(resourceNetworkUrl, `/v1/bookings/${bookingId}/reject`, {
    method: "POST",
    token,
  });
}
