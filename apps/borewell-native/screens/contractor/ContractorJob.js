/**
 * One job, from the contractor's side: generate or edit the quotation,
 * advance the stage, book a rig, close the job out. Ported from
 * apps/web-app/src/pages/contractor/ContractorJob.jsx.
 */
import { useState } from "react";
import { View } from "react-native";
import {
  PAYMENTS_URL, PLATFORM_SPINE_URL, QUOTATION_URL, RESOURCE_NETWORK_URL,
  editQuotation, generateQuotation, getJob, getJobCompletionResult,
  getLatestQuotationForJob, listBookings, listPayments, logJobCompletion,
  updateJobStatus,
} from "../../services/platform";
import {
  BOOKING_STATUS_LABELS, JOB_STAGES, STAGE_LABELS, bookingTone, colors,
  formatCoords, formatInr, jobTypeLabel, nextStage, shortId, stageIndex, stageTone,
} from "../../theme";
import { useAction, useAreaName, useLoad, useToast } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { PageHeader } from "../../components/AppShell";
import DepthGauge from "../../components/DepthGauge";
import SiteMap from "../../components/SiteMap";
import { StageRail } from "../../components/StageViews";
import {
  Alert, Amount, Badge, Body, Button, Card, Confirm, Eyebrow, Field, Icon, Input,
  Inset, KeyValue, Loading, Row, Screen, Sheet, Title, Toast,
} from "../../components/ui";

