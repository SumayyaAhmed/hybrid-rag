# App image: Python 3.12 + the rag package (chat loop, rag CLI, Alembic). See specs/08-app-container.md.
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
