/**
 * "New walk-in job" - a customer standing in front of the contractor who has
 * no account and no app. The contractor takes their name and number, pins the
 * site and picks the job type; the server opens the job under a customer id
 * that belongs to no account. From the job screen the contractor then quotes,
 * approves for the customer (after they agree) and records the cash.
 * Same site-picking flow as customer/NewRequest.js.
 */
import { useState } from "react";
import { Pressable, View } from "react-native";
import {
  PLATFORM_SPINE_URL, RESOURCE_NETWORK_URL, createWalkInJob, listServiceAreas,
} from "../../services/platform";
import { JOB_TYPES, PILOT_CENTER, colors, formatCoords } from "../../theme";
import { useAction, useAreaName, useLoad } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import SiteMap from "../../components/SiteMap";
import {
  Alert, Body, Button, Card, Field, Icon, Input, JobTypeIcon, Loading, Row, Screen, Tile, Title,
} from "../../components/ui";

/** Ten digits, with or without +91 / spaces / dashes - what the server accepts. */
export function normalisePhone(text) {
  return String(text || "").replace(/\+91|[\s-]/g, "");
}

export function walkInFormError({ name, phone }) {
  if (!String(name || "").trim()) return "Enter the customer's name.";
  if (!/^\d{10}$/.test(normalisePhone(phone))) return "Enter a 10-digit mobile number.";
  return null;
}

export default function WalkIn() {
  const { session } = useSession();
  const { replace } = useNav();
  const { busy, error, run } = useAction();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [pinned, setPinned] = useState(null);
  const [jobType, setJobType] = useState("agricultural");
  const [touched, setTouched] = useState(false);

  const areas = useLoad(() => listServiceAreas(RESOURCE_NETWORK_URL, session.token), [session.token]);
  const first = areas.data?.[0];
  const start = first ? { lat: first.center_lat, lng: first.center_lng } : PILOT_CENTER;
  const point = pinned || start;
  const area = useAreaName(point.lat, point.lng);

  const formError = walkInFormError({ name, phone });

  async function submit() {
    setTouched(true);
    if (formError) return;
    await run(async () => {
      const job = await createWalkInJob(PLATFORM_SPINE_URL, session.token, {
        customerName: name.trim(),
        customerPhone: normalisePhone(phone),
        lat: point.lat,
        lng: point.lng,
        jobType,
      });
      replace("contractor.job", { jobId: job.job_id });
    });
  }

  return (
    <Screen>
      <PageHeader
        title="New walk-in job"
        subtitle="For a customer who is with you and has no account. You will quote, approve and take payment for them."
      />

      <Card>
        <Title size={19}>Customer</Title>
        <Field label="Name" error={touched && !String(name).trim() ? "Enter the customer's name." : undefined}>
          <Input
            value={name}
            onChangeText={setName}
            placeholder="e.g. Ramesh Kumar"
            autoCapitalize="words"
            maxLength={100}
            testID="walkin-name"
          />
        </Field>
        <Field
          label="Mobile number"
          hint="10 digits. Kept with the job so you can reach them."
          error={touched && formError && String(name).trim() ? formError : undefined}
        >
          <Input
            value={phone}
            onChangeText={setPhone}
            placeholder="e.g. 98765 43210"
            keyboardType="phone-pad"
            maxLength={16}
            testID="walkin-phone"
          />
        </Field>
      </Card>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        {areas.loading ? (
          <View style={{ height: 260, alignItems: "center", justifyContent: "center" }}>
            <Loading label="Loading the map…" />
          </View>
        ) : (
          <SiteMap draggable onMove={setPinned} areas={areas.data || []} center={start} zoom={11} height={260} />
        )}
        <View style={{ padding: 16, gap: 10 }}>
          <Row gap={12}>
            <Tile><Icon name="pin" /></Tile>
            <View style={{ flex: 1, gap: 2 }}>
              <Body size={16} weight="700">{area ? `${area.name}, ${area.district}` : "Outside the pilot areas"}</Body>
              <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{formatCoords(point.lat, point.lng)}</Body>
            </View>
          </Row>
          <Body size={13} muted>Drag the map to put the pin on the customer&apos;s site.</Body>
        </View>
      </Card>

      <Card>
        <Title size={19}>What is the borewell for?</Title>
        {JOB_TYPES.map((type) => {
          const on = jobType === type.value;
          return (
            <Pressable
              key={type.value}
              onPress={() => setJobType(type.value)}
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: 12,
                padding: 12,
                borderRadius: 18,
                backgroundColor: on ? colors.ground : "transparent",
                borderWidth: 2,
                borderColor: on ? colors.ink : "transparent",
              }}
            >
              <Tile tone={on ? "saffron" : "ground"}>
                <JobTypeIcon jobType={type.value} />
              </Tile>
              <View style={{ flex: 1, gap: 1 }}>
                <Body size={16} weight="700">{type.long}</Body>
                <Body size={13} muted>{type.hint}</Body>
              </View>
              {on && <Icon name="check" size={20} />}
            </Pressable>
          );
        })}
      </Card>

      {!!error && <Alert>{error}</Alert>}

      <Button title={busy ? "Opening…" : "Open the job"} size="lg" trailing busy={busy} onPress={submit} />
    </Screen>
  );
}