export default function ContractorJob({ params }) {
  const { jobId } = params;
  const { session } = useSession();
  const { navigate, goBack } = useNav();
  const [toast, setToast] = useToast();
  const [sheet, setSheet] = useState(null);
  const action = useAction();

  const job = useLoad(() => getJob(PLATFORM_SPINE_URL, session.token, jobId), [jobId], { pollMs: 30000 });
  const quote = useLoad(
    () => getLatestQuotationForJob(QUOTATION_URL, session.token, jobId).catch((err) => {
      if (err.code === "QUOTATION_NOT_FOUND" || err.status === 404) return null;
      throw err;
    }),
    [jobId],
    { pollMs: 20000 }
  );
  const bookings = useLoad(() => listBookings(RESOURCE_NETWORK_URL, session.token), [jobId], { pollMs: 30000 });
  const payments = useLoad(() => listPayments(PAYMENTS_URL, session.token), [jobId], { pollMs: 30000 });
  const completion = useLoad(
    () => getJobCompletionResult(PLATFORM_SPINE_URL, session.token, jobId).catch((err) => {
      if (err.status === 404) return null;
      throw err;
    }),
    [jobId]
  );

  const area = useAreaName(job.data?.location?.lat, job.data?.location?.lng);
  const q = quote.data;
  const jobBookings = (bookings.data || []).filter((b) => b.job_id === jobId);
  const payment = (payments.data || []).find((p) => p.job_id === jobId);

  async function handleAdvance() {
    const next = nextStage(job.data.status);
    await action.run(async () => {
      await updateJobStatus(PLATFORM_SPINE_URL, session.token, jobId, next);
      setSheet(null);
      setToast(`Moved to ${STAGE_LABELS[next]}`);
      await job.reload();
    });
  }

  async function handleGenerate() {
    await action.run(
      async () => {
        await generateQuotation(QUOTATION_URL, session.token, {
          jobId,
          lat: job.data.location.lat,
          lng: job.data.location.lng,
          jobType: job.data.job_type,
        });
        setToast("Quotation sent to the customer");
        await quote.reload();
      },
      {
        onError: (err) => (err.code === "PRICING_RULE_MISSING"
          ? `Set your pricing rule for ${jobTypeLabel(job.data.job_type, true).toLowerCase()} jobs before quoting - open Setup.`
          : err.message),
      }
    );
  }

  if (job.loading && !job.data) return <Screen><Card><Loading label="Loading job…" /></Card></Screen>;
  if (job.error) {
    return (
      <Screen>
        <Alert>{job.error.message}</Alert>
        <Button title="Try again" variant="light" onPress={() => job.reload()} />
        <Button title="Back" variant="light" onPress={goBack} />
      </Screen>
    );
  }

  const next = nextStage(job.data.status);
  const atCompletion = job.data.status === "completion";

  return (
    <Screen>
      <PageHeader
        eyebrow={`${shortId(jobId)} · ${jobTypeLabel(job.data.job_type, true)}${area ? ` · ${area.name}` : ""}`}
        title={area ? `${area.name} site` : "Job"}
        subtitle={formatCoords(job.data.location.lat, job.data.location.lng)}
        right={<Badge tone={stageTone(job.data.status)}>{STAGE_LABELS[job.data.status]}</Badge>}
      />

      {!!action.error && <Alert>{action.error}</Alert>}

      <Card dark>
        <Row>
          <Eyebrow dark>Stage {stageIndex(job.data.status) + 1} of {JOB_STAGES.length}</Eyebrow>
          <View style={{ flex: 1 }} />
          <Body size={13} muted dark>{STAGE_LABELS[job.data.status]}</Body>
        </Row>
        {next ? (
          <Button title={`Advance to ${STAGE_LABELS[next]}`} variant="saffron" trailing onPress={() => setSheet("advance")} />
        ) : (
          <Body muted dark>This job is closed - there is no stage after this one.</Body>
        )}
        <Button title="See all 14 stages" variant="ghostDark" size="sm" onPress={() => setSheet("stages")} />
      </Card>

      <Card>
        <Row>
          <Title size={20}>Quotation</Title>
          <View style={{ flex: 1 }} />
          {q && <Badge tone={quoteTone(q.status)}>{quoteLabel(q.status)}</Badge>}
        </Row>

        {quote.loading && !quote.data && <Loading label="Checking for a quotation…" />}

        {!q && !quote.loading && (
          <>
            <Body muted size={14}>
              No quotation yet. Generating one uses your pricing rules and, inside a pilot area, the local
              water-table estimate instead of your flat assumed depth.
            </Body>
            <Button
              title={action.busy ? "Generating…" : "Generate quotation"}
              trailing
              busy={action.busy}
              onPress={handleGenerate}
            />
          </>
        )}

        {q && (
          <>
            <Inset>
              <Row gap={12}>
                <View style={{ flex: 1, gap: 4 }}>
                  <Body size={13} muted>Depth estimate · v{q.version}</Body>
                  <Amount size={23}>{q.estimated_depth_range.min_ft}–{q.estimated_depth_range.max_ft} ft</Amount>
                  <View style={{ alignSelf: "flex-start" }}>
                    <Badge tone={confidenceTone(q.estimated_depth_range.confidence)}>
                      {capitalise(q.estimated_depth_range.confidence)} confidence
                    </Badge>
                  </View>
                </View>
                <DepthGauge
                  min={q.estimated_depth_range.min_ft}
                  max={q.estimated_depth_range.max_ft}
                  water={area?.estimated_water_depth_ft}
                  height={180}
                  width={104}
                />
              </Row>
              <Body size={12} muted>
                {area
                  ? `${area.name} water table ~${area.estimated_water_depth_ft} ft ± ${area.confidence_band_ft}.`
                  : "Outside the pilot areas - your flat assumed depth was used."}
                {q.depth_overage_rate_per_ft ? ` Over ${q.estimated_depth_range.max_ft} ft: ${formatInr(q.depth_overage_rate_per_ft)}/ft.` : ""}
              </Body>
            </Inset>

            <View style={{ gap: 8 }}>
              {q.line_items.map((item, i) => (
                <ReceiptRow key={`${item.label}-${i}`} label={item.label} amount={item.amount} />
              ))}
              <ReceiptRow label={`Subtotal ${formatInr(q.subtotal)} + margin`} amount={q.margin_amount} />
            </View>

            {q.minimum_charge_applied && (
              <Alert tone="info">Minimum job charge applied - the calculated total was below your floor.</Alert>
            )}

            <View style={{ flexDirection: "row", alignItems: "center", backgroundColor: colors.chrome, borderRadius: 16, padding: 16 }}>
              <Body size={15} weight="600" dark>Total estimate</Body>
              <View style={{ flex: 1 }} />
              <Amount size={24} color={colors.saffron}>{formatInr(q.total_estimate)}</Amount>
            </View>

            <Button title={`Edit as v${q.version + 1}`} variant="light" size="sm" onPress={() => setSheet("edit")} />
          </>
        )}
      </Card>

      {atCompletion && !completion.data && (
        <CompletionCard
          jobId={jobId}
          quote={q}
          onDone={async () => { await completion.reload(); await job.reload(); setToast("Completion recorded"); }}
        />
      )}

      {completion.data && (
        <Card>
          <Title size={20}>Completion</Title>
          <Row gap={24} style={{ flexWrap: "wrap" }}>
            <KeyValue k="Actual depth" v={`${completion.data.actual_depth_ft} ft`} />
            <KeyValue k="Quoted" v={formatInr(completion.data.quoted_total)} />
            <KeyValue k="Actual cost" v={formatInr(completion.data.actual_cost)} />
          </Row>
          <Row gap={24} style={{ flexWrap: "wrap" }}>
            <View style={{ gap: 2 }}>
              <Body size={13} muted>Variance</Body>
              <Body size={16} weight="700" style={{ color: Number(completion.data.variance) > 0 ? colors.red : colors.green }}>
                {Number(completion.data.variance) > 0 ? "+" : ""}{formatInr(completion.data.variance)}
              </Body>
            </View>
            {Number(completion.data.depth_overage_ft) > 0 && (
              <KeyValue
                k="Depth overage"
                v={`${completion.data.depth_overage_ft} ft · ${formatInr(completion.data.depth_overage_charge)}`}
              />
            )}
          </Row>
        </Card>
      )}

      <Card dark>
        <Row>
          <Title size={20} dark>Rig booking</Title>
          <View style={{ flex: 1 }} />
          {jobBookings.length > 0
            ? <Badge tone={bookingTone(jobBookings[0].status)}>{BOOKING_STATUS_LABELS[jobBookings[0].status]}</Badge>
            : <Badge>None yet</Badge>}
        </Row>
        {jobBookings.length === 0 ? (
          <>
            <Body muted dark size={14}>No rig requested for this site yet.</Body>
            <Button title="Find nearby rigs" variant="saffron" trailing onPress={() => navigate("contractor.rigs", { jobId })} />
          </>
        ) : (
          <>
            {jobBookings.map((b) => (
              <Inset dark key={b.booking_id}>
                <Row gap={10}>
                  <Icon name="truck" size={20} color="#fff" />
                  <View style={{ flex: 1, gap: 1 }}>
                    {/* GET /v1/resources is resource_owner-only, so a contractor
                        can't resolve another owner's rig name here - the search
                        screen is where names come from. Showing the short id
                        keeps this honest rather than inventing a label. */}
                    <Body weight="600" dark>Requested rig</Body>
                    <Body size={12} muted dark style={{ fontVariant: ["tabular-nums"] }}>{b.resource_id.slice(0, 8)}</Body>
                  </View>
                  <Badge tone={bookingTone(b.status)}>{BOOKING_STATUS_LABELS[b.status]}</Badge>
                </Row>
              </Inset>
            ))}
            <Button title="Search again" variant="ghostDark" size="sm" onPress={() => navigate("contractor.rigs", { jobId })} />
          </>
        )}
      </Card>

      <Card>
        <Row>
          <Title size={20}>Payment</Title>
          <View style={{ flex: 1 }} />
          {payment ? <Badge tone={paymentTone(payment.status)}>{PAYMENT_LABELS[payment.status] || payment.status}</Badge> : <Badge>Not started</Badge>}
        </Row>
        <Body size={14} muted>
          {payment
            ? `${formatInr(payment.amount)} · ${payment.status === "completed" ? "confirmed by the Razorpay webhook" : "waiting on the customer"}`
            : "The customer pays after approving the quotation."}
        </Body>
      </Card>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <SiteMap marker={job.data.location} center={job.data.location} zoom={13} interactive={false} height={150} />
        <View style={{ padding: 16, gap: 2 }}>
          <Body weight="600">{area ? `${area.name}, ${area.district}` : "Outside pilot areas"}</Body>
          <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>
            {formatCoords(job.data.location.lat, job.data.location.lng)}
          </Body>
        </View>
      </Card>

      <Confirm
        visible={sheet === "advance"}
        title={next ? `Move to ${STAGE_LABELS[next]}?` : ""}
        body="Stages only move forward, one step at a time - this can't be undone from the app."
        confirmLabel={next ? `Move to ${STAGE_LABELS[next]}` : "Move"}
        busy={action.busy}
        onConfirm={handleAdvance}
        onClose={() => setSheet(null)}
      />

      <Sheet visible={sheet === "stages"} title="Job stages" onClose={() => setSheet(null)}>
        <StageRail status={job.data.status} />
      </Sheet>

      {q && (
        <EditQuoteSheet
          visible={sheet === "edit"}
          quote={q}
          onClose={() => setSheet(null)}
          onSaved={async () => { setSheet(null); setToast("New version sent"); await quote.reload(); }}
        />
      )}

      <Toast message={toast} />
    </Screen>
  );
}

