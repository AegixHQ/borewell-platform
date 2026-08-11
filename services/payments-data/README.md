# payments-data

Payments and Split Settlement, Data and Analytics

## Local dev (standalone, without docker-compose)

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

Contract for this service: `packages/contracts/openapi/payments-data.yaml`
