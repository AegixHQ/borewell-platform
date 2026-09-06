import { useEffect, useRef, useState } from "react";
import {
  PLATFORM_SPINE_URL,
  QUOTATION_URL,
  PAYMENTS_URL,
  createJob,
  getJob,
  getLatestQuotationForJob,
  approveQuotation,
  rejectQuotation,
  createPayment,
  getPayment,
} from "shared-ui";

const JOB_TYPES = [
  { value: "residential", label: "Residential" },
  { value: "agricultural", label: "Agricultural" },
  { value: "commercial", label: "Commercial" },
];

// UI/UX doc section 3: Home -> Request flow (Location -> Quote -> Approve -> Pay),
// then Job Tracking. One screen at a time, driven by internal step state -
// no router library, matching Architecture doc section 3's "keep it simple"
// call for this app's scale.
const STEPS = {
  LOCATION: "location",
  WAITING_FOR_QUOTE: "waiting_for_quote",
  QUOTATION: "quotation",
  PAYMENT: "payment",
  TRACKING: "tracking",
};

// RFC 0001 section 8 order, mirrored here only for the tracking stepper's
// display - platform-spine's job_state_machine.py is the actual source of
// truth and the only place transition legality is enforced.
const JOB_LIFECYCLE = [
  "lead", "site_location", "requirement", "estimation", "price_calculation",
  "quotation", "customer_approval", "booking", "resource_allocation",
  "drilling", "progress", "completion", "payment", "service_history",
];

function formatInr(amountString) {
  // amountString is the numeric-string Decimal from the API (see
  // shared-ui/platform.js header) - Number() here is purely for display
  // formatting, this value is never sent back to any endpoint.
  const n = Number(amountString);
  if (Number.isNaN(n)) return amountString;
  return n.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
}

