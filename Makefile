.PHONY: up down logs test lint check-contracts

up:
	docker compose up --build

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
