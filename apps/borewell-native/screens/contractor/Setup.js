/**
 * The contractor's two configuration screens, which are separate pages on
 * the web app (PricingRules.jsx and ServiceAreas.jsx) and one screen with a
 * segmented control here - a phone tab bar has no room for both, and they
 * are both "set this up once" work.
 *
 * Pricing rules are not optional: the quotation service returns
 * PRICING_RULE_MISSING until one exists for that job type.
 */
import { useState } from "react";
import { View } from "react-native";
import {
  QUOTATION_URL, RESOURCE_NETWORK_URL,
  listPricingRules, listServiceAreas, upsertPricingRule, upsertServiceArea,
} from "../../services/platform";
import { JOB_TYPES, PILOT_CENTER, colors, formatCoords, formatInr } from "../../theme";
import { clearAreaCache, useAction, useLoad, useToast } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import SiteMap from "../../components/SiteMap";
import {
  Alert, Amount, Badge, Body, Button, Card, Eyebrow, EmptyState, Field, Icon,
  Input, Inset, Loading, Pills, Row, Screen, Tile, Title, Toast,
} from "../../components/ui";

export default function Setup() {
  const [tab, setTab] = useState("pricing");
  const [toast, setToast] = useToast();

  return (
    <Screen>
      <PageHeader
        title="Setup"
        subtitle="What you charge, and the villages you have water-table data for."
      />
      <Pills
        value={tab}
        onChange={setTab}
        options={[{ value: "pricing", label: "Pricing" }, { value: "areas", label: "Service areas" }]}
      />
      {tab === "pricing" ? <PricingRules onToast={setToast} /> : <ServiceAreas onToast={setToast} />}
      <Toast message={toast} />
    </Screen>
  );
}

// ------------------------------------------------------------- pricing

const FIELDS = [
  { key: "base_rate_per_ft", label: "Drilling rate", unit: "₹ / ft", group: "Per foot" },
  { key: "casing_rate_per_ft", label: "Casing rate", unit: "₹ / ft", group: "Per foot" },
  { key: "labour_flat_fee", label: "Labour", unit: "₹", group: "Flat fees" },
  { key: "transport_flat_fee", label: "Transport", unit: "₹", group: "Flat fees" },
  { key: "equipment_flat_fee", label: "Equipment", unit: "₹", group: "Flat fees" },
  { key: "installation_flat_fee", label: "Installation", unit: "₹", group: "Flat fees" },
  { key: "margin_percent", label: "Margin", unit: "%", group: "Margin & floor" },
  { key: "minimum_job_charge", label: "Minimum job charge", unit: "₹", group: "Margin & floor" },
  { key: "assumed_depth_ft", label: "Assumed depth", unit: "ft", group: "Depth", hint: "Used outside the pilot areas" },
  { key: "depth_confidence_band_ft", label: "Confidence band", unit: "± ft", group: "Depth" },
  { key: "depth_overage_rate_per_ft", label: "Overage rate", unit: "₹ / ft", group: "Depth", hint: "Charged past the quoted maximum" },
];

const GROUPS = ["Per foot", "Flat fees", "Margin & floor", "Depth"];
const EMPTY = Object.fromEntries(FIELDS.map((f) => [f.key, ""]));

