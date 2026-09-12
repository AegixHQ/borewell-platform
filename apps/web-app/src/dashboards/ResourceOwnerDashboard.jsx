import { useEffect, useState } from "react";
import {
  RESOURCE_NETWORK_URL,
  createResource,
  listMyResources,
  updateResource,
  listBookings,
  acceptBooking,
  rejectBooking,
} from "shared-ui";

const RESOURCE_TYPES = ["rig", "equipment", "labour"];
const RESOURCE_STATUSES = ["available", "reserved", "assigned", "in_use", "returned"];

const EMPTY_FORM = {
  resource_type: "rig",
  name: "",
  vehicle_type: "",
  hourly_rate: "",
  lat: "",
  lng: "",
  notes: "",
};

export default function ResourceOwnerDashboard({ session }) {
  const [view, setView] = useState("resources"); // "resources" | "requests"
  const [error, setError] = useState(null);

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16, fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: 24 }}>Resource Owner Dashboard</h1>
      <p style={{ color: "#555" }}>Signed in as {session.email}</p>

      <nav style={{ marginBottom: 16 }}>
        <button onClick={() => setView("resources")} disabled={view === "resources"}>
          My Fleet
        </button>{" "}
        <button onClick={() => setView("requests")} disabled={view === "requests"}>
          Booking Requests
        </button>
      </nav>

      {error && (
        <p role="alert" style={{ color: "#b00020", border: "1px solid #b00020", padding: 8 }}>
          {error}
        </p>
      )}

      {view === "resources" && <FleetScreen session={session} setError={setError} />}
      {view === "requests" && <RequestsScreen session={session} setError={setError} />}
    </div>
  );
}

function FleetScreen({ session, setError }) {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const list = await listMyResources(RESOURCE_NETWORK_URL, session.token);
      setResources(list);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleAdd(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createResource(RESOURCE_NETWORK_URL, session.token, {
        resource_type: form.resource_type,
        name: form.name,
        vehicle_type: form.vehicle_type || undefined,
        // Sent as a string - resource-network's hourly_rate is a Decimal
        // field (Bug 2 precision discipline, same as every other money
        // field in this platform). An empty string means "not set yet."
        hourly_rate: form.hourly_rate || undefined,
        lat: form.lat ? Number(form.lat) : undefined,
        lng: form.lng ? Number(form.lng) : undefined,
        notes: form.notes || undefined,
      });
      setForm(EMPTY_FORM);
      setShowForm(false);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleStatusChange(resourceId, newStatus) {
    setBusy(true);
    setError(null);
    try {
      await updateResource(RESOURCE_NETWORK_URL, session.token, resourceId, {
        status: newStatus,
      });
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>My Fleet</h2>

      {loading ? (
        <p>Loading your resources...</p>
      ) : resources.length === 0 && !showForm ? (
        // UI/UX doc section 7 pattern: friendly empty state, not a blank list.
        <p>
          You haven&apos;t listed any rigs or equipment yet. Add one to start
          receiving booking requests from contractors.
        </p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
              <th style={{ padding: 6 }}>Name</th>
              <th style={{ padding: 6 }}>Type</th>
              <th style={{ padding: 6 }}>Rate/hr</th>
              <th style={{ padding: 6 }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {resources.map((r) => (
              <tr key={r.resource_id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: 6 }}>
                  {r.name}
                  {r.vehicle_type && (
                    <div style={{ fontSize: 12, color: "#777" }}>{r.vehicle_type}</div>
                  )}
                </td>
                <td style={{ padding: 6 }}>{r.resource_type}</td>
                <td style={{ padding: 6 }}>{r.hourly_rate ? `\u20b9${r.hourly_rate}` : "\u2014"}</td>
                <td style={{ padding: 6 }}>
                  <select
                    value={r.status}
                    onChange={(e) => handleStatusChange(r.resource_id, e.target.value)}
                    disabled={busy}
                  >
                    {RESOURCE_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!showForm ? (
        <button onClick={() => setShowForm(true)}>+ Add Rig / Equipment</button>
      ) : (
        <form onSubmit={handleAdd} style={{ background: "#fafafa", padding: 12, border: "1px solid #eee" }}>
          <label style={{ display: "block", marginBottom: 6 }}>
            Type
            <select
              value={form.resource_type}
              onChange={(e) => handleField("resource_type", e.target.value)}
            >
              {RESOURCE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "block", marginBottom: 6 }}>
            Name
            <input
              value={form.name}
              onChange={(e) => handleField("name", e.target.value)}
              required
              placeholder="e.g. DTH Rig 1"
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 6 }}>
            Vehicle type
            <input
              value={form.vehicle_type}
              onChange={(e) => handleField("vehicle_type", e.target.value)}
              placeholder="e.g. DTH Rig - Truck Mounted"
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 6 }}>
            Hourly rate (INR)
            <input
              type="number"
              step="0.01"
              value={form.hourly_rate}
              onChange={(e) => handleField("hourly_rate", e.target.value)}
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 6 }}>
            Base latitude
            <input
              type="number"
              step="any"
              value={form.lat}
              onChange={(e) => handleField("lat", e.target.value)}
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 6 }}>
            Base longitude
            <input
              type="number"
              step="any"
              value={form.lng}
              onChange={(e) => handleField("lng", e.target.value)}
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <p style={{ fontSize: 12, color: "#777" }}>
            Set your base location to appear in nearby searches - a resource
            without a location won&apos;t be found by contractors.
          </p>
          <button type="submit" disabled={busy}>
            {busy ? "Adding..." : "Add to Fleet"}
          </button>{" "}
          <button type="button" onClick={() => setShowForm(false)} disabled={busy}>
            Cancel
          </button>
        </form>
      )}
    </div>
  );
}

