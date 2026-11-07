/**
 * One borewell, from the customer's side: the quotation, approve or ask for
 * changes, payment, and the final result. Ported from
 * apps/web-app/src/pages/customer/CustomerJob.jsx - same call sequence,
 * same handling of the expected 404s.
 */
import { useState } from "react";
import { View } from "react-native";
import {
  PAYMENTS_URL, PLATFORM_SPINE_URL, QUOTATION_URL,
  approveQuotation, createPayment, createRazorpayOrder, getJob,
  getJobCompletionResult, getLatestQuotationForJob, listPayments, rejectQuotation,
} from "../../services/platform";
import {
  STAGE_LABELS, colors, customerStepIndex, formatCoords, formatInr, jobTypeLabel,
  shortId, stageTone,
} from "../../theme";
import { useAction, useAreaName, useLoad, useToast } from "../../lib/hooks";
import { useNav } from "../../lib/nav";
import { useSession } from "../../lib/session";
import { openCheckout } from "../../lib/checkout";
import { PageHeader } from "../../components/AppShell";
import DepthGauge from "../../components/DepthGauge";
import SiteMap from "../../components/SiteMap";
import { CustomerSteps } from "../../components/StageViews";
import {
  Alert, Amount, Badge, Body, Button, Card, Confirm, Eyebrow, Icon, Inset,
  KeyValue, Loading, Row, Screen, Title, Toast,
} from "../../components/ui";

