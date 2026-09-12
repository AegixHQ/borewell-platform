import { useEffect, useState } from "react";
import {
  PLATFORM_SPINE_URL,
  QUOTATION_URL,
  RESOURCE_NETWORK_URL,
  listMyJobs,
  updateJobStatus,
  upsertPricingRule,
  listPricingRules,
  generateQuotation,
  getLatestQuotationForJob,
  matchResources,
  createBookingRequest,
  listBookings,
} from "shared-ui";

const JOB_TYPES = ["residential", "agricultural", "commercial"];

// RFC 0001 section 8 order - the only place this is actually enforced is
// platform-spine's job_state_machine.py; this list drives the "advance to
// next stage" button, not the legality check itself.
const JOB_LIFECYCLE = [
  "lead", "site_location", "requirement", "estimation", "price_calculation",
  "quotation", "customer_approval", "booking", "resource_allocation",
  "drilling", "progress", "completion", "payment", "service_history",
];

const PRICING_FIELDS = [
  { key: "base_rate_per_ft", label: "Base rate per ft (INR)" },
  { key: "casing_rate_per_ft", label: "Casing rate per ft (INR)" },
  { key: "labour_flat_fee", label: "Labour flat fee (INR)" },
  { key: "transport_flat_fee", label: "Transport flat fee (INR)" },
  { key: "equipment_flat_fee", label: "Equipment flat fee (INR)" },
  { key: "installation_flat_fee", label: "Installation flat fee (INR)" },
  { key: "margin_percent", label: "Margin (%)" },
  { key: "minimum_job_charge", label: "Minimum job charge (INR)" },
  { key: "assumed_depth_ft", label: "Assumed depth (ft)" },
  { key: "depth_confidence_band_ft", label: "Depth confidence band (\u00b1 ft)" },
  { key: "depth_overage_rate_per_ft", label: "Depth overage rate per ft (INR)" },
];

const EMPTY_RULE = PRICING_FIELDS.reduce((acc, f) => ({ ...acc, [f.key]: "" }), {});

