# Short commands for the project. Run `make` to list them. See specs/07-makefile.md.
# Every target is a thin wrapper: read it to learn the real command.

.DEFAULT_GOAL := help
.PHONY: help install data up down reset psql logs migrate migration downgrade db-version \
        ingest stats search ask chat app-build app-chat app-cli app-migrate test eval

MIGRATIONS := db/migrations/versions
# next readable revision id: highest NNNN_*.py + 1 (0001 if none yet)
NEXT_REV := $(shell ls $(MIGRATIONS) 2>/dev/null | grep -Eo '^[0-9]{4}' | sort | tail -1 | awk '{printf "%04d", $$1 + 1}')

help: ## list commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# --- setup -------------------------------------------------------------------
install: ## install Python deps (uv sync)
	uv sync

data: ## regenerate sample PDFs + catalogue in data/
	uv run python scripts/make_sample_data.py

# --- database ----------------------------------------------------------------
up: ## start Postgres (builds the image if needed) and wait until healthy
	docker compose up -d --build --wait

down: ## stop Postgres (data is kept)
	docker compose down

reset: ## DELETE all data, recreate DB, migrate, ingest
	@read -p "This deletes the database volume. Continue? [y/N] " ok && [ "$$ok" = "y" ]
	docker compose down -v
	$(MAKE) up migrate ingest

psql: ## open a psql shell
	docker compose exec db psql -U rag -d rag

logs: ## follow Postgres logs
	docker compose logs -f db

# --- migrations (Alembic, spec 05) ---------------------------------------------
migrate: ## apply pending migrations
	uv run alembic upgrade head

migration: ## new migration: make migration M="add brand index"
	@test -n "$(M)" || (echo 'usage: make migration M="description"' && exit 1)
	uv run alembic revision -m "$(M)" --rev-id $(or $(NEXT_REV),0001)

downgrade: ## undo the last migration
	uv run alembic downgrade -1

db-version: ## show current revision and history
	uv run alembic current
	uv run alembic history

# --- RAG -----------------------------------------------------------------------
ingest: ## ingest data/ (PDFs + catalogue); re-run is a no-op
	uv run rag ingest

stats: ## row counts
	uv run rag stats

search: ## retrieval only, every stage: make search Q="waterproof shoes"
	@test -n "$(Q)" || (echo 'usage: make search Q="question"' && exit 1)
	uv run rag search "$(Q)" --explain

ask: ## full answer: make ask Q="what is the return policy?"
	@test -n "$(Q)" || (echo 'usage: make ask Q="question"' && exit 1)
	uv run rag ask "$(Q)"

chat: ## interactive chat loop
	uv run python app.py

# --- app in a container (spec 08) ----------------------------------------------
app-build: ## build the app image
	docker compose build app

app-chat: ## chat loop inside the container
	docker compose run --rm app

app-cli: ## rag CLI inside the container: make app-cli ARGS='search "SKU 00123" --explain'
	@test -n "$(ARGS)" || (echo "usage: make app-cli ARGS='stats'" && exit 1)
	docker compose run --rm app rag $(ARGS)

app-migrate: ## alembic upgrade head inside the container
	docker compose run --rm app alembic upgrade head

# --- quality -------------------------------------------------------------------
test: ## unit tests
	uv run pytest -q

eval: ## run the 29-question eval (slow: Voyage 3 req/min)
	uv run python eval/run_eval.py