function PricingRules({ onToast }) {
  const { session } = useSession();
  const [jobType, setJobType] = useState("agricultural");
  // Edits are kept per job type and the saved rule is the fallback, so
  // switching type shows that type's rule without an effect writing state.
  const [drafts, setDrafts] = useState({});
  const action = useAction();

  const rules = useLoad(() => listPricingRules(QUOTATION_URL, session.token), [session.token]);

  const saved = (rules.data || []).find((r) => r.job_type === jobType);
  const values = drafts[jobType]
    || (saved ? Object.fromEntries(FIELDS.map((f) => [f.key, String(saved[f.key] ?? "")])) : EMPTY);

  function setValue(key, value) {
    setDrafts((d) => ({ ...d, [jobType]: { ...values, [key]: value } }));
  }

  const configured = new Set((rules.data || []).map((r) => r.job_type));
  const preview = estimate(values);

  async function save() {
    await action.run(async () => {
      await upsertPricingRule(QUOTATION_URL, session.token, {
        job_type: jobType,
        ...Object.fromEntries(FIELDS.map((f) => [f.key, Number(values[f.key])])),
      });
      onToast("Pricing saved");
      await rules.reload();
    });
  }

  return (
    <>
      {!!rules.error && <Alert>{rules.error.message}</Alert>}
      {rules.loading && !rules.data && <Card><Loading label="Loading your rules…" /></Card>}

      <Card>
        <Title size={19}>Coverage</Title>
        {JOB_TYPES.map((t) => (
          <Row key={t.value}>
            <Body weight="600" style={{ flex: 1 }}>{t.long}</Body>
            {configured.has(t.value) ? <Badge tone="green">Set</Badge> : <Badge tone="red">Not set</Badge>}
          </Row>
        ))}
      </Card>

      <Pills value={jobType} onChange={setJobType} options={JOB_TYPES.map((t) => ({ value: t.value, label: t.long }))} />

      <Card>
        {GROUPS.map((group) => (
          <View key={group} style={{ gap: 10 }}>
            <Eyebrow>{group}</Eyebrow>
            {FIELDS.filter((f) => f.group === group).map((f) => (
              <Field key={f.key} label={`${f.label} (${f.unit})`} hint={f.hint}>
                <Input
                  value={values[f.key]}
                  keyboardType="decimal-pad"
                  onChangeText={(value) => setValue(f.key, value)}
                />
              </Field>
            ))}
          </View>
        ))}
        {!!action.error && <Alert>{action.error}</Alert>}
        <Button title={action.busy ? "Saving…" : "Save pricing"} busy={action.busy} onPress={save} />
      </Card>

      <Card dark>
        <Title size={19} dark>What a quote would look like</Title>
        {preview ? (
          <>
            <Body size={13} muted dark>
              At your assumed depth of {values.assumed_depth_ft} ft, before any local water-table adjustment.
            </Body>
            {preview.items.map((item) => (
              <Row key={item.label}>
                <Body size={14} dark style={{ flexShrink: 1 }}>{item.label}</Body>
                <View style={{ flex: 1, height: 1, marginHorizontal: 8, backgroundColor: colors.chrome3 }} />
                <Body size={14} weight="700" dark style={{ fontVariant: ["tabular-nums"] }}>
                  {formatInr(item.amount.toFixed(2))}
                </Body>
              </Row>
            ))}
            <Inset dark>
              <Row>
                <Body size={13} muted dark style={{ flex: 1 }}>
                  Total{preview.floorApplied ? " (minimum charge applied)" : ""}
                </Body>
                <Amount size={22} color={colors.saffron}>{formatInr(preview.total.toFixed(2))}</Amount>
              </Row>
            </Inset>
          </>
        ) : (
          <Body muted dark size={14}>
            Fill in the fields to see a sample total. This preview is calculated on the phone - the real quote is
            always computed by the quotation service.
          </Body>
        )}
      </Card>
    </>
  );
}

// Mirrors services/quotation/app/pricing/engine.py for a live preview only.
// The backend stays the source of truth for any quote that is actually sent.
function estimate(values) {
  const nums = Object.fromEntries(FIELDS.map((f) => [f.key, Number(values[f.key])]));
  if (FIELDS.some((f) => values[f.key] === "" || Number.isNaN(nums[f.key]))) return null;
  const depth = nums.assumed_depth_ft;
  const items = [
    { label: `Drilling · ${depth} ft`, amount: nums.base_rate_per_ft * depth },
    { label: `Casing · ${depth} ft`, amount: nums.casing_rate_per_ft * depth },
    { label: "Labour", amount: nums.labour_flat_fee },
    { label: "Transport", amount: nums.transport_flat_fee },
    { label: "Equipment", amount: nums.equipment_flat_fee },
    { label: "Installation", amount: nums.installation_flat_fee },
  ];
  const subtotal = items.reduce((sum, i) => sum + i.amount, 0);
  const withMargin = subtotal + (subtotal * nums.margin_percent) / 100;
  const floorApplied = withMargin < nums.minimum_job_charge;
  return { items, total: floorApplied ? nums.minimum_job_charge : withMargin, floorApplied };
}

// -------------------------------------------------------- service areas

const BLANK_AREA = {
  name: "", district: "Madurai", state: "Tamil Nadu",
  radius_km: "8", estimated_water_depth_ft: "", confidence_band_ft: "60",
};