export default function ContractorDashboard({ session }) {
  const [view, setView] = useState("jobs"); // "jobs" | "pricing"
  const [jobs, setJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    refreshJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshJobs() {
    setLoadingJobs(true);
    setError(null);
    try {
      const list = await listMyJobs(PLATFORM_SPINE_URL, session.token);
      setJobs(list);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingJobs(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16, fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: 24 }}>Contractor Dashboard</h1>
      <p style={{ color: "#555" }}>Signed in as {session.email}</p>

      <nav style={{ marginBottom: 16 }}>
        <button onClick={() => setView("jobs")} disabled={view === "jobs"}>
          Leads &amp; Jobs
        </button>{" "}
        <button onClick={() => setView("pricing")} disabled={view === "pricing"}>
          Pricing Rules
        </button>
      </nav>

      {error && (
        <p role="alert" style={{ color: "#b00020", border: "1px solid #b00020", padding: 8 }}>
          {error}
        </p>
      )}

      {view === "pricing" && <PricingRulesScreen session={session} />}

      {view === "jobs" &&
        (loadingJobs ? (
          <p>Loading your jobs...</p>
        ) : jobs.length === 0 ? (
          // UI/UX doc section 7: friendly empty state, not a blank list.
          <p>
            No leads yet. Once a customer submits a request, it will appear
            here automatically.
          </p>
        ) : (
          <JobListScreen
            session={session}
            jobs={jobs}
            onJobsChanged={refreshJobs}
            setError={setError}
          />
        ))}
    </div>
  );
}

function PricingRulesScreen({ session }) {
  const [jobType, setJobType] = useState("residential");
  const [rule, setRule] = useState(EMPTY_RULE);
  const [existingRules, setExistingRules] = useState([]);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    refreshRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshRules() {
    try {
      const list = await listPricingRules(QUOTATION_URL, session.token);
      setExistingRules(list);
    } catch (err) {
      setError(err.message);
    }
  }

  function handleField(key, value) {
    setSaved(false);
    setRule((r) => ({ ...r, [key]: value }));
  }

  async function handleSave(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const numericRule = Object.fromEntries(
        Object.entries(rule).map(([k, v]) => [k, Number(v)])
      );
      await upsertPricingRule(QUOTATION_URL, session.token, {
        job_type: jobType,
        ...numericRule,
      });
      setSaved(true);
      refreshRules();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const configuredTypes = new Set(existingRules.map((r) => r.job_type));

  return (
    <div>
      <h2>Pricing Rules</h2>
      {error && (
        <p role="alert" style={{ color: "#b00020", border: "1px solid #b00020", padding: 8 }}>
          {error}
        </p>
      )}
      <p style={{ fontSize: 13, color: "#555" }}>
        Configured for:{" "}
        {JOB_TYPES.map((t) => (
          <span key={t} style={{ marginRight: 8 }}>
            {t} {configuredTypes.has(t) ? "\u2705" : "\u2014 not set"}
          </span>
        ))}
      </p>

      <form onSubmit={handleSave}>
        <label style={{ display: "block", marginBottom: 8 }}>
          Job Type
          <select value={jobType} onChange={(e) => setJobType(e.target.value)}>
            {JOB_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        {PRICING_FIELDS.map((f) => (
          <label key={f.key} style={{ display: "block", marginBottom: 6, fontSize: 14 }}>
            {f.label}
            <input
              type="number"
              step="any"
              value={rule[f.key]}
              onChange={(e) => handleField(f.key, e.target.value)}
              required
              style={{ display: "block", width: "100%" }}
            />
          </label>
        ))}

        <button type="submit" disabled={busy}>
          {busy ? "Saving..." : "Save Rules"}
        </button>
        {saved && <span style={{ marginLeft: 8, color: "#2e7d32" }}>Saved.</span>}
      </form>
    </div>
  );
}

function JobListScreen({ session, jobs, onJobsChanged, setError }) {
  const [expandedJobId, setExpandedJobId] = useState(null);

  return (
    <div>
      <h2>Leads &amp; Jobs</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
            <th style={{ padding: 6 }}>Job</th>
            <th style={{ padding: 6 }}>Type</th>
            <th style={{ padding: 6 }}>Status</th>
            <th style={{ padding: 6 }}></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <JobRow
              key={job.job_id}
              session={session}
              job={job}
              expanded={expandedJobId === job.job_id}
              onToggle={() =>
                setExpandedJobId(expandedJobId === job.job_id ? null : job.job_id)
              }
              onJobsChanged={onJobsChanged}
              setError={setError}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JobRow({ session, job, expanded, onToggle, onJobsChanged, setError }) {
  return (
    <>
      <tr style={{ borderBottom: "1px solid #eee" }}>
        <td style={{ padding: 6 }}>
          <code style={{ fontSize: 12 }}>{job.job_id.slice(0, 8)}</code>
        </td>
        <td style={{ padding: 6 }}>{job.job_type}</td>
        <td style={{ padding: 6 }}>{job.status.replace(/_/g, " ")}</td>
        <td style={{ padding: 6 }}>
          <button onClick={onToggle}>{expanded ? "Hide" : "Manage"}</button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={4} style={{ padding: "0 6px 12px" }}>
            <JobDetailPanel
              session={session}
              job={job}
              onJobsChanged={onJobsChanged}
              setError={setError}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function JobDetailPanel({ session, job, onJobsChanged, setError }) {
  const [quotation, setQuotation] = useState(undefined); // undefined = not checked yet
  const [checkingQuote, setCheckingQuote] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    checkExistingQuote();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.job_id]);

  async function checkExistingQuote() {
    setCheckingQuote(true);
    try {
      const q = await getLatestQuotationForJob(QUOTATION_URL, session.token, job.job_id);
      setQuotation(q);
    } catch (err) {
      if (err.code === "QUOTATION_NOT_FOUND") {
        setQuotation(null);
      } else {
        setError(err.message);
      }
    } finally {
      setCheckingQuote(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      // UI/UX doc section 7: this is the one error state the doc names
      // exactly - "Set a base drilling rate before generating quotes" -
      // PRICING_RULE_MISSING is exactly that case, surfaced verbatim
      // rather than a generic failure message.
      const q = await generateQuotation(QUOTATION_URL, session.token, {
        jobId: job.job_id,
        lat: job.location.lat,
        lng: job.location.lng,
        jobType: job.job_type,
      });
      setQuotation(q);
    } catch (err) {
      if (err.code === "PRICING_RULE_MISSING") {
        setError(
          `Set your pricing rule for "${job.job_type}" jobs (Pricing Rules tab) before generating a quote.`
        );
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleAdvanceStatus() {
    const currentIndex = JOB_LIFECYCLE.indexOf(job.status);
    const next = JOB_LIFECYCLE[currentIndex + 1];
    if (!next) return;
    setBusy(true);
    setError(null);
    try {
      await updateJobStatus(PLATFORM_SPINE_URL, session.token, job.job_id, next);
      onJobsChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const currentIndex = JOB_LIFECYCLE.indexOf(job.status);
  const nextStage = JOB_LIFECYCLE[currentIndex + 1];

  return (
    <div style={{ background: "#fafafa", border: "1px solid #eee", padding: 12 }}>
      <p style={{ fontSize: 13 }}>
        Location: {job.location.lat}, {job.location.lng}
      </p>

      {checkingQuote ? (
        <p style={{ fontSize: 13, color: "#555" }}>Checking for an existing quotation...</p>
      ) : quotation ? (
        <div style={{ fontSize: 13, marginBottom: 8 }}>
          <p>
            Quotation v{quotation.version} - <strong>{quotation.status}</strong> - total{" "}
            {quotation.total_estimate} INR
          </p>
        </div>
      ) : (
        <button onClick={handleGenerate} disabled={busy}>
          {busy ? "Generating..." : "Send Quotation"}
        </button>
      )}

      {nextStage && (
        <div style={{ marginTop: 8 }}>
          <button onClick={handleAdvanceStatus} disabled={busy}>
            {busy ? "Updating..." : `Advance to "${nextStage.replace(/_/g, " ")}"`}
          </button>
        </div>
      )}

      <NearbyResourcesPanel session={session} job={job} setError={setError} />
    </div>
  );
}

function NearbyResourcesPanel({ session, job, setError }) {
  // Marketplace search (docs/adr/0004): finds AVAILABLE resources across
  // ALL resource owners near the customer's address (job.location, which
  // is already the address the contractor entered when creating the
  // job), ranked by distance - the "enter the customer's address, see
  // nearest rig owner + rate + vehicle type" flow.
  const [results, setResults] = useState(null); // null = not searched yet
  const [searching, setSearching] = useState(false);
  const [myBookings, setMyBookings] = useState([]);
  const [requestingId, setRequestingId] = useState(null);

  useEffect(() => {
    refreshMyBookings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.job_id]);

  async function refreshMyBookings() {
    try {
      const list = await listBookings(RESOURCE_NETWORK_URL, session.token);
      setMyBookings(list.filter((b) => b.job_id === job.job_id));
    } catch {
      // Non-critical for this panel - the search still works without it,
      // just without the "already requested" indicator.
    }
  }

  async function handleSearch() {
    setSearching(true);
    setError(null);
    try {
      const found = await matchResources(RESOURCE_NETWORK_URL, session.token, {
        lat: job.location.lat,
        lng: job.location.lng,
        maxResults: 5,
      });
      setResults(found);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  async function handleRequest(resourceId) {
    setRequestingId(resourceId);
    setError(null);
    try {
      await createBookingRequest(RESOURCE_NETWORK_URL, session.token, {
        resourceId,
        jobId: job.job_id,
      });
      refreshMyBookings();
    } catch (err) {
      // Same pattern as JobDetailPanel's PRICING_RULE_MISSING handling
      // above: these two codes have specific, actionable meanings - a
      // generic err.message would just repeat the same idea in less
      // predictable wording each time.
      if (err.code === "RESOURCE_ALREADY_REQUESTED") {
        setError("Someone else already requested this resource. Try another one, or refresh.");
      } else if (err.code === "RESOURCE_NOT_AVAILABLE") {
        setError("This resource is no longer available. Refresh to see current options.");
      } else {
        setError(err.message);
      }
      // Either way, refresh results so the list reflects reality rather
      // than showing a now-stale "Request" button for a taken resource.
      handleSearch();
    } finally {
      setRequestingId(null);
    }
  }

  function statusForResource(resourceId) {
    const booking = myBookings.find((b) => b.resource_id === resourceId);
    return booking ? booking.status : null;
  }

  return (
    <div style={{ marginTop: 12, borderTop: "1px solid #ddd", paddingTop: 8 }}>
      <h4 style={{ fontSize: 14, margin: "0 0 6px" }}>Nearby Rigs &amp; Equipment</h4>

      {results === null && (
        <button onClick={handleSearch} disabled={searching}>
          {searching ? "Searching..." : "Find Nearby Rigs"}
        </button>
      )}

      {results !== null && results.length === 0 && (
        <p style={{ fontSize: 13, color: "#555" }}>
          No available rigs or equipment found near this address yet.
        </p>
      )}

      {results !== null && results.length > 0 && (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                <th style={{ padding: 4 }}>Name</th>
                <th style={{ padding: 4 }}>Vehicle</th>
                <th style={{ padding: 4 }}>Rate/hr</th>
                <th style={{ padding: 4 }}>Distance</th>
                <th style={{ padding: 4 }}></th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => {
                const bookingStatus = statusForResource(r.resource_id);
                return (
                  <tr key={r.resource_id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: 4 }}>{r.name}</td>
                    <td style={{ padding: 4 }}>{r.vehicle_type || "\u2014"}</td>
                    <td style={{ padding: 4 }}>
                      {r.hourly_rate ? `\u20b9${r.hourly_rate}` : "\u2014"}
                    </td>
                    <td style={{ padding: 4 }}>{r.distance_km} km</td>
                    <td style={{ padding: 4 }}>
                      {bookingStatus ? (
                        <span
                          style={{
                            color:
                              bookingStatus === "accepted"
                                ? "#2e7d32"
                                : bookingStatus === "rejected"
                                  ? "#b00020"
                                  : "#e0a020",
                          }}
                        >
                          {bookingStatus}
                        </span>
                      ) : (
                        <button
                          onClick={() => handleRequest(r.resource_id)}
                          disabled={requestingId === r.resource_id}
                        >
                          {requestingId === r.resource_id ? "..." : "Request"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <button onClick={handleSearch} disabled={searching} style={{ marginTop: 6, fontSize: 12 }}>
            {searching ? "Searching..." : "Refresh"}
          </button>
        </>
      )}
    </div>
  );
}
