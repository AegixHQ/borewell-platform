/**
 * The contractor's board: money first, then the job list grouped by phase.
 * Ported from apps/web-app/src/pages/contractor/ContractorOverview.jsx -
 * the web version puts a table next to a preview panel; on a phone the same
 * information is a filtered list of cards.
 */
import { useMemo, useState } from "react";
import { View } from "react-native";
import {
  PLATFORM_SPINE_URL, QUOTATION_URL, RESOURCE_NETWORK_URL,
  getLatestQuotationForJob, listBookings, listMyJobs,
} from "../../services/platform";
import {
  PHASES, STAGE_LABELS, colors, formatInr, formatRelative, jobTypeLabel,
  phaseOf, shortId, stageTone,
} from "../../theme";
import { useAreaName, useLoad } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import {
  Alert, Amount, Badge, Body, Card, EmptyState, Eyebrow, Icon, JobTypeIcon,
  Loading, Pills, Row, Screen, Tile,
} from "../../components/ui";

export default function ContractorBoard() {
  const { session } = useSession();
  const { navigate } = useNav();
  const [phase, setPhase] = useState("all");

  const jobs = useLoad(() => listMyJobs(PLATFORM_SPINE_URL, session.token), [session.token], { pollMs: 30000 });
  const bookings = useLoad(() => listBookings(RESOURCE_NETWORK_URL, session.token), [session.token], { pollMs: 30000 });

  const list = useMemo(() => jobs.data || [], [jobs.data]);

  // Quotes only for the jobs sitting in the "Quoted" phase - that is what
  // the money figure is about, so this is not one call per job.
  const quotedJobs = useMemo(() => list.filter((j) => phaseOf(j.status).key === "quoted"), [list]);
  const quotedIds = quotedJobs.map((j) => j.job_id).join(",");
  const quotes = useLoad(async () => {
    const results = await Promise.all(
      quotedJobs.map((j) =>
        getLatestQuotationForJob(QUOTATION_URL, session.token, j.job_id)
          .then((q) => [j.job_id, q])
          .catch(() => [j.job_id, null])
      )
    );
    return Object.fromEntries(results);
  }, [quotedIds]);

  const counts = useMemo(() => {
    const byPhase = Object.fromEntries(PHASES.map((p) => [p.key, 0]));
    list.forEach((j) => { byPhase[phaseOf(j.status).key] += 1; });
    return byPhase;
  }, [list]);

  const awaiting = Object.values(quotes.data || {}).reduce(
    (sum, q) => (q && q.status !== "approved" && q.status !== "rejected" ? sum + Number(q.total_estimate || 0) : sum),
    0
  );
  const drilling = list.filter((j) => phaseOf(j.status).key === "drilling").length;
  const pendingBookings = (bookings.data || []).filter((b) => b.status === "pending").length;

  const filtered = phase === "all" ? list : list.filter((j) => phaseOf(j.status).key === phase);

  return (
    <Screen>
      <PageHeader
        title={greeting(session.email)}
        subtitle={`${list.length} jobs on your board · ${pendingBookings} rig ${pendingBookings === 1 ? "request" : "requests"} awaiting an owner`}
      />

      {!!jobs.error && <Alert>{jobs.error.message}</Alert>}

      <Card dark>
        <Row>
          <Eyebrow dark>Awaiting customer approval</Eyebrow>
          <View style={{ flex: 1 }} />
          <Icon name="arrowRight" size={18} color={colors.saffron} />
        </Row>
        <Amount size={34} color="#fff">{formatInr(awaiting.toFixed(2))}</Amount>
        <Body size={13} muted dark>
          {quotedJobs.length} {quotedJobs.length === 1 ? "quote" : "quotes"} out with customers
        </Body>
      </Card>

      <Row gap={10}>
        <Kpi label="Leads" value={counts.leads ?? 0} sub="to estimate" icon="inbox" />
        <Kpi label="Drilling" value={drilling} sub="rigs on site" icon="truck" />
        <Kpi label="Closing" value={counts.closing ?? 0} sub="completion" icon="board" />
      </Row>

      <Pills
        value={phase}
        onChange={setPhase}
        options={[
          { value: "all", label: "All", count: list.length },
          ...PHASES.map((p) => ({ value: p.key, label: p.label, count: counts[p.key] })),
        ]}
      />

      {jobs.loading && !jobs.data && <Card><Loading label="Loading jobs…" /></Card>}

      {jobs.data && filtered.length === 0 && (
        <Card>
          <EmptyState title="Nothing here yet">
            {phase === "all"
              ? "When a customer submits a request it lands here as a new lead."
              : "No jobs in this phase right now."}
          </EmptyState>
        </Card>
      )}

      {filtered.map((job) => (
        <JobCard
          key={job.job_id}
          job={job}
          quote={quotes.data?.[job.job_id]}
          onPress={() => navigate("contractor.job", { jobId: job.job_id })}
        />
      ))}
    </Screen>
  );
}

function Kpi({ label, value, sub, icon }) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, borderRadius: 20, padding: 14, gap: 8 }}>
      <Row>
        <Body size={11} muted numberOfLines={1} style={{ flex: 1 }}>{label}</Body>
        <Icon name={icon} size={15} color={colors.muted} />
      </Row>
      <Amount size={24}>{value}</Amount>
      <Body size={11} muted numberOfLines={1}>{sub}</Body>
    </View>
  );
}

function JobCard({ job, quote, onPress }) {
  const area = useAreaName(job.location?.lat, job.location?.lng);
  return (
    <Card onPress={onPress}>
      <Row gap={12} align="flex-start">
        <Tile><JobTypeIcon jobType={job.job_type} /></Tile>
        <View style={{ flex: 1, gap: 2 }}>
          <Body size={16} weight="700">{area ? area.name : jobTypeLabel(job.job_type, true)}</Body>
          <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>
            {shortId(job.job_id)} · {jobTypeLabel(job.job_type, true)}
          </Body>
        </View>
        <View style={{ alignItems: "flex-end", gap: 6 }}>
          <Body size={15} weight="700">{quote ? formatInr(quote.total_estimate) : "—"}</Body>
          <Body size={11} muted>{formatRelative(job.created_at)}</Body>
        </View>
      </Row>
      <Row>
        <Badge tone={stageTone(job.status)}>{STAGE_LABELS[job.status]}</Badge>
        <View style={{ flex: 1 }} />
        <Icon name="chevronRight" size={16} color={colors.muted} />
      </Row>
    </Card>
  );
}

function greeting(email) {
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const name = (email || "").split("@")[0].replace(/[._-]+/g, " ");
  return `${part}, ${name.charAt(0).toUpperCase()}${name.slice(1)}`;
}
