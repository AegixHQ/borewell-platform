export default function ContractorDashboard({ session }) {
  return (
    <div>
      <h1>Contractor Dashboard</h1>
      <p>Signed in as: {session.email}</p>
      <p>
        Lead intake, pricing rules, job list, quotation generator, and job
        progress screens (UI/UX doc §4.2) are Milestone 3 - not built yet.
        This view proves role-based routing works end to end against the
        real backend.
      </p>
    </div>
  );
}
