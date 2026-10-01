/**
 * Hand-copied from apps/shared-ui/src/tokens.js - the same convention as
 * services/platform.js and services/auth.js in this folder (this app is
 * deliberately outside the npm workspace; see AGENTS.md). If the web
 * tokens change, re-sync this file by hand.
 *
 * Nothing here is web-specific: colours, spacing, the job-stage groupings
 * and the INR formatter are all plain JS, so the two apps stay visually
 * and behaviourally identical without a build step shared between them.
 */

export const colors = {
  ground: "#EDECE8",
  surface: "#FFFFFF",
  sunk: "#E6E4DE",
  line: "#DFDDD7",
  lineSoft: "#EBEAE5",
  ink: "#141619",
  ink2: "#454950",
  muted: "#7D8188",
  chrome: "#141619",
  chrome2: "#1F2226",
  chrome3: "#2C3036",
  onChromeMuted: "#A9ADB4",
  saffron: "#F0A73A",
  saffronSoft: "#FCEFD9",
  saffronInk: "#7A4A0E",
  green: "#2C7549",
  greenSoft: "#E3F0E6",
  red: "#A93C33",
  redSoft: "#F7E4E1",
  slate: "#2A2E34",
  slateSoft: "#E9EAEC",
  mapLand: "#E9E5DA",
};

// React Native has no webfont loading without a native build, so the
// closest stock faces are used instead of Archivo / IBM Plex Mono. Weights
// carry the design's character here; see the note in HOW-TO-RUN.md.
export const fonts = {
  body: undefined, // platform default (San Francisco / Roboto)
  mono: undefined,
};

export const radii = { sm: 10, md: 14, lg: 20, xl: 24, pill: 999 };
export const space = [0, 4, 8, 12, 16, 20, 24, 32, 40, 48];

// --- job lifecycle -------------------------------------------------------

// Mirrors platform-spine's job_state_machine.STATE_ORDER exactly. The
// backend is the only place the order is enforced - this list only drives
// display and the "advance to next stage" action.
export const JOB_STAGES = [
  "lead", "site_location", "requirement", "estimation", "price_calculation",
  "quotation", "customer_approval", "booking", "resource_allocation",
  "drilling", "progress", "completion", "payment", "service_history",
];

export const STAGE_LABELS = {
  lead: "Lead",
  site_location: "Site location",
  requirement: "Requirement",
  estimation: "Estimation",
  price_calculation: "Price calculation",
  quotation: "Quotation",
  customer_approval: "Customer approval",
  booking: "Booking",
  resource_allocation: "Resource allocation",
  drilling: "Drilling",
  progress: "Progress",
  completion: "Completion",
  payment: "Payment",
  service_history: "Service history",
};

// The 14 stages grouped into the phases the contractor filters by.
export const PHASES = [
  { key: "leads", label: "Leads", stages: ["lead", "site_location", "requirement"] },
  { key: "estimating", label: "Estimating", stages: ["estimation", "price_calculation"] },
  { key: "quoted", label: "Quoted", stages: ["quotation", "customer_approval"] },
  { key: "booked", label: "Booked", stages: ["booking", "resource_allocation"] },
  { key: "drilling", label: "Drilling", stages: ["drilling", "progress"] },
  { key: "closing", label: "Closing", stages: ["completion", "payment", "service_history"] },
];

// Simpler 5-step view shown to customers.
export const CUSTOMER_STEPS = [
  { label: "Requested", stages: ["lead", "site_location", "requirement", "estimation", "price_calculation"] },
  { label: "Quote", stages: ["quotation", "customer_approval"] },
  { label: "Booked", stages: ["booking", "resource_allocation"] },
  { label: "Drilling", stages: ["drilling", "progress"] },
  { label: "Done", stages: ["completion", "payment", "service_history"] },
];

export function stageIndex(status) {
  return JOB_STAGES.indexOf(status);
}

export function nextStage(status) {
  const i = stageIndex(status);
  return i >= 0 && i < JOB_STAGES.length - 1 ? JOB_STAGES[i + 1] : null;
}

export function phaseOf(status) {
  return PHASES.find((p) => p.stages.includes(status)) || PHASES[0];
}

export function customerStepIndex(status) {
  return CUSTOMER_STEPS.findIndex((s) => s.stages.includes(status));
}

// tone keys map to badge colours in each app
export function stageTone(status) {
  switch (phaseOf(status).key) {
    case "quoted": return "saffron";
    case "booked": return "green";
    case "drilling": return "slate";
    case "closing": return status === "service_history" ? "green" : "red";
    default: return "neutral";
  }
}

export const JOB_TYPES = [
  { value: "residential", label: "Home", long: "Residential", hint: "Drinking water for a house" },
  { value: "agricultural", label: "Farm", long: "Agricultural", hint: "Irrigation for crops or orchards" },
  { value: "commercial", label: "Business", long: "Commercial", hint: "Shop, mill, hospital or school" },
];

export function jobTypeLabel(value, long = false) {
  const t = JOB_TYPES.find((j) => j.value === value);
  if (!t) return value;
  return long ? t.long : t.label;
}

export const RESOURCE_TYPES = [
  { value: "rig", label: "Rig" },
  { value: "equipment", label: "Equipment" },
  { value: "labour", label: "Labour" },
];

export const RESOURCE_STATUS_LABELS = {
  available: "Available",
  reserved: "Reserved",
  assigned: "Assigned",
  in_use: "In use",
  returned: "Returned",
};

export function resourceStatusTone(status) {
  return { available: "green", reserved: "saffron", assigned: "saffron", in_use: "slate", returned: "neutral" }[status] || "neutral";
}

export const BOOKING_STATUS_LABELS = {
  pending: "Pending",
  accepted: "Accepted",
  rejected: "Declined",
  cancelled: "Cancelled",
};

export function bookingTone(status) {
  return { pending: "saffron", accepted: "green", rejected: "red", cancelled: "neutral" }[status] || "neutral";
}

// --- formatting ----------------------------------------------------------

/**
 * Indian-grouped rupee string from the API's decimal string (e.g.
 * "97750.00" -> "₹97,750"). Display only - never send the result back to
 * the API (see platform.js header on exact decimal strings).
 */
export function formatInr(value, { paise = false } = {}) {
  if (value === null || value === undefined || value === "") return "—";
  const str = String(value);
  const negative = str.trim().startsWith("-");
  const [intPartRaw, fracRaw = ""] = str.replace("-", "").split(".");
  const intPart = intPartRaw.replace(/\D/g, "") || "0";
  const last3 = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const grouped = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3 : last3;
  const frac = paise && fracRaw && Number(fracRaw) !== 0 ? "." + fracRaw.padEnd(2, "0").slice(0, 2) : "";
  return `${negative ? "−" : ""}₹${grouped}${frac}`;
}

export function shortId(uuid) {
  return uuid ? `JB-${uuid.slice(0, 4).toUpperCase()}` : "";
}

export function formatRelative(iso, now = Date.now()) {
  if (!iso) return "";
  const t = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime();
  const mins = Math.round((now - t) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days} d ago`;
  return new Date(t).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function formatCoords(lat, lng) {
  if (lat === null || lat === undefined || lng === null || lng === undefined) return "";
  return `${Number(lat).toFixed(4)}° N, ${Number(lng).toFixed(4)}° E`;
}

// Madurai district centre - default map view for the pilot.
export const PILOT_CENTER = { lat: 9.9252, lng: 78.1198 };
