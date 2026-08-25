# syntax=docker/dockerfile:1

# --- builder: resolve + install deps and build the venv with uv -----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- runtime: non-root, no build toolchain, no writable root FS -----------
FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/scripts /app/scripts

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

# storage.py/status_store.py derive their paths from the package location
# (parent.parent.parent of the installed src layout), which resolves under
# this WORKDIR to /app/data — not /data — so that's where the writable
# mount has to land.
VOLUME ["/app/data"]

# Intended to run with `read_only: true` at the compose/run level (see
# deploy/docker-compose.yml) — nothing in this image writes outside
# /app/data. Compose overrides this entrypoint for the api service to run
# `python -m traffictracker.api` instead, from the same image.
ENTRYPOINT ["python", "-m", "traffictracker.poller"]
