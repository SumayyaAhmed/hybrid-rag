# 08 — Run the app in a container

Status: **implemented** (2026-11-04)

## Goal
Run the Python app (chat loop, `rag` CLI, Alembic) in Docker next to the `db` container, so the only things you need
on a new machine are Docker and an `.env` file. No local Python or uv required.

## What runs where
```
docker compose
├── db   (existing)  Postgres 18 + pgvector + pg_textsearch, port 5432, volume pgdata
└── app  (new)       Python 3.12 + the rag package; talks to db at host "db", to Voyage/Gemini over the internet
```
Local development keeps working as before (`uv run …` against `localhost:5432`). The container is an extra way to run it.

## Image: `Dockerfile` (project root)
```dockerfile
FROM python:3.12-slim
# same uv version as local, pinned
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# 1) dependencies only: this layer is cached until pyproject.toml / uv.lock change
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

# 2) the project itself
COPY src/ src/
COPY app.py alembic.ini ./
COPY db/migrations/ db/migrations/
COPY data/ data/
COPY eval/ eval/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

RUN useradd --create-home app && chown -R app /app
# don't run as root
USER app
CMD ["python", "app.py"]
```
- **`uv sync --frozen`** installs exactly what `uv.lock` says, so the container gets the same versions as your Mac.
- **Two-step install**: a code change only rebuilds step 2. Dependencies are reinstalled only when the lockfile changes.
- **`.venv/bin` on `PATH`** puts `python`, `rag` and `alembic` on the path without `uv run`.
- **`--no-dev`**: pytest isn't needed at runtime.

## `.dockerignore`
```
.env
.venv/
.git/
__pycache__/
.pytest_cache/
eval/results*.json
```
`.env` must **never** be baked into the image (it has API keys). It is passed at runtime instead.

## docker-compose: `app` service
```yaml
  app:
    build: .
    image: hybrid-rag-app
    profiles: ["app"]                 # `make up` / `docker compose up` still start only db
    env_file: .env                    # API keys + knobs, read at runtime
    environment:
      DATABASE_URL: postgresql://rag:rag@db:5432/rag   # "db" = the db service name; overrides localhost from .env
    depends_on:
      db: { condition: service_healthy }
    volumes:
      - ./eval:/app/eval              # eval results written in the container end up in the project folder
    stdin_open: true                  # chat loop reads from the keyboard
    tty: true
```
- Inside the container, `localhost` is the container itself, so the app reaches Postgres by service name `db`.
  Environment variables beat `.env` values in pydantic-settings, so the `.env` file can keep `localhost` for local use.
- `profiles: ["app"]`: the app is interactive, so it is started with `docker compose run`, not `up`.
  `run` starts `db` first because of `depends_on`.

## Usage (Makefile targets, spec 07)
| Target | Runs |
|---|---|
| `app-build` | `docker compose build app` |
| `app-chat` | `docker compose run --rm app` (chat loop) |
| `app-cli ARGS="…"` | `docker compose run --rm app rag $(ARGS)`, e.g. `make app-cli ARGS='search "SKU 00123" --explain'` |
| `app-migrate` | `docker compose run --rm app alembic upgrade head` |

## Trade-offs
- `data/` is copied into the image, so after `make data` you need `make app-build` before ingesting from the container.
  (Mounting it would avoid that, but the image would no longer work on its own.)
- `pyproject.toml` has `no-build = true` (because of the Intel Mac). In the Linux image this means every dependency
  must have a Linux wheel for the locked version. If the build fails on that, the fix is in `[tool.uv]`, not the Dockerfile.

## Acceptance
- [x] `make app-build` succeeds; `.env` is not in the image (`docker compose run --rm app ls -a` shows no `.env`).
- [x] `make app-cli ARGS=stats` shows 27 chunks / 15 products (container reaches `db`).
- [x] `make app-cli ARGS='search "SKU 00123" --explain'` works (Voyage reachable, keys passed).
- [ ] `make app-chat` answers a question and `exit` quits. (Loop + exit verified; answer not yet: Gemini returned 503 and then hit the daily free-tier quota on 2026-11-04.)
- [x] `make app-migrate` → "already at head" (Alembic works in the container).
- [x] Container runs as user `app`, not root.
