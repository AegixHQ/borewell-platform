/**
 * The admin's overview: money first (what has actually been collected), then
 * where every job sits, who is on the platform, and the latest jobs. Read-only
 * on purpose - every figure here comes from endpoints the admin role already
 * has, and tapping a job opens the same job screen the contractor uses.
 */
import { useMemo } from "react";
import { View } from "react-native";
import {
  PAYMENTS_URL, PLATFORM_SPINE_URL, listMyJobs, listPayments, listUsers,
} from "../../services/platform";
import {
  PHASES, STAGE_LABELS, colors, formatInr, formatRelative, jobTypeLabel, phaseOf, shortId, stageTone,
} from "../../theme";
import { useLoad } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import {
  Alert, Amount, Badge, Body, Button, Card, EmptyState, Eyebrow, Icon, JobTypeIcon, Loading, Row, Screen, Tile, Title,
} from "../../components/ui";

const RECENT_JOBS = 6;

export default function AdminOverview() {
  const { session } = useSession();
  const { navigate } = useNav();

  const jobs = useLoad(() => listMyJobs(PLATFORM_SPINE_URL, session.token), [session.token], { pollMs: 30000 });
  const payments = useLoad(() => listPayments(PAYMENTS_URL, session.token), [session.token], { pollMs: 30000 });
  const users = useLoad(() => listUsers(PLATFORM_SPINE_URL, session.token), [session.token]);

  const list = useMemo(() => jobs.data || [], [jobs.data]);
  const byPhase = useMemo(() => {
    const counts = Object.fromEntries(PHASES.map((p) => [p.key, 0]));
    list.forEach((j) => { counts[phaseOf(j.status).key] += 1; });
    return counts;
  }, [list]);

  const money = useMemo(() => {
    const out = { collected: 0, pending: 0, cash: 0, online: 0, paid: 0, open: 0 };
    (payments.data || []).forEach((p) => {
      const amount = Number(p.amount) || 0;
      if (p.status === "completed") {
        out.collected += amount;
        out.paid += 1;
        out[p.method === "cash" ? "cash" : "online"] += amount;
      } else if (p.status === "pending") {
        out.pending += amount;
        out.open += 1;
      }
    });
    return out;
  }, [payments.data]);

  const people = useMemo(() => {
    const counts = { customer: 0, contractor: 0, resource_owner: 0, admin: 0 };
    (users.data || []).forEach((u) => { counts[u.role] = (counts[u.role] || 0) + 1; });
    return counts;
  }, [users.data]);

  const loading = (jobs.loading && !jobs.data) || (payments.loading && !payments.data);
  const failed = jobs.error || payments.error || users.error;

  return (
    <Screen>
      <PageHeader title="Overview" subtitle={`${list.length} jobs · ${(users.data || []).length} accounts`} />

      {!!failed && <Alert>{failed.message}</Alert>}

      <Card dark>
        <Eyebrow dark>Collected</Eyebrow>
        <Amount size={34} color="#fff">{formatInr(money.collected.toFixed(2))}</Amount>
        <Body size={13} muted dark>
          {money.paid} {money.paid === 1 ? "payment" : "payments"} · {formatInr(money.online.toFixed(2))} online · {formatInr(money.cash.toFixed(2))} cash
        </Body>
      </Card>

      <Row gap={10}>
        <Stat label="Awaiting payment" value={formatInr(money.pending.toFixed(2))} sub={`${money.open} open`} icon="wallet" />
        <Stat label="Drilling now" value={byPhase.drilling ?? 0} sub="rigs on site" icon="truck" />
      </Row>

      <Card>
        <Title size={19}>Jobs by stage</Title>
        {loading && <Loading />}
        {PHASES.map((phase) => (
          <Row key={phase.key}>
            <Body weight="600" style={{ flex: 1 }}>{phase.label}</Body>
            <Body weight="700" style={{ fontVariant: ["tabular-nums"] }}>{byPhase[phase.key] ?? 0}</Body>
          </Row>
        ))}
      </Card>

      <Card>
        <Row>
          <Title size={19} style={{ flex: 1 }}>People</Title>
          <Button title="Manage" variant="light" size="sm" onPress={() => navigate("admin.people")} />
        </Row>
        <Row gap={10}>
          <Count label="Customers" value={people.customer} />
          <Count label="Contractors" value={people.contractor} />
          <Count label="Rig owners" value={people.resource_owner} />
        </Row>
      </Card>

      <Title size={19}>Latest jobs</Title>
      {jobs.data && list.length === 0 && (
        <Card><EmptyState title="No jobs yet">Jobs appear here as soon as a customer or contractor opens one.</EmptyState></Card>
      )}
      {list.slice(0, RECENT_JOBS).map((job) => (
        <Card key={job.job_id} onPress={() => navigate("admin.job", { jobId: job.job_id })}>
          <Row gap={12}>
            <Tile><JobTypeIcon jobType={job.job_type} /></Tile>
            <View style={{ flex: 1, gap: 2 }}>
              <Body size={16} weight="700">{job.walk_in && job.customer_name ? job.customer_name : jobTypeLabel(job.job_type, true)}</Body>
              <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>{shortId(job.job_id)} · {formatRelative(job.created_at)}</Body>
            </View>
            <Badge tone={stageTone(job.status)}>{STAGE_LABELS[job.status]}</Badge>
            <Icon name="chevronRight" size={16} color={colors.muted} />
          </Row>
        </Card>
      ))}
    </Screen>
  );
}

function Stat({ label, value, sub, icon }) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, borderRadius: 20, padding: 14, gap: 8 }}>
      <Row>
        <Body size={11} muted numberOfLines={1} style={{ flex: 1 }}>{label}</Body>
        <Icon name={icon} size={15} color={colors.muted} />
      </Row>
      <Amount size={22}>{value}</Amount>
      <Body size={11} muted numberOfLines={1}>{sub}</Body>
    </View>
  );
}

function Count({ label, value }) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.ground, borderRadius: 16, padding: 12, gap: 4 }}>
      <Amount size={22}>{value ?? 0}</Amount>
      <Body size={11} muted numberOfLines={1}>{label}</Body>
    </View>
  );
}
