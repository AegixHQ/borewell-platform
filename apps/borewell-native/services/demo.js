/**
 * DEMO MODE - a fake backend, for looking at the app without running the
 * four services.
 *
 * Hand-ported from apps/web-app/src/demo/mockApi.js (same convention as
 * services/platform.js in this directory - there is no build tooling
 * sharing code between the Vite web workspace and this Expo app, see this
 * app's AGENTS.md). The seed data, the routes and the response shapes are
 * a verbatim copy; only the four browser-only APIs the original leans on
 * were replaced, because none of them can be assumed present in Hermes:
 *
 *   window.fetch  -> global.fetch
 *   crypto.randomUUID -> uuid4() below
 *   btoa / atob   -> the base64 helpers below (same approach as
 *                    services/auth.js's base64UrlDecode, for the same reason)
 *   new Response  -> a duck-typed response object (see ok())
 *
 * Switched on by EXPO_PUBLIC_DEMO=1, and by default when no backend URL is
 * configured at all - see DEMO_MODE in services/config.js.
 *
 * Deliberate limitations, since this is a shop window and not a second
 * implementation of the backend:
 *   - no real auth: any password works for the seeded accounts, and the
 *     token is an unsigned base64 blob shaped like the real JWT
 *   - state lives in memory and resets when the app reloads
 *   - the pricing maths mirrors services/quotation/app/pricing/engine.py
 *     closely enough for the screens to be honest, but the real engine
 *     stays the source of truth
 */

const B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function b64encode(input) {
  let output = "";
  for (let i = 0; i < input.length; i += 3) {
    const a = input.charCodeAt(i);
    const b = input.charCodeAt(i + 1);
    const c = input.charCodeAt(i + 2);
    const chunk = (a << 16) | ((Number.isNaN(b) ? 0 : b) << 8) | (Number.isNaN(c) ? 0 : c);
    output += B64[(chunk >> 18) & 63] + B64[(chunk >> 12) & 63];
    output += Number.isNaN(b) ? "=" : B64[(chunk >> 6) & 63];
    output += Number.isNaN(c) ? "=" : B64[chunk & 63];
  }
  return output;
}

function b64decode(input) {
  const padded = input.padEnd(input.length + ((4 - (input.length % 4)) % 4), "=");
  let output = "";
  let buffer = 0;
  let bits = 0;
  for (const char of padded) {
    if (char === "=") break;
    buffer = (buffer << 6) | B64.indexOf(char);
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      output += String.fromCharCode((buffer >> bits) & 0xff);
    }
  }
  return output;
}

