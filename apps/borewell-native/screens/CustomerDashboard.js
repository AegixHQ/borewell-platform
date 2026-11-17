import { StyleSheet, Text, View } from "react-native";

// Deliberately a placeholder, matching how apps/web-app/src/dashboards/*
// looked before each was built out real screen-by-screen (see that
// project's git history - CustomerDashboard.jsx started exactly this
// bare). The real Customer flow to build here, in order (see
// docs/adr and packages/contracts/openapi/*.yaml for the exact request/
// response shapes each step needs):
//
// 1. Location Entry -> services/platform.js's createJob()
// 2. Poll services/platform.js's getLatestQuotationForJob() until a
//    quotation exists (quotation generation is CONTRACTOR-only - see
//    quotation service's require_role("contractor") on POST
//    /v1/quotations - the customer side only ever polls for one to
//    appear, same as web-app's CustomerDashboard.jsx already does)
// 3. Quotation Display - MUST show the depth-range + confidence badge
//    (UI/UX doc section 7 - this is a required element in every prior
//    version of this app, not optional polish)
// 4. Approve (approveQuotation()) or Request Changes (rejectQuotation())
// 5. Payment - createPayment(), then Razorpay Checkout (see
//    services/payments-data/app/gateway/razorpay_client.py on the
//    backend for what create-order/webhook expect - the native
//    equivalent of Razorpay's web Checkout.js is their React Native SDK,
//    a separate integration not yet started here)
// 6. Job Tracking - poll getJob(), show the RFC 0001 section 8 lifecycle
export default function CustomerDashboard({ session }) {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Customer Dashboard</Text>
      <Text style={styles.subtext}>Signed in as {session.email}</Text>
      <Text style={styles.body}>
        Location entry, quotation review, payment, and job tracking screens
        are not built yet. This screen proves login + role-based routing
        work end to end against the real backend.
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
