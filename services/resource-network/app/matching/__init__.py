"""
Resource Matching Engine - explicitly Phase 1 (RFC 0001 section 7, PRD
out-of-scope list, this service's AGENTS.md). Not implemented in MVP:
resource assignment is manual, driven by the contractor via PATCH
/v1/resources/{id} in app/main.py, not by anything in this module.

This file exists (rather than the folder simply not existing) because the
repo's STRUCTURE.md treats folder layout as stable - the folder was part
of the original service scaffold and stays put rather than being added and
removed as scope shifts. Left empty deliberately; do not add matching logic
here without checking PRD section 10 / RFC section 7 first.
"""
