# AGENTS.md — quotation

Read the root `AGENTS.md` first.

## This service owns
- The Quotation/Pricing Engine (`app/pricing/`)
- The Location Intelligence & Estimation Engine (`app/estimation/`) — **read
  RFC 0001 §6 before touching this folder.** It has an explicit in-scope
  list (rule-based/statistical estimation) and out-of-scope list (any
  trained ML model, computer vision, autonomous pricing decisions).

## Contract
`packages/contracts/openapi/quotation.yaml`

## Before adding a pricing rule
Check `app/pricing/` for an existing rule of the same shape before writing a
new one — contractor pricing rules (base rate, margin, surcharge, etc.) all
follow the pattern from RFC 0001 §9.2/FR-K14; don't invent a new pattern per
rule.
