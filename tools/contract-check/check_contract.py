#!/usr/bin/env python3
"""
Contract conformance check.

Compares a service's actually-registered FastAPI routes against its
committed OpenAPI spec in packages/contracts/openapi/. Fails if the running
code exposes a path/method that isn't declared in the contract - the most
common shape of AI-agent hallucination in this repo: an endpoint invented
because it seemed reasonable, not because it was specified.

Usage:
    python tools/contract-check/check_contract.py <service-name>

Example:
    python tools/contract-check/check_contract.py quotation
"""
import importlib
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Routes FastAPI adds automatically, or that are infra (not business
# contract) - never compared against the OpenAPI spec.
IGNORED_PATHS = {"/healthz", "/readyz", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}


def load_contract_paths(service: str) -> set:
    spec_path = ROOT / "packages" / "contracts" / "openapi" / f"{service}.yaml"
    if not spec_path.exists():
        print(f"No contract found at {spec_path}")
        sys.exit(1)
    spec = yaml.safe_load(spec_path.read_text())
    declared = set()
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            declared.add((method.upper(), path))
    return declared


def load_actual_paths(service: str) -> set:
    service_dir = ROOT / "services" / service
    sys.path.insert(0, str(service_dir))
    app_module = importlib.import_module("app.main")
    app = app_module.app
    actual = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in methods:
            if method == "HEAD":
                continue
            actual.add((method.upper(), path))
    return actual


def main():
    if len(sys.argv) != 2:
        print("Usage: check_contract.py <service-name>")
        sys.exit(1)

    service = sys.argv[1]
    declared = load_contract_paths(service)
    actual = {(m, p) for m, p in load_actual_paths(service) if p not in IGNORED_PATHS}

    undeclared = actual - declared
    unimplemented = declared - actual

    if undeclared:
        print(f"UNDECLARED ROUTES in {service} (exist in code, not in contract):")
        for method, path in sorted(undeclared):
            print(f"  {method} {path}")

    if unimplemented:
        print(f"UNIMPLEMENTED ROUTES in {service} (declared in contract, not built yet):")
        for method, path in sorted(unimplemented):
            print(f"  {method} {path}")

    if undeclared:
        print("\nFAIL: code exposes endpoints the contract doesn't define.")
        print("Either the contract needs a PR first, or this route shouldn't exist.")
        sys.exit(1)

    print(f"OK: no undeclared routes in {service}.")
    if unimplemented:
        print("(Unimplemented routes are informational only - not a failure.)")


if __name__ == "__main__":
    main()
