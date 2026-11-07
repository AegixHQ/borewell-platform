/**
 * The rig owner's fleet: list equipment, set where it is based, keep its
 * status current. Ported from OwnerFleet/ResourceDialog in
 * apps/web-app/src/pages/owner/OwnerPages.jsx.
 *
 * Only listings that are *available* AND have a location are returned by
 * POST /v1/resources/match, so that is called out on every card rather
 * than left for someone to discover.
 */
import { useState } from "react";
import { View } from "react-native";
import {
  RESOURCE_NETWORK_URL, createResource, listMyResources, updateResource,
} from "../../services/platform";
import {
  PILOT_CENTER, RESOURCE_STATUS_LABELS, RESOURCE_TYPES, colors, formatCoords,
  formatInr, resourceStatusTone,
} from "../../theme";
import { useAction, useLoad, useToast } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import SiteMap from "../../components/SiteMap";
import {
  Alert, Badge, Body, Button, Card, EmptyState, Field, Icon, Input, Loading,
  Pills, Row, Screen, Sheet, Tile, Toast,
} from "../../components/ui";

const BLANK_RESOURCE = {
  resource_type: "rig", name: "", vehicle_type: "", hourly_rate: "", notes: "", status: "available",
};

export default function OwnerFleet() {
  const { session } = useSession();
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useToast();
  const resources = useLoad(() => listMyResources(RESOURCE_NETWORK_URL, session.token), [session.token], { pollMs: 30000 });

  const list = resources.data || [];
  const searchable = list.filter((r) => r.status === "available" && r.lat !== null && r.lat !== undefined);

  return (
    <Screen>
      <PageHeader
        title="Your fleet"
        subtitle={list.length
          ? `${searchable.length} of ${list.length} visible in contractor searches`
          : "Only listings that are available and located show up in a search."}
      />

      {!!resources.error && <Alert>{resources.error.message}</Alert>}
      {resources.loading && !resources.data && <Card><Loading label="Loading your fleet…" /></Card>}

      <Button title="List equipment" trailing onPress={() => setEditing({ ...BLANK_RESOURCE })} />

      {resources.data && list.length === 0 && (
        <Card>
          <EmptyState title="Nothing listed yet">
            Add a rig, a piece of equipment or a crew. Set its location so contractors nearby can find it.
          </EmptyState>
        </Card>
      )}

      {list.map((r) => (
        <Card key={r.resource_id}>
          <Row gap={12} align="flex-start">
            <Tile><Icon name="truck" size={22} /></Tile>
            <View style={{ flex: 1, gap: 2 }}>
              <Body size={16} weight="700">{r.name}</Body>
              <Body size={13} muted>
                {RESOURCE_TYPES.find((t) => t.value === r.resource_type)?.label}
                {r.vehicle_type ? ` · ${r.vehicle_type}` : ""}
              </Body>
            </View>
            <Badge tone={resourceStatusTone(r.status)}>{RESOURCE_STATUS_LABELS[r.status]}</Badge>
          </Row>

          {!!r.notes && <Body size={14} muted numberOfLines={2}>{r.notes}</Body>}

          <View style={{ height: 1, backgroundColor: colors.line }} />

          <Row>
            <Body size={18} weight="700">{r.hourly_rate ? formatInr(r.hourly_rate) : "—"}</Body>
            <Body size={13} muted> /hr</Body>
            <View style={{ flex: 1 }} />
            <Button title="Edit" variant="light" size="sm" onPress={() => setEditing(r)} />
          </Row>

          <Row gap={6}>
            <Icon name="pin" size={15} color={colors.muted} />
            {r.lat === null || r.lat === undefined ? (
              <Body size={13} style={{ color: colors.red }}>No location - not searchable</Body>
            ) : (
              <Body size={13} muted style={{ fontVariant: ["tabular-nums"] }}>{formatCoords(r.lat, r.lng)}</Body>
            )}
          </Row>
        </Card>
      ))}

      {editing && (
        <ResourceSheet
          resource={editing}
          token={session.token}
          onClose={() => setEditing(null)}
          onSaved={async (label) => { setEditing(null); setToast(label); await resources.reload(); }}
        />
      )}
      <Toast message={toast} />
    </Screen>
  );
}