function ServiceAreas({ onToast }) {
  const { session } = useSession();
  const [form, setForm] = useState(BLANK_AREA);
  const [point, setPoint] = useState(PILOT_CENTER);
  // Bumped when an existing area is loaded, to remount the map on its
  // centre - SiteMap owns its centre after mount.
  const [mapKey, setMapKey] = useState(0);
  const action = useAction();

  const areas = useLoad(() => listServiceAreas(RESOURCE_NETWORK_URL, session.token), [session.token]);

  function editArea(area) {
    setForm({
      name: area.name,
      district: area.district,
      state: area.state,
      radius_km: String(area.radius_km),
      estimated_water_depth_ft: String(area.estimated_water_depth_ft),
      confidence_band_ft: String(area.confidence_band_ft),
    });
    setPoint({ lat: area.center_lat, lng: area.center_lng });
    setMapKey((n) => n + 1);
  }

  async function save() {
    await action.run(async () => {
      await upsertServiceArea(RESOURCE_NETWORK_URL, session.token, {
        name: form.name,
        district: form.district,
        state: form.state,
        center_lat: point.lat,
        center_lng: point.lng,
        radius_km: Number(form.radius_km),
        estimated_water_depth_ft: Number(form.estimated_water_depth_ft),
        confidence_band_ft: Number(form.confidence_band_ft),
      });
      clearAreaCache();
      onToast(`${form.name} saved`);
      setForm(BLANK_AREA);
      await areas.reload();
    });
  }

  return (
    <>
      {!!areas.error && <Alert>{areas.error.message}</Alert>}

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <SiteMap key={mapKey} draggable onMove={setPoint} areas={areas.data || []} center={point} zoom={10} height={240} />
        <View style={{ padding: 14, gap: 2 }}>
          <Body size={13} muted>Drag the map to place this area’s centre</Body>
          <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{formatCoords(point.lat, point.lng)}</Body>
        </View>
      </Card>

      <Card>
        <Title size={19}>Add or update an area</Title>
        <Body size={13} muted>
          Saving a name that already exists updates it rather than adding a duplicate.
        </Body>
        <Field label="Village / area name">
          <Input value={form.name} onChangeText={(v) => setForm({ ...form, name: v })} placeholder="e.g. Kallikudi" />
        </Field>
        <Row gap={10}>
          <View style={{ flex: 1 }}>
            <Field label="District">
              <Input value={form.district} onChangeText={(v) => setForm({ ...form, district: v })} />
            </Field>
          </View>
          <View style={{ flex: 1 }}>
            <Field label="State">
              <Input value={form.state} onChangeText={(v) => setForm({ ...form, state: v })} />
            </Field>
          </View>
        </Row>
        <Row gap={10}>
          <View style={{ flex: 1 }}>
            <Field label="Radius (km)">
              <Input value={form.radius_km} keyboardType="decimal-pad" onChangeText={(v) => setForm({ ...form, radius_km: v })} />
            </Field>
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Water depth (ft)">
              <Input
                value={form.estimated_water_depth_ft}
                keyboardType="number-pad"
                onChangeText={(v) => setForm({ ...form, estimated_water_depth_ft: v })}
              />
            </Field>
          </View>
          <View style={{ flex: 1 }}>
            <Field label="± ft">
              <Input
                value={form.confidence_band_ft}
                keyboardType="number-pad"
                onChangeText={(v) => setForm({ ...form, confidence_band_ft: v })}
              />
            </Field>
          </View>
        </Row>
        {!!action.error && <Alert>{action.error}</Alert>}
        <Button
          title={action.busy ? "Saving…" : "Save area"}
          busy={action.busy}
          disabled={!form.name || !form.estimated_water_depth_ft}
          onPress={save}
        />
      </Card>

      <Card>
        <Title size={19}>Configured areas ({(areas.data || []).length})</Title>
        {areas.loading && !areas.data && <Loading />}
        {areas.data && areas.data.length === 0 && (
          <EmptyState title="No areas yet">
            Without an area, every quote falls back to your flat assumed depth.
          </EmptyState>
        )}
        {(areas.data || []).map((area) => (
          <Row key={area.area_id} gap={12}>
            <Tile><Icon name="drop" /></Tile>
            <View style={{ flex: 1, gap: 2 }}>
              <Body weight="600">{area.name}</Body>
              <Body size={13} muted>
                {area.district} · ~{area.estimated_water_depth_ft} ft ± {area.confidence_band_ft} · {area.radius_km} km
              </Body>
            </View>
            <Button title="Edit" variant="light" size="sm" onPress={() => editArea(area)} />
          </Row>
        ))}
      </Card>
    </>
  );
}
