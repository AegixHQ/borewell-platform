.PHONY: up down logs test lint

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