function ResourceSheet({ resource, token, onClose, onSaved }) {
  const isNew = !resource.resource_id;
  const action = useAction();
  const [form, setForm] = useState({
    resource_type: resource.resource_type || "rig",
    name: resource.name || "",
    vehicle_type: resource.vehicle_type || "",
    hourly_rate: resource.hourly_rate ? String(resource.hourly_rate) : "",
    notes: resource.notes || "",
    status: resource.status || "available",
  });
  const [point, setPoint] = useState(
    resource.lat !== null && resource.lat !== undefined ? { lat: resource.lat, lng: resource.lng } : PILOT_CENTER
  );

  async function save() {
    await action.run(async () => {
      const payload = {
        resource_type: form.resource_type,
        name: form.name,
        notes: form.notes || undefined,
        lat: point.lat,
        lng: point.lng,
        hourly_rate: form.hourly_rate ? Number(form.hourly_rate) : undefined,
        vehicle_type: form.vehicle_type || undefined,
      };
      if (isNew) {
        await createResource(RESOURCE_NETWORK_URL, token, payload);
        await onSaved("Listing added");
      } else {
        await updateResource(RESOURCE_NETWORK_URL, token, resource.resource_id, { ...payload, status: form.status });
        await onSaved("Listing updated");
      }
    });
  }

  return (
    <Sheet
      visible
      title={isNew ? "List equipment" : "Edit listing"}
      onClose={onClose}
      actions={
        <Row gap={10}>
          <Button title="Cancel" variant="light" style={{ flex: 1 }} onPress={onClose} />
          <Button
            title={action.busy ? "Saving…" : isNew ? "Add listing" : "Save changes"}
            style={{ flex: 1.4 }}
            busy={action.busy}
            disabled={!form.name}
            onPress={save}
          />
        </Row>
      }
    >
      <Field label="Type">
        <Pills
          value={form.resource_type}
          onChange={(value) => setForm({ ...form, resource_type: value })}
          options={RESOURCE_TYPES}
        />
      </Field>
      <Field label="Name" hint="What a contractor will see">
        <Input value={form.name} onChangeText={(v) => setForm({ ...form, name: v })} placeholder="e.g. Tata 1613 DTH rig" />
      </Field>
      <Field label="Vehicle / description">
        <Input
          value={form.vehicle_type}
          onChangeText={(v) => setForm({ ...form, vehicle_type: v })}
          placeholder="e.g. Truck-mounted DTH 6.5”"
        />
      </Field>
      <Field label="Hourly rate (₹)" hint="Optional - can be set later">
        <Input
          value={form.hourly_rate}
          keyboardType="number-pad"
          onChangeText={(v) => setForm({ ...form, hourly_rate: v })}
          placeholder="2800"
        />
      </Field>
      {!isNew && (
        <Field label="Status" hint="Only 'available' is searchable">
          <Pills
            value={form.status}
            onChange={(value) => setForm({ ...form, status: value })}
            options={Object.entries(RESOURCE_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </Field>
      )}
      <Field label="Notes">
        <Input value={form.notes} onChangeText={(v) => setForm({ ...form, notes: v })} placeholder="e.g. Crew of 4 included" multiline />
      </Field>

      <Field label="Where is it based?" hint="Drag the map to set the point contractors search against">
        <View style={{ borderRadius: 18, overflow: "hidden" }}>
          <SiteMap draggable onMove={setPoint} center={point} zoom={11} height={200} />
        </View>
      </Field>
      <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{formatCoords(point.lat, point.lng)}</Body>

      {!!action.error && <Alert>{action.error}</Alert>}
    </Sheet>
  );
}
