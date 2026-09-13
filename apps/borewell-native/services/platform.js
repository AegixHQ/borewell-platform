/**
 * Ported from apps/shared-ui/src/platform.js - see that file for the full
 * original design-rationale comments (pure fetch, no data-fetching
 * library, Decimal-as-string handling for money fields, the documented
 * gateway deviation). This is NOT a fork meant to diverge - if the real
 * shared-ui file changes, re-sync this one by hand (no build tooling
 * currently shares code between the Vite web workspace and this Expo app -
 * see this app's AGENTS.md for why apps/borewell-native is deliberately
 * excluded from the root npm workspace).
 *
 * Every function body below is copied verbatim from shared-ui/platform.js
 * - confirmed there is no browser-only API anywhere in it (no window,
 * document, localStorage) before porting, so this was a mechanical copy,
 * not a rewrite. The ONLY real adaptation is the env var section below:
 * Vite's `import.meta.env.VITE_*` doesn't exist in Expo's bundler at all
 * (it's not just unavailable at runtime - it's a build-time syntax error
 * in this environment). Expo's actual convention is
 * `process.env.EXPO_PUBLIC_*` - any env var prefixed EXPO_PUBLIC_ in a
 * .env file at the project root is inlined at build time. See
 * https://docs.expo.dev/guides/environment-variables/ (verify against
 * current docs before relying on this - Expo's own scaffolded AGENTS.md
 * in this same directory says exactly that: "Expo HAS CHANGED, read
 * versioned docs before writing code").
 */

export const PLATFORM_SPINE_URL =
  process.env.EXPO_PUBLIC_PLATFORM_SPINE_URL || "http://localhost:8001";
export const QUOTATION_URL =
  process.env.EXPO_PUBLIC_QUOTATION_URL || "http://localhost:8002";
export const RESOURCE_NETWORK_URL =
  process.env.EXPO_PUBLIC_RESOURCE_NETWORK_URL || "http://localhost:8003";
export const PAYMENTS_URL =
  process.env.EXPO_PUBLIC_PAYMENTS_URL || "http://localhost:8004";

// "localhost" above will NOT reach your backend from a real device or
// even the iOS Simulator/Android Emulator in many setups - localhost
// inside the emulator/simulator/device refers to ITSELF, not your
// development machine. For local development against `make up`'s dev
// stack, set these in a .env file at this app's root (gitignored, same
// as .env.prod is at the repo root - see that file's own .gitignore
// entry for the pattern) to your machine's real LAN IP, e.g.
// EXPO_PUBLIC_PLATFORM_SPINE_URL=http://192.168.1.50:8001 - not
// something this file can detect or default correctly on its own.

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
// an error to surface.
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
  // has from the quotation response - do not coerce this to Number()
  // before sending it back; both quotation and payments-data compare it
  // for EXACT equality against a Decimal-as-string value (see the money-
  // precision comments in the backend services' schemas.py files).
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