function ReceiptRow({ label, amount }) {
  return (
    <Row>
      <Body size={14} style={{ flexShrink: 1 }}>{label}</Body>
      <View style={{ flex: 1, height: 1, marginHorizontal: 8, backgroundColor: colors.line }} />
      <Body size={14} weight="700" style={{ fontVariant: ["tabular-nums"] }}>{formatInr(amount)}</Body>
    </Row>
  );
}

function CompletionCard({ jobId, quote, onDone }) {
  const { session } = useSession();
  const action = useAction();
  const [depth, setDepth] = useState("");
  const [cost, setCost] = useState("");
  const [confirming, setConfirming] = useState(false);

  const overage = quote && Number(depth) > Number(quote.estimated_depth_range.max_ft)
    ? Number(depth) - Number(quote.estimated_depth_range.max_ft)
    : 0;

  async function submit() {
    await action.run(async () => {
      await logJobCompletion(PLATFORM_SPINE_URL, session.token, jobId, {
        actualDepthFt: Number(depth),
        actualCost: Number(cost),
      });
      setConfirming(false);
      await onDone();
    });
  }

  return (
    <Card>
      <Title size={20}>Close out this job</Title>
      <Body size={14} muted>
        Recorded once and never editable afterwards - variance against the approved quotation is computed at write time.
      </Body>
      <Field label="Actual depth drilled (ft)">
        <Input value={depth} onChangeText={setDepth} keyboardType="number-pad" placeholder="e.g. 468" />
      </Field>
      <Field label="Actual cost (₹)">
        <Input value={cost} onChangeText={setCost} keyboardType="decimal-pad" placeholder="e.g. 99500" />
      </Field>
      {overage > 0 && quote?.depth_overage_rate_per_ft && (
        <Alert tone="info">
          {overage} ft beyond the quoted range - an overage charge at {formatInr(quote.depth_overage_rate_per_ft)}/ft is added automatically.
        </Alert>
      )}
      {!!action.error && <Alert>{action.error}</Alert>}
      <Button title="Mark complete" disabled={!depth || !cost} onPress={() => setConfirming(true)} />
      <Confirm
        visible={confirming}
        title="Mark this job complete?"
        body={`Recording ${depth} ft and ${formatInr(cost)}. This is written once and can't be changed later.`}
        confirmLabel="Mark complete"
        busy={action.busy}
        onConfirm={submit}
        onClose={() => setConfirming(false)}
      />
    </Card>
  );
}