function RequestsScreen({ session, setError }) {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const list = await listBookings(RESOURCE_NETWORK_URL, session.token);
      setBookings(list);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept(bookingId) {
    setBusyId(bookingId);
    setError(null);
    try {
      await acceptBooking(RESOURCE_NETWORK_URL, session.token, bookingId);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(bookingId) {
    setBusyId(bookingId);
    setError(null);
    try {
      await rejectBooking(RESOURCE_NETWORK_URL, session.token, bookingId);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  const pending = bookings.filter((b) => b.status === "pending");
  const resolved = bookings.filter((b) => b.status !== "pending");

  return (
    <div>
      <h2>Booking Requests</h2>

      {loading ? (
        <p>Loading requests...</p>
      ) : bookings.length === 0 ? (
        <p>No booking requests yet. They&apos;ll appear here when a contractor requests one of your resources.</p>
      ) : (
        <>
          {pending.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 16 }}>Pending</h3>
              {pending.map((b) => (
                <div
                  key={b.booking_id}
                  style={{ border: "1px solid #e0c060", background: "#fff8e1", padding: 10, marginBottom: 8 }}
                >
                  <p style={{ margin: 0, fontSize: 13 }}>
                    Resource <code>{b.resource_id.slice(0, 8)}</code>
                    {b.message && <> &mdash; &quot;{b.message}&quot;</>}
                  </p>
                  <div style={{ marginTop: 6 }}>
                    <button onClick={() => handleAccept(b.booking_id)} disabled={busyId === b.booking_id}>
                      {busyId === b.booking_id ? "..." : "Accept"}
                    </button>{" "}
                    <button onClick={() => handleReject(b.booking_id)} disabled={busyId === b.booking_id}>
                      {busyId === b.booking_id ? "..." : "Reject"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {resolved.length > 0 && (
            <div>
              <h3 style={{ fontSize: 16 }}>Past Requests</h3>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <tbody>
                  {resolved.map((b) => (
                    <tr key={b.booking_id} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ padding: 6, fontSize: 13 }}>
                        <code>{b.resource_id.slice(0, 8)}</code>
                      </td>
                      <td style={{ padding: 6, fontSize: 13 }}>{b.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
