/**
 * Requests this contractor has sent to rig owners. Ported from
 * apps/web-app/src/pages/contractor/Bookings.jsx.
 */
import { useState } from "react";
import { View } from "react-native";
import { RESOURCE_NETWORK_URL, listBookings, releaseBooking } from "../../services/platform";
import { BOOKING_STATUS_LABELS, bookingTone, formatRelative, shortId } from "../../theme";
import { useAction, useLoad, useToast } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import {
  Alert, Badge, Body, Button, Card, EmptyState, Icon, Loading, Pills, Row, Screen, Tile, Toast,
} from "../../components/ui";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Declined" },
  { value: "completed", label: "Finished" },
];

export default function Bookings() {
  const { session } = useSession();
  const { navigate } = useNav();
  const [filter, setFilter] = useState("all");
  const [toast, setToast] = useToast();
  const action = useAction();
  const bookings = useLoad(() => listBookings(RESOURCE_NETWORK_URL, session.token), [session.token], { pollMs: 30000 });

  const all = bookings.data || [];
  const list = all.filter((b) => filter === "all" || b.status === filter);
  const counts = Object.fromEntries(
    FILTERS.map((f) => [f.value, f.value === "all" ? all.length : all.filter((b) => b.status === f.value).length])
  );

  // Frees the rig once the work is done, so it can be booked by someone else.
  async function release(booking) {
    await action.run(async () => {
      await releaseBooking(RESOURCE_NETWORK_URL, session.token, booking.booking_id);
      setToast("Rig released - it is available again");
      await bookings.reload();
    });
  }

  return (
    <Screen>
      <PageHeader title="Rig bookings" subtitle="Requests you've sent to rig owners." />
      {!!bookings.error && <Alert>{bookings.error.message}</Alert>}
      {!!action.error && <Alert>{action.error}</Alert>}

      <Pills value={filter} onChange={setFilter} options={FILTERS.map((f) => ({ ...f, count: counts[f.value] }))} />

      {bookings.loading && !bookings.data && <Card><Loading label="Loading bookings…" /></Card>}

      {bookings.data && list.length === 0 && (
        <Card>
          <EmptyState title="No requests here">
            Find a rig near a job site and send the owner a booking request - it shows up here with its status.
          </EmptyState>
        </Card>
      )}

      {list.map((b) => (
        <Card key={b.booking_id} onPress={b.job_id ? () => navigate("contractor.job", { jobId: b.job_id }) : undefined}>
          <Row gap={12} align="flex-start">
            <Tile><Icon name="truck" /></Tile>
            <View style={{ flex: 1, gap: 2 }}>
              <Body weight="700" style={{ fontVariant: ["tabular-nums"] }}>
                {b.job_id ? shortId(b.job_id) : "No job attached"}
              </Body>
              <Body size={13} muted>
                Rig {b.resource_id.slice(0, 8)}{b.message ? ` · “${b.message}”` : ""}
              </Body>
            </View>
            <View style={{ alignItems: "flex-end", gap: 4 }}>
              <Badge tone={bookingTone(b.status)}>{BOOKING_STATUS_LABELS[b.status]}</Badge>
              <Body size={11} muted>{formatRelative(b.responded_at || b.created_at)}</Body>
            </View>
          </Row>
          {b.status === "accepted" && (
            <Button
              title="Done with this rig - release it"
              variant="light"
              size="sm"
              busy={action.busy}
              onPress={() => release(b)}
            />
          )}
        </Card>
      ))}
      <Toast message={toast} />
    </Screen>
  );
}
