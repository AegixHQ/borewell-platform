/**
 * The customer's list of borewells. Ported from
 * apps/web-app/src/pages/customer/CustomerHome.jsx.
 */
import { View } from "react-native";
import { PLATFORM_SPINE_URL, listMyJobs } from "../../services/platform";
import {
  STAGE_LABELS, colors, customerStepIndex, formatRelative, jobTypeLabel, shortId, stageTone,
} from "../../theme";
import { useAreaName, useLoad } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import { CustomerSteps } from "../../components/StageViews";
import {
  Alert, Badge, Body, Button, Card, EmptyState, Icon, JobTypeIcon, Loading, Row, Screen, Tile, Title,
} from "../../components/ui";

export default function CustomerHome() {
  const { session } = useSession();
  const { navigate } = useNav();
  const jobs = useLoad(() => listMyJobs(PLATFORM_SPINE_URL, session.token), [session.token], { pollMs: 30000 });

  const all = jobs.data || [];
  const active = all.filter((j) => j.status !== "service_history");
  const past = all.filter((j) => j.status === "service_history");

  return (
    <Screen>
      <PageHeader
        title="Your borewells"
        subtitle="Track a request, review your quote and pay - all in one place."
      />

      {!!jobs.error && <Alert>{jobs.error.message}</Alert>}
      {jobs.loading && !jobs.data && <Card><Loading label="Loading your jobs…" /></Card>}

      <Button title="Request a borewell" trailing onPress={() => navigate("customer.new")} />

      {jobs.data && all.length === 0 && (
        <Card>
          <EmptyState title="No borewell requests yet">
            Pin your site on the map and a contractor will send you a quote with the expected depth range.
          </EmptyState>
        </Card>
      )}

      {active.map((job) => <JobCard key={job.job_id} job={job} onPress={() => navigate("customer.job", { jobId: job.job_id })} />)}

      {past.length > 0 && (
        <>
          <Title size={18} style={{ marginTop: 8 }}>Completed</Title>
          {past.map((job) => <JobCard key={job.job_id} job={job} onPress={() => navigate("customer.job", { jobId: job.job_id })} />)}
        </>
      )}
    </Screen>
  );
}

function JobCard({ job, onPress }) {
  const area = useAreaName(job.location?.lat, job.location?.lng);
  const step = customerStepIndex(job.status);

  return (
    <Card onPress={onPress}>
      <Row gap={12} align="flex-start">
        <Tile>
          <JobTypeIcon jobType={job.job_type} />
        </Tile>
        <View style={{ flex: 1, gap: 2 }}>
          <Body size={16} weight="700">{jobTypeLabel(job.job_type, true)} borewell</Body>
          <Body size={13} muted>{area ? `${area.name}, ${area.district}` : "Location pinned"}</Body>
        </View>
        <Badge tone={stageTone(job.status)}>{STAGE_LABELS[job.status]}</Badge>
      </Row>

      <CustomerSteps status={job.status} />

      {step === 1 && (
        <Alert tone="info">Your quote is ready to review</Alert>
      )}

      <Row>
        <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{shortId(job.job_id)}</Body>
        <View style={{ flex: 1 }} />
        <Body size={12} muted>{formatRelative(job.created_at)}</Body>
        <Icon name="chevronRight" size={16} color={colors.muted} />
      </Row>
    </Card>
  );
}
