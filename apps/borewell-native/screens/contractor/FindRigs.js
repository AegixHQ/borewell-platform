/**
 * Marketplace search: every owner's available listings near a job site,
 * nearest first, and the booking request. Ported from
 * apps/web-app/src/pages/contractor/FindRigs.jsx.
 *
 * Opened without a jobId it asks which job first, because the search runs
 * around a job's coordinates (ADR-0004).
 */
import { useState } from "react";
import { View } from "react-native";
import {
  PLATFORM_SPINE_URL, RESOURCE_NETWORK_URL,
  createBookingRequest, getJob, listBookings, listMyJobs, matchResources,
} from "../../services/platform";
import {
  BOOKING_STATUS_LABELS, RESOURCE_TYPES, bookingTone, colors, formatInr,
  jobTypeLabel, shortId,
} from "../../theme";
import { useAction, useAreaName, useLoad, useToast } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import SiteMap from "../../components/SiteMap";
import {
  Alert, Badge, Body, Button, Card, EmptyState, Field, Icon, Input, JobTypeIcon,
  Loading, Pills, Row, Screen, Sheet, Tile, Toast,
} from "../../components/ui";

function distanceLabel(km) {
  if (km === null || km === undefined) return "distance unknown";
  return km < 1 ? "under 1 km away" : `${Number(km).toFixed(1)} km away`;
}

export default function FindRigs({ params }) {
  return params?.jobId ? <RigSearch jobId={params.jobId} /> : <JobPicker />;
}

function JobPicker() {
  const { session } = useSession();
  const { navigate } = useNav();
  const jobs = useLoad(() => listMyJobs(PLATFORM_SPINE_URL, session.token), [session.token]);

  return (
    <Screen>
      <PageHeader title="Find rigs" subtitle="Pick the job you're sourcing a rig for - the search runs around its site." />
      {!!jobs.error && <Alert>{jobs.error.message}</Alert>}
      {jobs.loading && !jobs.data && <Card><Loading label="Loading jobs…" /></Card>}
      {jobs.data && jobs.data.length === 0 && (
        <Card>
          <EmptyState title="No jobs yet">
            A customer request has to exist before you can search for a rig near it.
          </EmptyState>
        </Card>
      )}
      {(jobs.data || []).map((job) => (
        <Card key={job.job_id} onPress={() => navigate("contractor.rigs", { jobId: job.job_id })}>
          <JobPickRow job={job} />
        </Card>
      ))}
    </Screen>
  );
}

function JobPickRow({ job }) {
  const area = useAreaName(job.location?.lat, job.location?.lng);
  return (
    <Row gap={12}>
      <Tile><JobTypeIcon jobType={job.job_type} /></Tile>
      <View style={{ flex: 1, gap: 2 }}>
        <Body weight="700">{area ? area.name : "Site"} · {jobTypeLabel(job.job_type, true)}</Body>
        <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{shortId(job.job_id)}</Body>
      </View>
      <Icon name="chevronRight" size={18} color={colors.muted} />
    </Row>
  );
}

