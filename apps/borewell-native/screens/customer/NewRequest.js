/**
 * "Where should we drill?" - pin the site, pick the type, get an estimate.
 * Ported from apps/web-app/src/pages/customer/NewRequest.jsx.
 *
 * The web version has a "use my current location" button. expo-location is
 * a native module that could not be installed when this was built (see
 * components/ui.js), so the map opens over the first pilot area and the site
 * is chosen by dragging. Adding it later is `npx expo install expo-location`
 * plus one handler here.
 */
import { useState } from "react";
import { Pressable, View } from "react-native";
import {
  PLATFORM_SPINE_URL, RESOURCE_NETWORK_URL, createJob, listServiceAreas,
} from "../../services/platform";
import { JOB_TYPES, PILOT_CENTER, colors, formatCoords } from "../../theme";
import { useAction, useAreaName, useLoad } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import SiteMap from "../../components/SiteMap";
import {
  Alert, Body, Button, Card, Icon, JobTypeIcon, Loading, Row, Screen, Tile, Title,
} from "../../components/ui";

export default function NewRequest() {
  const { session } = useSession();
  const { replace } = useNav();
  const { busy, error, run } = useAction();
  const [pinned, setPinned] = useState(null);
  const [jobType, setJobType] = useState("agricultural");

  const areas = useLoad(() => listServiceAreas(RESOURCE_NETWORK_URL, session.token), [session.token]);

  // The map opens over the first pilot area rather than the district centre
  // (PILOT_CENTER is Madurai city, ~20 km from any of the pilot villages, so
  // opening there greets every customer with "outside the pilot areas").
  // Until the pin is moved, the chosen point IS that centre - derived, so no
  // effect has to write it back into state.
  const first = areas.data?.[0];
  const start = first ? { lat: first.center_lat, lng: first.center_lng } : PILOT_CENTER;
  const point = pinned || start;
  const area = useAreaName(point.lat, point.lng);

  async function submit() {
    await run(async () => {
      const job = await createJob(PLATFORM_SPINE_URL, session.token, {
        lat: point.lat,
        lng: point.lng,
        jobType,
      });
      replace("customer.job", { jobId: job.job_id });
    });
  }

  return (
    <Screen>
      <PageHeader
        title="Where should we drill?"
        subtitle="Drag the map to put the pin on your site. The closer it is, the better the depth estimate."
      />

      <Card style={{ padding: 0, overflow: "hidden" }}>
        {/* Mounted only once the areas are in, because the map keeps its own
            centre after mount - it must start in the right place. */}
        {areas.loading ? (
          <View style={{ height: 300, alignItems: "center", justifyContent: "center" }}>
            <Loading label="Loading the map…" />
          </View>
        ) : (
          <SiteMap draggable onMove={setPinned} areas={areas.data || []} center={start} zoom={11} height={300} />
        )}
        <View style={{ padding: 16, gap: 10 }}>
          <Row gap={12}>
            <Tile><Icon name="pin" /></Tile>
            <View style={{ flex: 1, gap: 2 }}>
              <Body size={16} weight="700">{area ? `${area.name}, ${area.district}` : "Outside the pilot areas"}</Body>
              <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{formatCoords(point.lat, point.lng)}</Body>
            </View>
          </Row>
          {area ? (
            <Alert tone="ok">
              Water table here is around {area.estimated_water_depth_ft} ft (± {area.confidence_band_ft} ft), so your quote uses real local data.
            </Alert>
          ) : (
            <Alert tone="info">
              No depth data for this spot yet - your contractor will quote from their own assumed depth.
            </Alert>
          )}
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

      <Button title={busy ? "Sending…" : "Get my estimate"} size="lg" trailing busy={busy} onPress={submit} />
    </Screen>
  );
}
