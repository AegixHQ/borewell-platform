/**
 * The rig owner's inbox: contractor booking requests to accept or decline.
 * Ported from the RequestsPanel in
 * apps/web-app/src/pages/owner/OwnerPages.jsx.
 *
 * Accepting reserves the listing; declining frees it for other contractors
 * straight away. Only one open request per listing at a time (ADR-0004).
 */
import { useState } from "react";
import { View } from "react-native";
import {
  RESOURCE_NETWORK_URL, acceptBooking, listBookings, listMyResources, rejectBooking,
} from "../../services/platform";
import { BOOKING_STATUS_LABELS, bookingTone, formatInr, formatRelative } from "../../theme";
import { useAction, useLoad, useToast } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import {
  Alert, Amount, Badge, Body, Button, Card, EmptyState, Eyebrow, Icon, Inset,
  Loading, Pills, Row, Screen, Sheet, Tile, Title, Toast,
} from "../../components/ui";

const FILTERS = [
  { value: "pending", label: "Pending" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Declined" },
  { value: "all", label: "All" },
];

export default function OwnerRequests() {
  const { session } = useSession();
  const [toast, setToast] = useToast();
  const [filter, setFilter] = useState("pending");
  const [selected, setSelected] = useState(null);
  const action = useAction();

  const resources = useLoad(() => listMyResources(RESOURCE_NETWORK_URL, session.token), [session.token], { pollMs: 30000 });
  const bookings = useLoad(() => listBookings(RESOURCE_NETWORK_URL, session.token), [session.token], { pollMs: 20000 });

  const all = bookings.data || [];
  const list = all.filter((b) => filter === "all" || b.status === filter);
  const pending = all.filter((b) => b.status === "pending");

  function resourceFor(booking) {
    return (resources.data || []).find((r) => r.resource_id === booking.resource_id);
  }

  async function respond(booking, accept) {
    await action.run(
      async () => {
        if (accept) await acceptBooking(RESOURCE_NETWORK_URL, session.token, booking.booking_id);
        else await rejectBooking(RESOURCE_NETWORK_URL, session.token, booking.booking_id);
        setSelected(null);
        setToast(accept ? "Booking accepted" : "Request declined");
        await Promise.all([bookings.reload(), resources.reload({ quiet: true })]);
      },
      {
        onError: (err) => (err.code === "RESOURCE_NO_LONGER_AVAILABLE"
          ? "That rig isn't available any more, so this request can't be accepted."
          : err.message),
      }
    );
  }

  const chosen = selected ? all.find((b) => b.booking_id === selected) : null;
  const chosenResource = chosen ? resourceFor(chosen) : null;

  return (
    <Screen>
      <PageHeader
        title="Booking requests"
        subtitle={pending.length
          ? `${pending.length} contractor ${pending.length === 1 ? "request is" : "requests are"} waiting for an answer`
          : "No requests waiting right now"}
      />

      {!!bookings.error && <Alert>{bookings.error.message}</Alert>}

      <Card dark>
        <Row>
          <Eyebrow dark>Requests waiting</Eyebrow>
          <View style={{ flex: 1 }} />
          <Icon name="inbox" size={18} color="#fff" />
        </Row>
        <Amount size={34} color="#fff">{pending.length}</Amount>
        <Body size={13} muted dark>
          {pending.length ? `oldest ${formatRelative(pending[pending.length - 1].created_at)}` : "all clear"}
        </Body>
      </Card>

      <Pills
        value={filter}
        onChange={setFilter}
        options={FILTERS.map((f) => ({
          ...f,
          count: f.value === "all" ? all.length : all.filter((b) => b.status === f.value).length,
        }))}
      />

      {bookings.loading && !bookings.data && <Card><Loading /></Card>}

      {bookings.data && list.length === 0 && (
        <Card>
          <EmptyState title="Nothing waiting">
            When a contractor requests one of your listings, it appears here to accept or decline.
          </EmptyState>
        </Card>
      )}

      {list.map((b) => {
        const res = resourceFor(b);
        return (
          <Card key={b.booking_id} onPress={() => setSelected(b.booking_id)}>
            <Row gap={12}>
              <Tile><Icon name="briefcase" /></Tile>
              <View style={{ flex: 1, gap: 2 }}>
                <Body weight="700">{res ? res.name : "A listing of yours"}</Body>
                <Body size={13} muted>Contractor request · {formatRelative(b.created_at)}</Body>
              </View>
              <Badge tone={bookingTone(b.status)}>{BOOKING_STATUS_LABELS[b.status]}</Badge>
            </Row>
          </Card>
        );
      })}

      <Sheet
        visible={!!chosen}
        title={chosenResource?.name || "Your listing"}
        onClose={() => setSelected(null)}
        actions={
          chosen?.status === "pending" ? (
            <Row gap={10}>
              <Button title="Decline" variant="light" style={{ flex: 1 }} onPress={() => respond(chosen, false)} />
              <Button
                title={action.busy ? "Working…" : "Accept"}
                variant="saffron"
                style={{ flex: 1.4 }}
                busy={action.busy}
                onPress={() => respond(chosen, true)}
              />
            </Row>
          ) : null
        }
      >
        {chosen && (
          <>
            <Body size={13} muted>Request received {formatRelative(chosen.created_at)}</Body>
            <Inset>
              <Row gap={8}>
                <Icon name="truck" size={18} />
                <Body style={{ flex: 1 }}>
                  {chosenResource?.vehicle_type || "Listing"}
                  {chosenResource?.hourly_rate ? ` · ${formatInr(chosenResource.hourly_rate)}/hr` : ""}
                </Body>
              </Row>
              <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>
                Job {chosen.job_id ? chosen.job_id.slice(0, 8) : "not linked"}
              </Body>
            </Inset>
            {chosen.message
              ? <Title size={19}>“{chosen.message}”</Title>
              : <Body muted>No note from the contractor.</Body>}
            {!!action.error && <Alert>{action.error}</Alert>}
            {chosen.status !== "pending" && (
              <View style={{ alignSelf: "flex-start" }}>
                <Badge tone={bookingTone(chosen.status)}>{BOOKING_STATUS_LABELS[chosen.status]}</Badge>
              </View>
            )}
          </>
        )}
      </Sheet>

      <Toast message={toast} />
    </Screen>
  );
}
