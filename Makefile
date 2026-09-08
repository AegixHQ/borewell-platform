.PHONY: up down logs test lint check-contracts migrate prod-up prod-down prod-logs

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	@for svc in platform-spine quotation resource-network payments-data; do \
		echo "== Testing $$svc =="; \
		(cd services/$$svc && python -m pytest) || exit 1; \
	done

lint:
	ruff check services/

check-contracts:
	@for svc in platform-spine quotation resource-network payments-data; do \
		echo "== Checking $$svc against its contract =="; \
		python tools/contract-check/check_contract.py $$svc || exit 1; \
	done

migrate:
	@for svc in platform-spine quotation resource-network payments-data; do \
		echo "== Migrating $$svc =="; \
		(cd services/$$svc && alembic upgrade head) || exit 1; \
	done

# Production targets - see docs/deployment/PRODUCTION.md for the full
# runbook. These assume .env.prod already exists (cp .env.prod.example
# .env.prod, then fill it in) - deliberately NOT auto-created here, since
# a Makefile target that silently creates a secrets file with placeholder
# values is exactly the kind of thing that gets accidentally deployed.
prod-up:
	docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml --env-file .env.prod down

prod-logs:
	docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f
