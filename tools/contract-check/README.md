# contract-check

Compares a service's actual FastAPI routes against its committed OpenAPI
spec. Run before every commit that touches a service (wired into
pre-commit and CI already).

```bash
pip install -r tools/contract-check/requirements.txt
python tools/contract-check/check_contract.py <service-name>
```

Exits non-zero only if code exposes a route the contract doesn't declare.
An unimplemented-but-declared route is printed as informational, not a
failure - that's normal mid-sprint.
