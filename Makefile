.PHONY: up down logs test lint lint-frontend lint-app lint-all check-contracts migrate prod-init prod-check prod-deploy prod-smoke prod-contractor prod-backup prod-up prod-down prod-logs

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

lint-frontend:
	npm run lint

lint-app:
	cd apps/borewell-native && npm run lint

lint-all: lint lint-frontend lint-app

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

# Production - the short path (see docs/deployment/GO-LIVE.md):
#   make prod-init DOMAIN=api.yourdomain.in EMAIL=you@yourdomain.in
#   (fill in .env.prod)   make prod-check   make prod-deploy
# HTTPS is on by default; add BORE_NO_TLS=1 for a plain-HTTP test run.
prod-init:
	python3 tools/go-live/init_env.py $(if $(DOMAIN),--domain $(DOMAIN)) $(if $(EMAIL),--email $(EMAIL))

prod-check:
	python3 tools/go-live/preflight.py --dns

prod-deploy:
	tools/go-live/deploy.sh

prod-smoke:
	python3 tools/go-live/smoke.py --env .env.prod

# Create a contractor account by hand (public contractor sign-up is closed).
prod-contractor:
	@test -n "$(EMAIL)" || { echo "usage: make prod-contractor EMAIL=owner@example.com"; exit 1; }
	tools/go-live/stack.sh exec -it platform-spine python -m app.bootstrap create-user --role contractor --email $(EMAIL)

prod-backup:
	./infra/backup/backup.sh

# Plain stack control (reads .env.prod; no preflight, no smoke test).
prod-up:
	tools/go-live/stack.sh up -d --build

prod-down:
	tools/go-live/stack.sh down

prod-logs:
	tools/go-live/stack.sh logs -f
