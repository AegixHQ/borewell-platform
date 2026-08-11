# AGENTS.md — resource-network

Read the root `AGENTS.md` first.

## This service owns
- Inventory state machine: `Available → Reserved → Assigned → In Use →
  Returned` (original vision doc §7). Don't add new states without
  checking this is actually necessary — the 5-state model is deliberate.
- Resource Matching Engine (`app/matching/`) — ranks and suggests, never
  auto-assigns. The contractor always makes the final call (RFC §9.2 FR-K7).

## Contract
`packages/contracts/openapi/resource-network.yaml`
