import { StyleSheet, Text, View } from "react-native";

// Placeholder - see CustomerDashboard.js's comment for the same pattern
// explanation. Real Contractor flow to build here, in order:
//
// 1. Pricing Rules screen - upsertPricingRule()/listPricingRules(), all
//    11 fields (see quotation service's PricingRuleUpsertRequest schema)
// 2. Job List / Leads - listMyJobs()
// 3. Per-job: "Find Nearby Rigs" - matchResources() with the job's own
//    location, then createBookingRequest() on a chosen result (real
//    cross-owner marketplace search - see docs/adr/0004)
// 4. "Send Quotation" - generateQuotation()
// 5. Advance job status through its lifecycle - updateJobStatus()
// 6. Job completion - actual depth/cost logging (platform-spine's
//    POST /v1/jobs/{id}/completion - not yet in services/platform.js,
//    needs adding when this screen is built)
//
// web-app/src/dashboards/ContractorDashboard.jsx has a full working
// reference implementation of this entire flow (web UI, not directly
// portable JSX, but the API call sequence and state shape are exactly
// what this screen needs) - read it before starting from scratch.
export default function ContractorDashboard({ session }) {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Contractor Dashboard</Text>
      <Text style={styles.subtext}>Signed in as {session.email}</Text>
      <Text style={styles.body}>
        Pricing rules, leads, nearby-resource search, quotation generation,
        and job tracking screens are not built yet. This screen proves
        login + role-based routing work end to end against the real
        backend.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, paddingTop: 60 },
  heading: { fontSize: 24, fontWeight: "600" },
  subtext: { fontSize: 14, color: "#555", marginTop: 4 },
  body: { fontSize: 14, marginTop: 16, lineHeight: 20 },
});