function uuid4() {
  // crypto.randomUUID() is a browser/Node API; Hermes has no global crypto
  // unless expo-crypto is installed. These ids never leave the demo.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}


const DAY = 86400000;
const now = Date.now();
const iso = (ms) => new Date(ms).toISOString().replace("Z", "");

function uuid(seed) {
  // Stable-ish ids: seeded rows pass their own, anything created at
  // runtime gets a fresh one.
  if (seed) return seed;
  return uuid4();
}

function token(user) {
  const b64 = (obj) => b64encode(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const payload = { sub: user.id, role: user.role, email: user.email, exp: Math.floor((now + 30 * DAY) / 1000) };
  return `${b64({ alg: "none", typ: "JWT" })}.${b64(payload)}.demo`;
}

function money(n) {
  return Number(n).toFixed(2);
}

// ---------------------------------------------------------------- seed data

const users = [
  { id: uuid("11111111-1111-4111-8111-111111111111"), email: "selvi@demo.in", role: "customer" },
  { id: uuid("22222222-2222-4222-8222-222222222222"), email: "senthil@demo.in", role: "contractor" },
  { id: uuid("33333333-3333-4333-8333-333333333333"), email: "murugan@demo.in", role: "resource_owner" },
];
const [CUSTOMER, CONTRACTOR, OWNER] = users;
const OTHER_OWNER = uuid("44444444-4444-4444-8444-444444444444");

const serviceAreas = [
  area("Kallikudi", "Madurai", 9.8201, 77.9845, 8, 440, 60),
  area("Thirumangalam", "Madurai", 9.8225, 77.9878, 10, 385, 55),
  area("T. Kallupatti", "Madurai", 9.7189, 77.8981, 9, 510, 80),
];
function area(name, district, lat, lng, radius, depth, band) {
  return {
    area_id: uuid(),
    name,
    district,
    state: "Tamil Nadu",
    center_lat: lat,
    center_lng: lng,
    radius_km: radius,
    estimated_water_depth_ft: depth,
    confidence_band_ft: band,
    source: "contractor_estimate",
    updated_at: iso(now - 20 * DAY),
  };
}

const pricingRules = ["agricultural", "residential", "commercial"].map((jobType) => ({
  id: uuid(),
  contractor_id: CONTRACTOR.id,
  job_type: jobType,
  base_rate_per_ft: jobType === "commercial" ? 110 : 95,
  casing_rate_per_ft: 45,
  labour_flat_fee: 6000,
  transport_flat_fee: 4500,
  equipment_flat_fee: 3500,
  installation_flat_fee: 8000,
  margin_percent: 15,
  minimum_job_charge: 25000,
  assumed_depth_ft: 450,
  depth_confidence_band_ft: 70,
  depth_overage_rate_per_ft: 120,
}));

const resources = [
  resource(OWNER.id, "rig", "Tata 1613 DTH rig", "Truck-mounted DTH 6.5”", 2800, 9.83, 77.99, "available", "Crew of 4 included"),
  resource(OWNER.id, "equipment", "Air compressor 900 CFM", "Trailer compressor", 900, 9.86, 78.02, "available", ""),
  resource(OWNER.id, "labour", "Drilling crew — 4 people", "", 1200, 9.84, 78.0, "in_use", "Currently on the Sivarakottai job"),
  resource(OTHER_OWNER, "rig", "Ashok Leyland 2518 rotary rig", "Truck-mounted rotary", 2450, 9.76, 77.93, "available", ""),
  resource(OTHER_OWNER, "rig", "Eicher Pro DTH rig", "Truck-mounted DTH 4.5”", 2600, 9.7, 77.86, "available", ""),
];
function resource(ownerId, type, name, vehicle, rate, lat, lng, status, notes) {
  return {
    resource_id: uuid(),
    owner_id: ownerId,
    resource_type: type,
    name,
    status,
    notes,
    lat,
    lng,
    hourly_rate: rate ? money(rate) : null,
    vehicle_type: vehicle || null,
    created_at: iso(now - 30 * DAY),
  };
}

const jobs = [];
const quotations = [];
const bookings = [];
const payments = [];
const completions = [];

function seedJob({ status, jobType, lat, lng, ageDays, customerId = CUSTOMER.id }) {
  const job = {
    job_id: uuid(),
    customer_id: customerId,
    status,
    job_type: jobType,
    location: { lat, lng },
    created_at: iso(now - ageDays * DAY),
  };
  jobs.push(job);
  return job;
}

const activeJob = seedJob({ status: "customer_approval", jobType: "agricultural", lat: 9.8201, lng: 77.9845, ageDays: 1 });
seedJob({ status: "lead", jobType: "residential", lat: 9.8225, lng: 77.9878, ageDays: 0.1 });
seedJob({ status: "estimation", jobType: "commercial", lat: 9.7189, lng: 77.8981, ageDays: 2, customerId: uuid() });
const drillingJob = seedJob({ status: "drilling", jobType: "agricultural", lat: 9.79, lng: 77.95, ageDays: 6, customerId: uuid() });
const closedJob = seedJob({ status: "service_history", jobType: "residential", lat: 9.83, lng: 77.98, ageDays: 40 });

function quoteFor(job, { version = 1, status = "draft" } = {}) {
  const rule = pricingRules.find((r) => r.job_type === job.job_type);
  const matched = areaFor(job.location.lat, job.location.lng);
  const depth = matched ? matched.estimated_water_depth_ft : rule.assumed_depth_ft;
  const band = matched ? matched.confidence_band_ft : rule.depth_confidence_band_ft;
  const items = [
    { label: "Drilling", amount: money(rule.base_rate_per_ft * depth) },
    { label: "Casing", amount: money(rule.casing_rate_per_ft * depth) },
    { label: "Labour", amount: money(rule.labour_flat_fee) },
    { label: "Transport", amount: money(rule.transport_flat_fee) },
    { label: "Equipment", amount: money(rule.equipment_flat_fee) },
    { label: "Installation", amount: money(rule.installation_flat_fee) },
  ];
  const subtotal = items.reduce((sum, i) => sum + Number(i.amount), 0);
  const margin = (subtotal * rule.margin_percent) / 100;
  const total = Math.max(subtotal + margin, rule.minimum_job_charge);
  const q = {
    quotation_id: uuid(),
    job_id: job.job_id,
    customer_id: job.customer_id,
    version,
    status,
    estimated_depth_range: {
      min_ft: Math.round(depth - band),
      max_ft: Math.round(depth + band),
      confidence: matched ? (band <= 60 ? "high" : "medium") : "low",
    },
    line_items: items,
    subtotal: money(subtotal),
    margin_amount: money(margin),
    minimum_charge_applied: subtotal + margin < rule.minimum_job_charge,
    total_estimate: money(total),
    depth_overage_rate_per_ft: money(rule.depth_overage_rate_per_ft),
    created_at: iso(now - DAY),
  };
  quotations.push(q);
  return q;
}

quoteFor(activeJob);
const drillingQuote = quoteFor(drillingJob, { status: "approved" });
const closedQuote = quoteFor(closedJob, { status: "approved" });

bookings.push({
  booking_id: uuid(),
  resource_id: resources[0].resource_id,
  owner_id: OWNER.id,
  contractor_id: CONTRACTOR.id,
  job_id: activeJob.job_id,
  status: "pending",
  message: "Need the rig on site by Monday morning, 2 days work.",
  created_at: iso(now - 0.2 * DAY),
  responded_at: null,
});
bookings.push({
  booking_id: uuid(),
  resource_id: resources[2].resource_id,
  owner_id: OWNER.id,
  contractor_id: CONTRACTOR.id,
  job_id: drillingJob.job_id,
  status: "accepted",
  message: null,
  created_at: iso(now - 5 * DAY),
  responded_at: iso(now - 5 * DAY),
});

payments.push({
  payment_id: uuid(),
  job_id: drillingJob.job_id,
  quotation_id: drillingQuote.quotation_id,
  amount: drillingQuote.total_estimate,
  status: "completed",
  razorpay_order_id: "order_demo123",
  razorpay_payment_id: "pay_demo456",
  created_at: iso(now - 4 * DAY),
});

completions.push({
  job_id: closedJob.job_id,
  actual_depth_ft: 468,
  actual_cost: money(Number(closedQuote.total_estimate) + 1750),
  quoted_total: closedQuote.total_estimate,
  variance: money(1750),
  depth_overage_ft: 0,
  depth_overage_charge: money(0),
  completed_at: iso(now - 35 * DAY),
});

// ---------------------------------------------------------------- helpers

function areaFor(lat, lng) {
  return serviceAreas.find((a) => haversine(lat, lng, a.center_lat, a.center_lng) <= a.radius_km) || null;
}

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(lat2 - lat1);
  const dLng = rad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

const STAGES = [
  "lead", "site_location", "requirement", "estimation", "price_calculation",
  "quotation", "customer_approval", "booking", "resource_allocation",
  "drilling", "progress", "completion", "payment", "service_history",
];

function ok(body, status = 200) {
  // A duck-typed stand-in for Response rather than `new Response(...)`:
  // React Native does ship a whatwg-fetch polyfill with Response on it,
  // but the only consumers of this object are services/platform.js and
  // services/auth.js, which use exactly these three members - so there is
  // nothing to gain from depending on the global being there.
  const text = JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(text),
    text: async () => text,
  };
}

function fail(status, code, message) {
  return ok({ error: { code, message, trace_id: "demo" } }, status);
}

function userFrom(headers) {
  const auth = headers?.Authorization || headers?.authorization || "";
  const raw = auth.replace("Bearer ", "").split(".")[1];
  if (!raw) return null;
  try {
    const payload = JSON.parse(b64decode(raw.replace(/-/g, "+").replace(/_/g, "/")));
    return users.find((u) => u.id === payload.sub) || { id: payload.sub, role: payload.role, email: payload.email };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------- routes

async function handle(method, path, body, headers) {
  const me = userFrom(headers);
  const seg = path.split("/").filter(Boolean); // ["v1", "jobs", ":id", ...]

  // --- auth
  if (path === "/v1/auth/register" && method === "POST") {
    const existing = users.find((u) => u.email === body.email);
    const user = existing || { id: uuid(), email: body.email, role: body.role };
    if (!existing) users.push(user);
    return ok({ access_token: token(user), role: user.role }, 201);
  }
  if (path === "/v1/auth/login" && method === "POST") {
    const user = users.find((u) => u.email.toLowerCase() === String(body.email).toLowerCase());
    if (!user) return fail(401, "INVALID_CREDENTIALS", "No demo account with that email. Try selvi@demo.in, senthil@demo.in or murugan@demo.in.");
    return ok({ access_token: token(user), role: user.role });
  }

  if (!me) return fail(401, "MISSING_TOKEN", "Authorization token is required.");

  // --- jobs
  if (path === "/v1/jobs" && method === "POST") {
    const job = {
      job_id: uuid(),
      customer_id: me.id,
      status: "lead",
      job_type: body.job_type,
      location: body.location,
      created_at: iso(Date.now()),
    };
    jobs.unshift(job);
    return ok(job, 201);
  }
  if (path === "/v1/jobs" && method === "GET") {
    const visible = me.role === "customer" ? jobs.filter((j) => j.customer_id === me.id) : jobs;
    return ok([...visible].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)));
  }
  if (seg[1] === "jobs" && seg.length === 3 && method === "GET") {
    const job = jobs.find((j) => j.job_id === seg[2]);
    return job ? ok(job) : fail(404, "JOB_NOT_FOUND", "No job with this ID exists.");
  }
  if (seg[1] === "jobs" && seg[3] === "status" && method === "PATCH") {
    const job = jobs.find((j) => j.job_id === seg[2]);
    if (!job) return fail(404, "JOB_NOT_FOUND", "No job with this ID exists.");
    const expected = STAGES[STAGES.indexOf(job.status) + 1];
    if (body.status !== expected) {
      return fail(400, "INVALID_TRANSITION", `Cannot move from '${job.status}' to '${body.status}' - the only allowed next state is '${expected}'.`);
    }
    job.status = body.status;
    return ok(job);
  }
  if (seg[1] === "jobs" && seg[3] === "completion" && method === "POST") {
    const job = jobs.find((j) => j.job_id === seg[2]);
    if (job.status !== "completion") return fail(400, "NOT_AT_COMPLETION", "Job is not at completion status.");
    if (completions.find((c) => c.job_id === job.job_id)) return fail(409, "ALREADY_COMPLETED", "Completion already recorded for this job.");
    const quote = latestQuote(job.job_id);
    const overage = Math.max(0, body.actual_depth_ft - (quote?.estimated_depth_range.max_ft || 0));
    const record = {
      job_id: job.job_id,
      actual_depth_ft: body.actual_depth_ft,
      actual_cost: money(body.actual_cost),
      quoted_total: quote ? quote.total_estimate : money(0),
      variance: money(body.actual_cost - Number(quote?.total_estimate || 0)),
      depth_overage_ft: overage,
      depth_overage_charge: money(overage * Number(quote?.depth_overage_rate_per_ft || 0)),
      completed_at: iso(Date.now()),
    };
    completions.push(record);
    return ok(record, 201);
  }
  if (seg[1] === "jobs" && seg[3] === "completion" && seg[4] === "result" && method === "GET") {
    const record = completions.find((c) => c.job_id === seg[2]);
    return record ? ok(record) : fail(404, "NO_COMPLETION", "No completion record for this job yet.");
  }

  // --- pricing rules
  if (path === "/v1/pricing-rules" && method === "GET") {
    return ok(pricingRules.filter((r) => r.contractor_id === me.id || me.role !== "contractor"));
  }
  if (path === "/v1/pricing-rules" && method === "POST") {
    const idx = pricingRules.findIndex((r) => r.job_type === body.job_type && r.contractor_id === me.id);
    const rule = { ...body, id: idx >= 0 ? pricingRules[idx].id : uuid(), contractor_id: me.id };
    if (idx >= 0) pricingRules[idx] = rule;
    else pricingRules.push(rule);
    return ok(rule, 201);
  }

  // --- quotations
  if (path === "/v1/quotations" && method === "POST") {
    const job = jobs.find((j) => j.job_id === body.job_id);
    const rule = pricingRules.find((r) => r.job_type === job.job_type && r.contractor_id === me.id);
    if (!rule) return fail(400, "PRICING_RULE_MISSING", `No pricing rule for ${job.job_type} jobs.`);
    return ok(quoteFor(job), 201);
  }
  if (seg[1] === "quotations" && seg[2] === "job" && seg[4] === "latest" && method === "GET") {
    const q = latestQuote(seg[3]);
    return q ? ok(q) : fail(404, "QUOTATION_NOT_FOUND", "No quotation for this job yet.");
  }
  if (seg[1] === "quotations" && seg.length === 3 && method === "PATCH") {
    const current = quotations.find((q) => q.quotation_id === seg[2]);
    const next = {
      ...current,
      quotation_id: uuid(),
      version: current.version + 1,
      status: "draft",
      line_items: body.line_items.map((i) => ({ label: i.label, amount: money(i.amount) })),
      subtotal: money(body.line_items.reduce((sum, i) => sum + Number(i.amount), 0)),
      total_estimate: money(body.total_estimate),
      created_at: iso(Date.now()),
    };
    quotations.push(next);
    return ok(next, 201);
  }
  if (seg[1] === "quotations" && (seg[3] === "approve" || seg[3] === "reject") && method === "POST") {
    const q = quotations.find((x) => x.quotation_id === seg[2]);
    q.status = seg[3] === "approve" ? "approved" : "rejected";
    return ok(q);
  }

  // --- resources
  if (path === "/v1/resources" && method === "GET") {
    return ok(resources.filter((r) => r.owner_id === me.id));
  }
  if (path === "/v1/resources" && method === "POST") {
    const created = {
      resource_id: uuid(),
      owner_id: me.id,
      resource_type: body.resource_type,
      name: body.name,
      status: "available",
      notes: body.notes || "",
      lat: body.lat ?? null,
      lng: body.lng ?? null,
      hourly_rate: body.hourly_rate ? money(body.hourly_rate) : null,
      vehicle_type: body.vehicle_type || null,
      created_at: iso(Date.now()),
    };
    resources.push(created);
    return ok(created, 201);
  }
  if (seg[1] === "resources" && seg.length === 3 && method === "PATCH") {
    const r = resources.find((x) => x.resource_id === seg[2]);
    Object.assign(r, body, { hourly_rate: body.hourly_rate ? money(body.hourly_rate) : r.hourly_rate });
    return ok(r);
  }
  if (path === "/v1/resources/match" && method === "POST") {
    const found = resources
      .filter((r) => r.status === "available" && r.lat !== null)
      .filter((r) => !body.resource_type || r.resource_type === body.resource_type)
      .map((r) => ({
        resource_id: r.resource_id,
        name: r.name,
        resource_type: r.resource_type,
        status: r.status,
        hourly_rate: r.hourly_rate,
        vehicle_type: r.vehicle_type,
        distance_km: Number(haversine(body.lat, body.lng, r.lat, r.lng).toFixed(1)),
      }))
      .sort((a, b) => a.distance_km - b.distance_km)
      .slice(0, body.max_results || 5);
    return ok(found);
  }

  // --- bookings
  if (path === "/v1/bookings" && method === "POST") {
    const target = resources.find((r) => r.resource_id === body.resource_id);
    if (bookings.find((b) => b.resource_id === body.resource_id && ["pending", "accepted"].includes(b.status))) {
      return fail(409, "RESOURCE_ALREADY_REQUESTED", "This resource already has an active request.");
    }
    const booking = {
      booking_id: uuid(),
      resource_id: body.resource_id,
      owner_id: target.owner_id,
      contractor_id: me.id,
      job_id: body.job_id || null,
      status: "pending",
      message: body.message || null,
      created_at: iso(Date.now()),
      responded_at: null,
    };
    bookings.push(booking);
    return ok(booking, 201);
  }
  if (path === "/v1/bookings" && method === "GET") {
    const mine = me.role === "resource_owner"
      ? bookings.filter((b) => b.owner_id === me.id)
      : bookings.filter((b) => b.contractor_id === me.id);
    return ok([...mine].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)));
  }
  if (seg[1] === "bookings" && (seg[3] === "accept" || seg[3] === "reject") && method === "POST") {
    const booking = bookings.find((b) => b.booking_id === seg[2]);
    if (booking.status !== "pending") return fail(409, "ALREADY_RESOLVED", "This request was already answered.");
    booking.status = seg[3] === "accept" ? "accepted" : "rejected";
    booking.responded_at = iso(Date.now());
    if (seg[3] === "accept") {
      const r = resources.find((x) => x.resource_id === booking.resource_id);
      if (r) r.status = "reserved";
    }
    return ok(booking);
  }

  // --- service areas
  if (path === "/v1/service-areas" && method === "GET") return ok(serviceAreas);
  if (path === "/v1/service-areas" && method === "POST") {
    const idx = serviceAreas.findIndex((a) => a.name === body.name && a.district === body.district);
    const saved = { ...body, area_id: idx >= 0 ? serviceAreas[idx].area_id : uuid(), source: "contractor_estimate", updated_at: iso(Date.now()) };
    if (idx >= 0) serviceAreas[idx] = saved;
    else serviceAreas.push(saved);
    return ok(saved, 201);
  }
  if (path.startsWith("/v1/service-areas/lookup") && method === "GET") {
    const params = new URLSearchParams(path.split("?")[1] || "");
    const matched = areaFor(Number(params.get("lat")), Number(params.get("lng")));
    return matched ? ok(matched) : fail(404, "NO_SERVICE_AREA", "No configured service area covers this point.");
  }

  // --- payments
  if (path === "/v1/payments" && method === "GET") {
    const mine = me.role === "customer"
      ? payments.filter((p) => jobs.find((j) => j.job_id === p.job_id)?.customer_id === me.id)
      : payments;
    return ok(mine);
  }
  if (path === "/v1/payments" && method === "POST") {
    const existing = payments.find((p) => p.quotation_id === body.quotation_id);
    if (existing) return ok(existing, 201);
    const payment = {
      payment_id: uuid(),
      job_id: body.job_id,
      quotation_id: body.quotation_id,
      amount: body.amount,
      status: "pending",
      razorpay_order_id: null,
      razorpay_payment_id: null,
      created_at: iso(Date.now()),
    };
    payments.push(payment);
    return ok(payment, 201);
  }
  if (seg[1] === "payments" && seg[3] === "create-order" && method === "POST") {
    const payment = payments.find((p) => p.payment_id === seg[2]);
    payment.razorpay_order_id = `order_demo_${Date.now()}`;
    return ok({
      razorpay_order_id: payment.razorpay_order_id,
      razorpay_key_id: "rzp_test_demo",
      amount_paise: Math.round(Number(payment.amount) * 100),
      currency: "INR",
    });
  }
  if (seg[1] === "payments" && seg.length === 3 && method === "GET") {
    const payment = payments.find((p) => p.payment_id === seg[2]);
    return payment ? ok(payment) : fail(404, "PAYMENT_NOT_FOUND", "No payment with this ID.");
  }

  if (path.endsWith("/healthz")) return ok({ status: "ok" });
  return fail(404, "NOT_FOUND", `Demo backend has no route for ${method} ${path}`);
}