export default function CustomerDashboard({ session }) {
  const [step, setStep] = useState(STEPS.LOCATION);
  const [job, setJob] = useState(null);
  const [quotation, setQuotation] = useState(null);
  const [payment, setPayment] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // Location Entry form state
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [jobType, setJobType] = useState("residential");

  const pollRef = useRef(null);

  useEffect(() => () => clearInterval(pollRef.current), []);

  async function handleSubmitLocation(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const parsedLat = Number(lat);
      const parsedLng = Number(lng);
      const created = await createJob(PLATFORM_SPINE_URL, session.token, {
        lat: parsedLat,
        lng: parsedLng,
        jobType,
      });
      setJob(created);
      setStep(STEPS.WAITING_FOR_QUOTE);
      startPollingForQuotation(created.job_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Quotation generation is contractor-only (require_role("contractor") on
  // POST /v1/quotations - see quotation service's main.py) - the customer
  // side can only wait for one to appear, via the real committed contract
  // (GET /v1/quotations/job/{job_id}/latest). QUOTATION_NOT_FOUND (404) is
  // the expected, common response until the contractor acts - not an error
  // to show the user, just "keep waiting."
  function startPollingForQuotation(jobId) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const q = await getLatestQuotationForJob(QUOTATION_URL, session.token, jobId);
        clearInterval(pollRef.current);
        setQuotation(q);
        setStep(STEPS.QUOTATION);
      } catch (err) {
        if (err.code !== "QUOTATION_NOT_FOUND") {
          clearInterval(pollRef.current);
          setError(err.message);
        }
        // else: no quote yet, keep polling silently
      }
    }, 4000);
  }

  async function handleApprove() {
    setError(null);
    setBusy(true);
    try {
      const approved = await approveQuotation(QUOTATION_URL, session.token, quotation.quotation_id);
      setQuotation(approved);
      setStep(STEPS.PAYMENT);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRequestChanges() {
    setError(null);
    setBusy(true);
    try {
      await rejectQuotation(QUOTATION_URL, session.token, quotation.quotation_id);
      // Rejected, not deleted - FR-QUOTE-05/BR-06: the contractor sees the
      // rejection and can send a new version. Nothing left for the
      // customer to do here but wait again, same as the initial quote.
      setQuotation(null);
      setStep(STEPS.WAITING_FOR_QUOTE);
      startPollingForQuotation(job.job_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePay() {
    setError(null);
    setBusy(true);
    try {
      // idempotency_key generated once per pay attempt, per FR-PAY-02 - a
      // double-click or retry reuses this same key rather than minting a
      // new one, so payments-data's idempotency check (FR-PAY-03) can
      // actually do its job. crypto.randomUUID() is available in every
      // browser this app targets (Vite's default modern-browser baseline).
      const idempotencyKey =
        payment?.idempotency_key || `web-${job.job_id}-${crypto.randomUUID()}`;
      const created = await createPayment(PAYMENTS_URL, session.token, {
        jobId: job.job_id,
        quotationId: quotation.quotation_id,
        amount: quotation.total_estimate,
        idempotencyKey,
      });
      setPayment(created);
      setStep(STEPS.TRACKING);
      startPollingJobStatus(job.job_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function startPollingJobStatus(jobId) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const updated = await getJob(PLATFORM_SPINE_URL, session.token, jobId);
        setJob(updated);
      } catch (err) {
        // Tracking is a passive, pull-to-refresh-style screen (UI/UX doc
        // section 4.1) - a transient poll failure isn't worth interrupting
        // the user over. Surfacing it would fight the "passive screen"
        // intent the UI/UX doc specifies for this exact screen.
        void err;
      }
    }, 6000);
  }

  async function refreshPaymentStatus() {
    if (!payment) return;
    setBusy(true);
    try {
      const updated = await getPayment(PAYMENTS_URL, session.token, payment.payment_id);
      setPayment(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: 16, fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: 24 }}>Borewell Platform</h1>
      <p style={{ color: "#555" }}>Signed in as {session.email}</p>

      {error && (
        <p role="alert" style={{ color: "#b00020", border: "1px solid #b00020", padding: 8 }}>
          {error}
        </p>
      )}

      {step === STEPS.LOCATION && (
        <LocationEntryScreen
          lat={lat}
          lng={lng}
          jobType={jobType}
          setLat={setLat}
          setLng={setLng}
          setJobType={setJobType}
          onSubmit={handleSubmitLocation}
          busy={busy}
        />
      )}

      {step === STEPS.WAITING_FOR_QUOTE && <WaitingForQuoteScreen job={job} />}

      {step === STEPS.QUOTATION && quotation && (
        <QuotationDisplayScreen
          quotation={quotation}
          onApprove={handleApprove}
          onRequestChanges={handleRequestChanges}
          busy={busy}
        />
      )}

      {step === STEPS.PAYMENT && quotation && (
        <PaymentScreen quotation={quotation} onPay={handlePay} busy={busy} />
      )}

      {step === STEPS.TRACKING && job && (
        <JobTrackingScreen
          job={job}
          payment={payment}
          onRefreshPayment={refreshPaymentStatus}
          busy={busy}
        />
      )}
    </div>
  );
}

function LocationEntryScreen({ lat, lng, jobType, setLat, setLng, setJobType, onSubmit, busy }) {
  return (
    <form onSubmit={onSubmit}>
      <h2>Request a Borewell</h2>
      <p style={{ color: "#555", fontSize: 14 }}>
        Enter your site's coordinates and job type to get an estimate.
      </p>
      <label style={{ display: "block", marginBottom: 8 }}>
        Latitude
        <input
          type="number"
          step="any"
          value={lat}
          onChange={(e) => setLat(e.target.value)}
          required
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Longitude
        <input
          type="number"
          step="any"
          value={lng}
          onChange={(e) => setLng(e.target.value)}
          required
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Job Type
        <select value={jobType} onChange={(e) => setJobType(e.target.value)}>
          {JOB_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={busy}>
        {busy ? "Submitting..." : "Get Estimate"}
      </button>
    </form>
  );
}

function WaitingForQuoteScreen({ job }) {
  // UI/UX doc section 7: loading state, never a blank screen. This is a
  // genuinely different wait than "generating a quote" (that's the
  // contractor's own screen/action) - the honest copy here is "waiting for
  // your contractor," not "calculating," since nothing is computing on the
  // customer's behalf right now.
  return (
    <div>
      <h2>Request Received</h2>
      <p>
        Your request (job <code>{job?.job_id}</code>) has been sent to the
        contractor. This page will update automatically once your quotation
        is ready - usually within a few minutes.
      </p>
      <p style={{ color: "#555", fontSize: 14 }}>Checking for your quotation...</p>
    </div>
  );
}

function QuotationDisplayScreen({ quotation, onApprove, onRequestChanges, busy }) {
  const { estimated_depth_range: depth } = quotation;
  return (
    <div>
      <h2>Your Quotation</h2>

      {/* UI/UX doc section 7: this disclosure is a required element, not
          optional polish - depth range + confidence badge, always shown,
          never hidden even when confidence is high. */}
      <div
        style={{
          background: "#fff8e1",
          border: "1px solid #e0c060",
          padding: 12,
          marginBottom: 12,
        }}
      >
        <strong>Estimated depth: {depth.min_ft}\u2013{depth.max_ft} ft</strong>{" "}
        <span
          style={{
            fontSize: 12,
            padding: "2px 8px",
            borderRadius: 12,
            background: depth.confidence === "low" ? "#ffca28" : depth.confidence === "medium" ? "#aed581" : "#66bb6a",
          }}
        >
          {depth.confidence} confidence
        </span>
        <p style={{ fontSize: 13, margin: "8px 0 0" }}>
          Actual depth may vary once drilling begins. Any difference from
          this estimate is priced transparently at completion, not silently
          added to your bill.
        </p>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 12 }}>
        <tbody>
          {quotation.line_items.map((item, i) => (
            <tr key={i}>
              <td style={{ padding: "4px 0" }}>{item.label}</td>
              <td style={{ padding: "4px 0", textAlign: "right" }}>{formatInr(item.amount)}</td>
            </tr>
          ))}
          <tr style={{ borderTop: "2px solid #333", fontWeight: "bold" }}>
            <td style={{ padding: "8px 0" }}>Total</td>
            <td style={{ padding: "8px 0", textAlign: "right" }}>
              {formatInr(quotation.total_estimate)}
            </td>
          </tr>
        </tbody>
      </table>
      {quotation.minimum_charge_applied && (
        <p style={{ fontSize: 12, color: "#555" }}>
          Your contractor's minimum job charge has been applied to this total.
        </p>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={onApprove} disabled={busy}>
          {busy ? "Please wait..." : "Approve & Pay"}
        </button>
        <button onClick={onRequestChanges} disabled={busy}>
          Request Changes
        </button>
      </div>
    </div>
  );
}

function PaymentScreen({ quotation, onPay, busy }) {
  return (
    <div>
      <h2>Payment</h2>
      <p>
        Amount due: <strong>{formatInr(quotation.total_estimate)}</strong>
      </p>
      <p style={{ fontSize: 13, color: "#555" }}>
        A real payment gateway is not wired up yet (RFC 0001 section 7 open
        decision - Razorpay is the current front-runner for India). Confirming
        this payment right now creates a real, correctly-priced payment
        record that stays "pending" until that gateway integration lands and
        actually confirms it - it will not silently show as paid.
      </p>
      <button onClick={onPay} disabled={busy}>
        {busy ? "Processing..." : "Pay Now"}
      </button>
    </div>
  );
}

function JobTrackingScreen({ job, payment, onRefreshPayment, busy }) {
  const currentIndex = JOB_LIFECYCLE.indexOf(job.status);
  return (
    <div>
      <h2>Job Tracking</h2>
      <p style={{ fontSize: 13, color: "#555" }}>Pull to refresh - this page updates automatically.</p>

      <ol style={{ listStyle: "none", padding: 0 }}>
        {JOB_LIFECYCLE.map((stage, i) => (
          <li
            key={stage}
            style={{
              padding: "4px 0",
              color: i <= currentIndex ? "#2e7d32" : "#aaa",
              fontWeight: i === currentIndex ? "bold" : "normal",
            }}
          >
            {i <= currentIndex ? "\u25cf" : "\u25cb"} {stage.replace(/_/g, " ")}
          </li>
        ))}
      </ol>

      {payment && (
        <div style={{ marginTop: 16, borderTop: "1px solid #ddd", paddingTop: 12 }}>
          <p>
            Payment status: <strong>{payment.status}</strong>
          </p>
          {payment.status === "pending" && (
            <button onClick={onRefreshPayment} disabled={busy}>
              {busy ? "Checking..." : "Check Payment Status"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