export default function CustomerJob({ params }) {
  const { jobId } = params;
  const { session } = useSession();
  const { goBack } = useNav();
  const [toast, setToast] = useToast();
  const [confirm, setConfirm] = useState(null);
  const action = useAction();

  const job = useLoad(() => getJob(PLATFORM_SPINE_URL, session.token, jobId), [jobId], { pollMs: 20000 });
  const quote = useLoad(
    () => getLatestQuotationForJob(QUOTATION_URL, session.token, jobId).catch((err) => {
      // 404 until the contractor generates one - an expected state, not an error.
      if (err.code === "QUOTATION_NOT_FOUND" || err.status === 404) return null;
      throw err;
    }),
    [jobId],
    { pollMs: 15000 }
  );
  const payments = useLoad(() => listPayments(PAYMENTS_URL, session.token), [jobId], { pollMs: 15000 });
  const completion = useLoad(
    () => getJobCompletionResult(PLATFORM_SPINE_URL, session.token, jobId).catch((err) => {
      if (err.status === 404) return null;
      throw err;
    }),
    [jobId]
  );

  const area = useAreaName(job.data?.location?.lat, job.data?.location?.lng);
  const payment = (payments.data || []).find((p) => p.job_id === jobId) || null;
  const q = quote.data;

  async function handleApprove() {
    await action.run(async () => {
      await approveQuotation(QUOTATION_URL, session.token, q.quotation_id);
      setConfirm(null);
      setToast("Quotation approved");
      await Promise.all([quote.reload(), job.reload()]);
    });
  }

  async function handleReject() {
    await action.run(async () => {
      await rejectQuotation(QUOTATION_URL, session.token, q.quotation_id);
      setConfirm(null);
      setToast("Change request sent to your contractor");
      await quote.reload();
    });
  }

  async function handlePay() {
    await action.run(
      async () => {
        const existing = payment && payment.status === "pending"
          ? payment
          : await createPayment(PAYMENTS_URL, session.token, {
              jobId,
              quotationId: q.quotation_id,
              // decimal string, passed through untouched so the backend's
              // exact-amount check has something exact to compare
              amount: q.total_estimate,
              idempotencyKey: `job-${jobId}-quote-${q.quotation_id}`,
            });
        const order = await createRazorpayOrder(PAYMENTS_URL, session.token, existing.payment_id);
        const result = await openCheckout({ order });
        await payments.reload();
        if (result.attempted) setToast("Payment submitted - confirming with the bank");
        if (result.unsupported) {
          action.setError(
            "The order is created and waiting, but the Razorpay sheet can't open in this build yet - finish this payment on the web app and it will show as paid here."
          );
        }
      },
      {
        onError: (err) => (err.status === 502
          ? "Online payment isn't switched on for this server yet (Razorpay keys are missing). Your contractor can still take payment directly."
          : err.message),
      }
    );
  }

  if (job.loading && !job.data) return <Screen><Card><Loading label="Loading your job…" /></Card></Screen>;
  if (job.error) {
    return (
      <Screen>
        <Alert>{job.error.message}</Alert>
        <Button title="Try again" variant="light" onPress={() => job.reload()} />
        <Button title="Back" variant="light" onPress={goBack} />
      </Screen>
    );
  }

  const step = customerStepIndex(job.data.status);
  const approved = q?.status === "approved";
  const rejected = q?.status === "rejected";

  return (
    <Screen>
      <PageHeader
        eyebrow={`${shortId(jobId)} · ${jobTypeLabel(job.data.job_type, true)}`}
        title={area ? `${area.name} borewell` : "Your borewell"}
        subtitle={area ? `${area.name}, ${area.district}` : formatCoords(job.data.location.lat, job.data.location.lng)}
        right={<Badge tone={stageTone(job.data.status)}>{STAGE_LABELS[job.data.status]}</Badge>}
      />

      <Card dark>
        <Eyebrow dark>Now</Eyebrow>
        <Title dark size={25}>{headline(job.data.status, q, payment)}</Title>
        <CustomerSteps status={job.data.status} dark />
      </Card>

      {!!quote.error && <Alert>{quote.error.message}</Alert>}
      {!!action.error && <Alert>{action.error}</Alert>}

      {!q && !quote.loading && (
        <Card>
          <Row gap={12}>
            <Icon name="clock" size={22} />
            <View style={{ flex: 1, gap: 2 }}>
              <Body size={16} weight="700">Waiting for your quote</Body>
              <Body size={13} muted>Your contractor is preparing it. This page updates by itself.</Body>
            </View>
          </Row>
        </Card>
      )}

      {q && (
        <Card>
          <Row>
            <Title size={20}>Your quotation</Title>
            <View style={{ flex: 1 }} />
            {approved && <Badge tone="green">Approved</Badge>}
            {rejected && <Badge tone="red">Changes requested</Badge>}
            {!approved && !rejected && <Badge tone="saffron">Awaiting you</Badge>}
          </Row>

          <Inset>
            <Row gap={14} align="center">
              <View style={{ flex: 1, gap: 6 }}>
                <Body size={13} muted>Expected depth</Body>
                <Amount size={26}>{q.estimated_depth_range.min_ft}–{q.estimated_depth_range.max_ft} ft</Amount>
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
                height={190}
                width={104}
              />
            </Row>
            <Body size={13} muted>
              Depth is only certain while drilling.
              {q.depth_overage_rate_per_ft
                ? ` Past ${q.estimated_depth_range.max_ft} ft, each extra foot costs ${formatInr(q.depth_overage_rate_per_ft)}.`
                : ""}
            </Body>
          </Inset>

          <View style={{ gap: 8 }}>
            {q.line_items.map((item, i) => (
              <ReceiptRow key={`${item.label}-${i}`} label={item.label} amount={item.amount} />
            ))}
            <ReceiptRow label="Service charge" amount={q.margin_amount} />
          </View>

          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.chrome,
              borderRadius: 16,
              padding: 16,
            }}
          >
            <Body size={15} weight="600" dark>Total estimate</Body>
            <View style={{ flex: 1 }} />
            <Amount size={24} color={colors.saffron}>{formatInr(q.total_estimate)}</Amount>
          </View>

          {!approved && !rejected && (
            <Row gap={10}>
              <Button title="Ask for changes" variant="light" size="sm" style={{ flex: 1 }} onPress={() => setConfirm("reject")} />
              <Button title="Approve" variant="saffron" size="sm" style={{ flex: 1 }} onPress={() => setConfirm("approve")} />
            </Row>
          )}

          {rejected && (
            <Alert tone="info">
              You asked for changes. Your contractor will send a new version - it will appear here.
            </Alert>
          )}
        </Card>
      )}

      {approved && (
        <Card>
          <Row>
            <Title size={20}>Payment</Title>
            <View style={{ flex: 1 }} />
            {payment ? <Badge tone={paymentTone(payment.status)}>{paymentLabel(payment.status)}</Badge> : <Badge>Not started</Badge>}
          </Row>

          {payment?.status === "completed" ? (
            <Row gap={24}>
              <KeyValue k="Paid" v={formatInr(payment.amount)} />
              {!!payment.razorpay_payment_id && <KeyValue k="Reference" v={payment.razorpay_payment_id} />}
            </Row>
          ) : (
            <>
              <Body size={14} muted>
                Pay with UPI, card or net banking. Your payment is confirmed by the bank, not by this screen.
              </Body>
              <Amount>{formatInr(q.total_estimate)}</Amount>
              <Button
                title={action.busy ? "Opening…" : payment ? "Continue payment" : "Pay now"}
                variant="saffron"
                size="lg"
                trailing
                busy={action.busy}
                onPress={handlePay}
              />
              {payment?.status === "pending" && (
                <>
                  <Alert tone="info">Waiting for the bank to confirm this payment.</Alert>
                  <Button title="Check again" variant="light" size="sm" onPress={() => payments.reload()} />
                </>
              )}
              {payment?.status === "failed" && <Alert>That attempt failed. You can try again.</Alert>}
            </>
          )}
        </Card>
      )}

      {completion.data && (
        <Card>
          <Title size={20}>Final result</Title>
          <Row gap={24} style={{ flexWrap: "wrap" }}>
            <KeyValue k="Actual depth" v={`${completion.data.actual_depth_ft} ft`} />
            <KeyValue k="Quoted" v={formatInr(completion.data.quoted_total)} />
            <KeyValue k="Final cost" v={formatInr(completion.data.actual_cost)} />
          </Row>
          {Number(completion.data.depth_overage_charge) > 0 && (
            <KeyValue k="Extra depth charge" v={formatInr(completion.data.depth_overage_charge)} />
          )}
        </Card>
      )}

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <SiteMap marker={job.data.location} center={job.data.location} zoom={13} interactive={false} height={160} />
        <View style={{ padding: 16, gap: 2 }}>
          <Body weight="600">{area ? `${area.name}, ${area.district}` : "Site location"}</Body>
          <Body size={12} muted style={{ fontVariant: ["tabular-nums"] }}>
            {formatCoords(job.data.location.lat, job.data.location.lng)}
          </Body>
        </View>
      </Card>

      <Card>
        <Title size={20}>What happens next</Title>
        <Step n={1} text="Your contractor books a rig near your site." />
        <Step n={2} text="Drilling starts on the agreed day." />
        <Step n={3} text="Actual depth and final cost are recorded here when the job closes." />
        {step >= 3 && <Alert tone="info">Drilling has started. Updates appear here as your contractor logs them.</Alert>}
      </Card>

      <Confirm
        visible={confirm === "approve"}
        title="Approve this quotation?"
        body={q ? `You're approving ${formatInr(q.total_estimate)} for a depth of ${q.estimated_depth_range.min_ft}–${q.estimated_depth_range.max_ft} ft. You can pay straight after.` : ""}
        confirmLabel="Approve"
        busy={action.busy}
        onConfirm={handleApprove}
        onClose={() => setConfirm(null)}
      />
      <Confirm
        visible={confirm === "reject"}
        title="Ask for changes?"
        body="Your contractor will be able to send a new version of this quote. Nothing is charged."
        confirmLabel="Send request"
        busy={action.busy}
        onConfirm={handleReject}
        onClose={() => setConfirm(null)}
      />
      <Toast message={toast} />
    </Screen>
  );
}

