# quotation

Location Intelligence and Estimation Engine, Quotation and Pricing Engine

## Local dev (standalone, without docker-compose)

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

Contract for this service: `packages/contracts/openapi/quotation.yaml`
