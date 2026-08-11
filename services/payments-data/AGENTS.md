# AGENTS.md — payments-data

Read the root `AGENTS.md` first.

## This service owns
- Payments & Split Settlement (`app/payments/`) — every payment mutation
  requires an idempotency key (RFC 0001 §5). Never write a payment endpoint
  that can be safely retried without one; a retried request must not
  double-charge or double-payout.
- Data & Analytics (`app/analytics/`) — reacts to `job.completed` events;
  doesn't call other services synchronously for this.

## Contract
`packages/contracts/openapi/payments-data.yaml`

## Money-specific rule
If a task touches anything that moves money, don't guess the split logic —
it's defined in RFC 0001 §14. If the task needs a split rule that isn't
there, that's a spec discussion, not an implementation detail to improvise.
