#!/usr/bin/env python3
"""Load demo data into a running Borewell stack so a demo works out of the box.

    python3 tools/seed-demo/seed_demo.py

Standard library only. Safe to run more than once. Creates three accounts
(all with the password printed at the end), two rigs, three service areas
and a pricing rule for each job type. It never touches existing accounts'
passwords.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

SPINE = os.getenv("PLATFORM_SPINE_URL", "http://localhost:8001")
QUOTATION = os.getenv("QUOTATION_URL", "http://localhost:8002")
NETWORK = os.getenv("RESOURCE_NETWORK_URL", "http://localhost:8003")
PASSWORD = "demo-password-123"
ACCOUNTS = {
    "customer": "customer@example.com",
    "contractor": "contractor@example.com",
    "resource_owner": "owner@example.com",
}

AREAS = [
    ("Virudhunagar", 9.5851, 77.9624, 280),
    ("Madurai", 9.9252, 78.1198, 320),
    ("Coimbatore", 11.0168, 76.9558, 380),
]
RIGS = [
    ("Sri Murugan DTH Rig", "DTH Rig - Truck Mounted", "850.00", 9.5851, 77.9624),
    ("Kaveri Borewell Works", "Rotary Rig - Truck Mounted", "950.00", 9.9252, 78.1198),
]
PRICING = {
    "residential": dict(base_rate_per_ft=120, assumed_depth_ft=300),
    "agricultural": dict(base_rate_per_ft=95, assumed_depth_ft=400),
    "commercial": dict(base_rate_per_ft=150, assumed_depth_ft=450),
}


def call(method, url, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw.decode(errors="replace")


def wait_ready():
    for base in (SPINE, QUOTATION, NETWORK):
        for _ in range(60):
            try:
                if call("GET", f"{base}/readyz")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(2)
        else:
            sys.exit(f"The backend is not answering on {base}. Start it first.")


def account(role, email):
    creds = {"email": email, "password": PASSWORD}
    status, body = call("POST", f"{SPINE}/v1/auth/register", {**creds, "role": role})
    if status not in (201, 409):
        sys.exit(f"Could not create {role} account: {status} {body}")
    status, body = call("POST", f"{SPINE}/v1/auth/login", creds)
    if status != 200:
        sys.exit(
            f"{email} exists but the demo password does not work ({status}). "
            "Reset the demo data (docker compose down -v) and run again."
        )
    return body["access_token"]


def main():
    wait_ready()
    tokens = {role: account(role, email) for role, email in ACCOUNTS.items()}
    print("accounts ready")

    status, existing = call("GET", f"{NETWORK}/v1/resources", token=tokens["resource_owner"])
    have = {r["name"] for r in existing} if status == 200 and isinstance(existing, list) else set()
    for name, vehicle, rate, lat, lng in RIGS:
        if name in have:
            continue
        status, body = call(
            "POST",
            f"{NETWORK}/v1/resources",
            dict(resource_type="rig", name=name, vehicle_type=vehicle, hourly_rate=rate,
                 lat=lat, lng=lng),
            tokens["resource_owner"],
        )
        if status != 201:
            sys.exit(f"Could not list rig {name}: {status} {body}")
    print("rigs listed")

    for name, lat, lng, depth in AREAS:
        status, body = call(
            "POST",
            f"{NETWORK}/v1/service-areas",
            dict(name=name, district=name, state="Tamil Nadu", center_lat=lat, center_lng=lng,
                 radius_km=25, estimated_water_depth_ft=depth, confidence_band_ft=40),
            tokens["contractor"],
        )
        if status not in (200, 201):
            sys.exit(f"Could not add service area {name}: {status} {body}")
    print("service areas added")

    for job_type, extra in PRICING.items():
        rule = dict(
            job_type=job_type, casing_rate_per_ft=40, labour_flat_fee=5000, transport_flat_fee=3000,
            equipment_flat_fee=2000, installation_flat_fee=4000, margin_percent=15,
            minimum_job_charge=30000, depth_confidence_band_ft=50, depth_overage_rate_per_ft=150,
        )
        rule.update(extra)
        status, body = call("POST", f"{QUOTATION}/v1/pricing-rules", rule, tokens["contractor"])
        if status not in (200, 201):
            sys.exit(f"Could not set pricing for {job_type}: {status} {body}")
    print("pricing rules set")

    print("\nDemo logins (password for all: " + PASSWORD + ")")
    for role, email in ACCOUNTS.items():
        print(f"  {role:<15} {email}")


if __name__ == "__main__":
    main()
