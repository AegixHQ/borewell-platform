#!/usr/bin/env python3
"""Every path in the OpenAPI contracts must be routed by the Traefik labels in
docker-compose.prod.yml - otherwise it works on :800x and 404s through the
gateway, which is the only door in production (found for real: GET
/v1/analytics/estimate-accuracy was unrouted).

    python3 tools/go-live/check_gateway_routes.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ["platform-spine", "quotation", "resource-network", "payments-data"]


def prefixes(compose: dict, service: str):
    for label in compose["services"][service].get("labels", []):
        if label.startswith(f"traefik.http.routers.{service}.rule="):
            return re.findall(r"PathPrefix\(`([^`]+)`\)", label)
    return []


def check(root: Path = ROOT):
    compose = yaml.safe_load((root / "docker-compose.prod.yml").read_text())
    problems = []
    for service in SERVICES:
        routed = prefixes(compose, service)
        if not routed:
            problems.append(f"{service}: no Traefik router rule found")
            continue
        spec = yaml.safe_load((root / f"packages/contracts/openapi/{service}.yaml").read_text())
        for path in spec["paths"]:
            if not any(path == p or path.startswith(p + "/") for p in routed):
                problems.append(f"{service}: {path} is not covered by the gateway rule {routed}")
    # A prefix claimed by two services would send traffic to the wrong one.
    owners = {}
    for service in SERVICES:
        for p in prefixes(compose, service):
            if p in owners:
                problems.append(f"{p} is routed to both {owners[p]} and {service}")
            owners[p] = service
    return problems


if __name__ == "__main__":
    found = check()
    for line in found:
        print("ERROR", line)
    print("Gateway routes cover every contract path." if not found else f"{len(found)} problem(s).")
    sys.exit(1 if found else 0)
