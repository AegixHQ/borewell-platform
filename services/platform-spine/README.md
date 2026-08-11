# platform-spine

Identity/RBAC, Job Orchestration state machine, Notifications, Gateway routing

## Local dev (standalone, without docker-compose)

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

Contract for this service: `packages/contracts/openapi/platform-spine.yaml`
