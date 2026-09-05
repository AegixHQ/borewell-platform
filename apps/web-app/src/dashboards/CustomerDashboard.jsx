export default function CustomerDashboard({ session }) {
  return (
    <div>
      <h1>Customer Dashboard</h1>
      <p>Signed in as: {session.email}</p>
      <p>
        Location entry, quotation review, payment, and job tracking screens
        (UI/UX doc §4.1) are Milestone 3 - not built yet. This view proves
        role-based routing works end to end against the real backend.
      </p>
    </div>
  );
}