function EditQuoteSheet({ visible, quote, onClose, onSaved }) {
  const { session } = useSession();
  const action = useAction();
  const [items, setItems] = useState(() => quote.line_items.map((i) => ({ ...i, amount: String(i.amount) })));

  const subtotal = items.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
  const total = subtotal + Number(quote.margin_amount || 0);

  async function save() {
    await action.run(async () => {
      await editQuotation(QUOTATION_URL, session.token, quote.quotation_id, {
        lineItems: items.map((i) => ({ label: i.label, amount: Number(i.amount) })),
        totalEstimate: Number(total.toFixed(2)),
      });
      await onSaved();
    });
  }

  return (
    <Sheet
      visible={visible}
      title={`Edit as v${quote.version + 1}`}
      onClose={onClose}
      actions={
        <Row gap={10}>
          <Button title="Cancel" variant="light" style={{ flex: 1 }} onPress={onClose} />
          <Button title={action.busy ? "Sending…" : `Send v${quote.version + 1}`} style={{ flex: 1.4 }} busy={action.busy} onPress={save} />
        </Row>
      }
    >
      <Body size={14} muted>
        The original version is never changed - the customer sees this as a new version of the same quote.
      </Body>
      {items.map((item, i) => (
        <Field key={`${item.label}-${i}`} label={item.label}>
          <Input
            value={item.amount}
            keyboardType="decimal-pad"
            onChangeText={(value) => setItems((list) => list.map((it, idx) => (idx === i ? { ...it, amount: value } : it)))}
          />
        </Field>
      ))}
      <Inset>
        <Row>
          <Body size={13} muted style={{ flex: 1 }}>
            Subtotal {formatInr(subtotal.toFixed(2))} + margin {formatInr(quote.margin_amount)}
          </Body>
          <Amount size={22}>{formatInr(total.toFixed(2))}</Amount>
        </Row>
      </Inset>
      {!!action.error && <Alert>{action.error}</Alert>}
    </Sheet>
  );
}

function quoteTone(status) {
  return { approved: "green", rejected: "red", draft: "saffron", sent: "saffron" }[status] || "neutral";
}

function quoteLabel(status) {
  return { approved: "Approved", rejected: "Changes requested", draft: "Awaiting approval", sent: "Awaiting approval" }[status] || status;
}

function confidenceTone(confidence) {
  return { high: "green", medium: "saffron", low: "red" }[confidence] || "neutral";
}

function paymentTone(status) {
  return { completed: "green", pending: "saffron", failed: "red" }[status] || "neutral";
}

const PAYMENT_LABELS = { completed: "Paid", pending: "Awaiting payment", failed: "Failed" };

function capitalise(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}
