# AGENTS.md — contracts

This directory is the single source of truth for every cross-service field,
endpoint, and event. If it's not defined here, it does not exist yet — no
matter how reasonable the name seems.

## Workflow (don't skip a step)
1. Contract change → its own PR, reviewed by every service owner who
   consumes it, merged first.
2. Implementation PR follows, referencing the merged contract PR.

Never combine steps 1 and 2 in one PR. That's the single most common way a
schema and an implementation silently diverge in a repo where multiple
agents are writing code in parallel.
