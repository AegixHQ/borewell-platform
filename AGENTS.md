# AGENTS.md — Borewell Platform

Read this before writing any code in this repo, whether you're a human or an
AI agent. If you're an AI coding assistant, treat every instruction below as
binding, not as a suggestion to weigh against your own judgment.

## The three ways hallucination shows up in this repo, and the rule for each

1. **Inventing an endpoint or field that doesn't exist.**
   Rule: `packages/contracts/` is the only place a cross-service field,
   endpoint, or event is allowed to be defined. If you need to call something
   and can't find it in the actual `.yaml` or `.schema.json` file — open the
   file and check, don't infer from the name of a similar-sounding one — it
   does not exist yet. Propose the contract change as its own PR first.

2. **Inventing a library API that doesn't exist.**
   Rule: if you're about to call a method on a dependency already listed in
   `pyproject.toml`/`package.json`, don't assume the signature from a similar
   library you've seen before. If you're not certain, say so, or check the
   installed version's actual interface before writing the call.

3. **Claiming something works without having run it.**
   Rule: never state that tests pass, a service builds, or an endpoint
   behaves a certain way unless you actually ran it in this session and are
   reporting the real output. "This should work" is not the same claim as
   "I ran this and it passed" — say which one you mean.

## Scope discipline (the "unnecessary code" problem)

- Build only what the current task actually asks for. Don't add config
  options, abstraction layers, or "might need this later" functions that
  nothing in the repo currently calls.
- Every new dependency in a `pyproject.toml` or `package.json` needs a
  one-line reason in the PR description — not just "seemed useful."
- No commented-out code, no unused imports, no dead functions. `ruff` (root
  `pyproject.toml`) catches the mechanical cases in CI and pre-commit — but
  the rule is broader than what a linter can see.
- Don't create new files or folders "for organization" if nothing yet needs
  them. An empty abstraction is still unnecessary code.

## Structural changes

Read `STRUCTURE.md` before adding, renaming, or moving any top-level folder.
Short version: you can't do it in a normal PR. It requires an ADR in
`docs/adr/` and sign-off from all 4 service owners.

## Before you touch a service you don't own

Every service's contract is in `packages/contracts/openapi/<service>.yaml`.
Read it. Don't guess another service's behavior from its name — ownership
and domain boundaries are in `README.md` and
`docs/rfc/0001-microservices-architecture.md` §2.

## The AI/Estimation Engine specifically

If your task touches `services/quotation/app/estimation/`, read RFC 0001 §6
first. It has an explicit in-scope/out-of-scope list (no trained models, no
computer vision, output is always a range with a confidence label, never a
single guaranteed number). If a task seems to ask for something on the
"out of scope" list, stop and flag it — don't quietly build it because it's
technically possible.

## Before you say a task is done

- [ ] Ran the actual tests for any service you touched, pasted the real output
- [ ] Ran `python tools/contract-check/check_contract.py <service>` for any
      service touched
- [ ] Every endpoint/field referenced exists in `packages/contracts/` —
      verified by opening the file
- [ ] No new dependency, file, or folder without a stated reason
- [ ] `ruff check .` passes

## Per-directory notes

- `services/<name>/AGENTS.md` — service-specific scope and ownership notes
- `apps/AGENTS.md` — frontend-specific rules
- `packages/contracts/AGENTS.md` — the contract workflow, in detail
