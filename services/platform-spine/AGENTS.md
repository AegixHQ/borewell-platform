# AGENTS.md — platform-spine

Read the root `AGENTS.md` first.

## This service owns
- The job state machine (RFC 0001 §8) — the *only* place a job's status is
  allowed to change. No other service should ever set job status directly;
  if you find yourself doing that in another service, stop, that's a
  contract violation.
- Auth/JWT issuance. Other services verify tokens locally; they don't call
  back here to check one (see RFC §5).

## Contract
`packages/contracts/openapi/platform-spine.yaml`

## Before adding a job status value or transition
Check `docs/rfc/0001-microservices-architecture.md` §8 for the existing
state list before inventing a new one. If the task genuinely needs a new
state, that's a contract + RFC update, not a same-PR addition.
