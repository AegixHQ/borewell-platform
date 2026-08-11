# resource-network

Resource Matching Engine, Inventory (rig/equipment/labour), Document/Media Storage

## Local dev (standalone, without docker-compose)

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

Contract for this service: `packages/contracts/openapi/resource-network.yaml`
