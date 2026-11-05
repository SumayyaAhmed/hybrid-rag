# 07 — Makefile (short commands)

Status: **implemented**

## Why
Commands like `docker compose exec db psql -U rag -d rag` or `uv run alembic upgrade head` are long and easy to mistype.
`make <target>` gives one short, discoverable name per task. `make` / `make help` lists them all.

## Rules
- The Makefile only **wraps** existing commands and adds no logic of its own. Each target is one or two lines, so you can read it and run the command by hand.
- Arguments are passed as variables: `make search Q="waterproof shoes"`, `make migration M="add brand index"`.
- New target = add a `## description` comment so it shows up in `make help`.

## Targets
| Group | Target | Runs |
|---|---|---|
| Setup | `install` | `uv sync` |
| | `data` | `uv run python scripts/make_sample_data.py` |
| Database | `up` / `down` | `docker compose up -d --build --wait` / `docker compose down` |
| | `reset` | `docker compose down -v`, then `up` → `migrate` → `ingest` (**deletes all data**, asks to confirm) |
| | `psql` | `docker compose exec db psql -U rag -d rag` |
| | `logs` | `docker compose logs -f db` |
| Migrations | `migrate` | `uv run alembic upgrade head` |
| | `migration M=…` | `uv run alembic revision -m "$(M)" --rev-id <next number>` |
| | `downgrade` | `uv run alembic downgrade -1` |
| | `db-version` | `uv run alembic current` + `history` |
| RAG | `ingest` / `stats` | `uv run rag ingest` / `uv run rag stats` |
| | `search Q=…` | `uv run rag search "$(Q)" --explain` |
| | `ask Q=…` | `uv run rag ask "$(Q)"` |
| | `chat` | `uv run python app.py` |
| App container (08) | `app-build` / `app-chat` | `docker compose build app` / `docker compose run --rm app` |
| | `app-cli ARGS=…` | `docker compose run --rm app rag $(ARGS)` |
| | `app-migrate` | `docker compose run --rm app alembic upgrade head` |
| API (10) | `api` / `api-logs` | `uv run fastapi dev` / `docker compose logs -f api` |
| Quality | `lint` | `uv run ruff check .` |
| | `test` | `uv run pytest -q -m "not db"` (unit) |
| | `test-db` | `uv run pytest -q -m db` (integration, `rag_test` DB) |
| | `ci` | lint + test + test-db + app image build (spec 09) |
| | `eval` | `uv run python eval/run_eval.py` |

`migration` computes the next 4-digit rev id from the files in `db/migrations/versions/`, keeping the readable `0001, 0002…` ids from 05.
