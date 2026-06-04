FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY aperture ./aperture
COPY docs/tutorials/docker-compose-demo/demo_plugins ./demo_plugins
COPY docs/tutorials/docker-compose-demo/settings.yaml ./settings.yaml

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

ENV PYTHONPATH=/app

CMD ["uv", "run", "aperture"]