function RigSearch({ jobId }) {
  const { session } = useSession();
  const [toast, setToast] = useToast();
  const [type, setType] = useState("all");
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState("");
  const action = useAction();

  const job = useLoad(() => getJob(PLATFORM_SPINE_URL, session.token, jobId), [jobId]);
  const area = useAreaName(job.data?.location?.lat, job.data?.location?.lng);
  const bookings = useLoad(() => listBookings(RESOURCE_NETWORK_URL, session.token), [jobId]);

  const results = useLoad(async () => {
    if (!job.data) return null;
    return matchResources(RESOURCE_NETWORK_URL, session.token, {
      lat: job.data.location.lat,
      lng: job.data.location.lng,
      resourceType: type === "all" ? undefined : type,
      maxResults: 10,
    });
  }, [job.data?.job_id, type]);

  const jobBookings = (bookings.data || []).filter((b) => b.job_id === jobId);
  function bookingFor(resourceId) {
    return jobBookings.find((b) => b.resource_id === resourceId);
  }

  async function sendRequest() {
    await action.run(
      async () => {
        await createBookingRequest(RESOURCE_NETWORK_URL, session.token, {
          resourceId: selected.resource_id,
          jobId,
          message: note || undefined,
        });
        setNote("");
        setSelected(null);
        setToast("Booking request sent to the owner");
        await Promise.all([bookings.reload(), results.reload({ quiet: true })]);
      },
      {
        onError: (err) => {
          if (err.code === "RESOURCE_ALREADY_REQUESTED") return "Another contractor already has an open request on this rig. Try the next one.";
          if (err.code === "RESOURCE_NOT_AVAILABLE") return "This rig is no longer available - refresh the search.";
          return err.message;
        },
      }
    );
  }

  if (job.loading && !job.data) return <Screen><Card><Loading label="Loading site…" /></Card></Screen>;
  if (job.error) return <Screen><Alert>{job.error.message}</Alert></Screen>;

  const existing = selected ? bookingFor(selected.resource_id) : null;

  return (
    <Screen>
      <PageHeader
        eyebrow={`${shortId(jobId)} · ${jobTypeLabel(job.data.job_type, true)}`}
        title={area ? `Rigs near ${area.name}` : "Rigs near this site"}
        subtitle="Every owner's available listings, nearest first."
      />

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <SiteMap
          marker={job.data.location}
          center={job.data.location}
          circle={{ ...job.data.location, radiusKm: 10 }}
          zoom={10}
          height={180}
        />
        <View style={{ padding: 14, gap: 2 }}>
          <Body weight="600">{area ? `${area.name}, ${area.district}` : "Job site"}</Body>
          <Body size={12} muted>Dashed ring is 10 km from the site.</Body>
        </View>
      </Card>

      <Pills
        value={type}
        onChange={(value) => { setType(value); setSelected(null); }}
        options={[{ value: "all", label: "All" }, ...RESOURCE_TYPES.map((r) => ({ value: r.value, label: r.label }))]}
      />

      {results.loading && <Card><Loading label="Searching the marketplace…" /></Card>}
      {!!results.error && <Alert>{results.error.message}</Alert>}

      {results.data && results.data.length === 0 && (
        <Card>
          <EmptyState title="No rigs match this search">
            Only available listings with a location set are searchable. Try removing the type filter, or check back later.
          </EmptyState>
        </Card>
      )}

      {(results.data || []).map((res, i) => {
        const booking = bookingFor(res.resource_id);
        return (
          <Card key={res.resource_id} onPress={() => setSelected(res)}>
            <Row gap={12}>
              <Tile tone="dark">
                <Body dark weight="700">{i + 1}</Body>
              </Tile>
              <View style={{ flex: 1, gap: 2 }}>
                <Body size={16} weight="700">{res.name}</Body>
                <Body size={13} muted>
                  {res.vehicle_type || RESOURCE_TYPES.find((t) => t.value === res.resource_type)?.label} · {distanceLabel(res.distance_km)}
                </Body>
              </View>
              <View style={{ alignItems: "flex-end", gap: 4 }}>
                <Body weight="700">{res.hourly_rate ? `${formatInr(res.hourly_rate)}/hr` : "On ask"}</Body>
                {booking && <Badge tone={bookingTone(booking.status)}>{BOOKING_STATUS_LABELS[booking.status]}</Badge>}
              </View>
            </Row>
          </Card>
        );
      })}

      <Body size={12} muted>
        Distance is straight-line from the job site. One open request per rig at a time - the owner accepts or declines.
      </Body>

      <Sheet
        visible={!!selected}
        title={selected?.name || ""}
        onClose={() => setSelected(null)}
        actions={
          existing ? null : (
            <Button
              title={action.busy ? "Sending…" : "Send booking request"}
              variant="saffron"
              trailing
              busy={action.busy}
              onPress={sendRequest}
            />
          )
        }
      >
        {selected && (
          <>
            <Body muted>
              {selected.vehicle_type || selected.resource_type} · {distanceLabel(selected.distance_km)}
            </Body>
            <Row gap={24}>
              <View style={{ gap: 2 }}>
                <Body size={13} muted>Rate</Body>
                <Body size={18} weight="700">{selected.hourly_rate ? `${formatInr(selected.hourly_rate)}/hr` : "On ask"}</Body>
              </View>
              <View style={{ gap: 2 }}>
                <Body size={13} muted>Status</Body>
                <Body size={18} weight="700">{selected.status}</Body>
              </View>
            </Row>
            {existing ? (
              <Alert tone="info">
                You already have a {BOOKING_STATUS_LABELS[existing.status].toLowerCase()} request on this rig.
              </Alert>
            ) : (
              <>
                <Field label="Note for the owner">
                  <Input
                    value={note}
                    onChangeText={setNote}
                    multiline
                    placeholder="e.g. Need the rig on site by Monday, 2 days work"
                  />
                </Field>
                {!!action.error && <Alert>{action.error}</Alert>}
              </>
            )}
          </>
        )}
      </Sheet>

      <Toast message={toast} />
    </Screen>
  );
}
