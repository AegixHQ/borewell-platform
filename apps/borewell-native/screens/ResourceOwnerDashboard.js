import { StyleSheet, Text, View } from "react-native";

// Placeholder - see CustomerDashboard.js's comment for the pattern.
// Real Resource Owner flow to build here, in order:
//
// 1. "My Fleet" - createResource() (type/name/vehicle_type/hourly_rate/
//    lat/lng), listMyResources(), updateResource() for status changes
// 2. "Booking Requests" - listBookings() (role-scoped server-side: an
//    owner only ever sees requests on their OWN resources - see
//    resource-network's list_bookings endpoint), acceptBooking()/
//    rejectBooking()
//
// web-app/src/dashboards/ResourceOwnerDashboard.jsx has a full working
// reference implementation - read it before starting from scratch.
export default function ResourceOwnerDashboard({ session }) {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Resource Owner Dashboard</Text>
      <Text style={styles.subtext}>Signed in as {session.email}</Text>
      <Text style={styles.body}>
        Fleet management and booking-request screens are not built yet.
        This screen proves login + role-based routing work end to end
        against the real backend.
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
