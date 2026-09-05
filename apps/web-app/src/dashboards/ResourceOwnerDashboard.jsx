export default function ResourceOwnerDashboard({ session }) {
  return (
    <div>
      <h1>Resource Owner Dashboard</h1>
      <p>Signed in as: {session.email}</p>
      <p>
        Rig/equipment management and job-request views are Phase 1 (RFC
        0001 §7) - not built yet. resource-network's data model currently
        keys resources to the contractor, not to an independent resource
        owner, so there is nothing real to show here until that schema
        change lands.
      </p>
    </div>
  );
}
