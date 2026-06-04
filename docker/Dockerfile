# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.11.3-python3.14-trixie-slim AS builder

WORKDIR /build

ARG APP_VERSION=dev

COPY pyproject.toml uv.lock README.md ./

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY aperture ./aperture

RUN uv sync --frozen --no-dev --no-cache

FROM ghcr.io/astral-sh/uv:0.11.3-python3.14-trixie-slim

ARG APP_VERSION=dev

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/aperture /app/aperture

ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv" \
    PYTHONPATH="/app"

LABEL org.opencontainers.image.source="https://github.com/cdelgehier/aperture"
LABEL org.opencontainers.image.description="Aperture internal REST API for dynamic-select widgets"
LABEL org.opencontainers.image.version="$APP_VERSION"

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home app

USER app

EXPOSE 8000

ENTRYPOINT ["aperture"]