function ReceiptRow({ label, amount }) {
  return (
    <Row>
      <Body size={14}>{label}</Body>
      <View style={{ flex: 1, height: 1, marginHorizontal: 8, backgroundColor: colors.line }} />
      <Body size={14} weight="700" style={{ fontVariant: ["tabular-nums"] }}>{formatInr(amount)}</Body>
    </Row>
  );
}

function Step({ n, text }) {
  return (
    <Row gap={10} align="flex-start">
      <View
        style={{
          width: 22, height: 22, borderRadius: 11, backgroundColor: colors.ground,
          alignItems: "center", justifyContent: "center", marginTop: 1,
        }}
      >
        <Body size={12} weight="700">{n}</Body>
      </View>
      <Body size={14} style={{ flex: 1 }}>{text}</Body>
    </Row>
  );
}

function headline(status, quote, payment) {
  if (status === "service_history") return "Job complete";
  if (status === "completion" || status === "payment") return "Drilling finished";
  if (status === "drilling" || status === "progress") return "Drilling in progress";
  if (payment?.status === "completed") return "Payment received";
  if (quote?.status === "approved") return "Approved - ready to pay";
  if (quote?.status === "rejected") return "Waiting for a revised quote";
  if (quote) return "Your quote is ready";
  return "Request received";
}

function capitalise(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function confidenceTone(confidence) {
  return { high: "green", medium: "saffron", low: "red" }[confidence] || "neutral";
}

function paymentTone(status) {
  return { completed: "green", pending: "saffron", failed: "red" }[status] || "neutral";
}

function paymentLabel(status) {
  return { completed: "Paid", pending: "Awaiting confirmation", failed: "Failed" }[status] || status;
}