function latestQuote(jobId) {
  const forJob = quotations.filter((q) => q.job_id === jobId);
  return forJob.length ? forJob[forJob.length - 1] : null;
}

/** Marks a demo payment completed - stands in for Razorpay's signed webhook. */
export function completeDemoPayment(orderId) {
  const payment = payments.find((p) => p.razorpay_order_id === orderId);
  if (payment) {
    payment.status = "completed";
    payment.razorpay_payment_id = `pay_demo_${Date.now()}`;
  }
}

export function installMockApi() {
  if (global.__borewellDemoInstalled) return;
  global.__borewellDemoInstalled = true;
  const realFetch = global.fetch;
  global.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    if (!path.startsWith("/v1") && !path.endsWith("/healthz")) return realFetch(input, init);
    const method = (init.method || "GET").toUpperCase();
    const body = init.body ? JSON.parse(init.body) : undefined;
    const headers = init.headers || {};
    // A touch of latency so loading states are visible, like the real thing.
    await new Promise((r) => setTimeout(r, 180));
    try {
      return await handle(method, path, body, headers);
    } catch (err) {
      return fail(500, "DEMO_ERROR", err.message);
    }
  };
  console.info("Borewell demo mode: using the in-memory backend. Sign in with selvi@demo.in, senthil@demo.in or murugan@demo.in (any password).");
}

export const DEMO_ACCOUNTS = [
  { email: "selvi@demo.in", label: "Customer" },
  { email: "senthil@demo.in", label: "Contractor" },
  { email: "murugan@demo.in", label: "Rig owner" },
];
