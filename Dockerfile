# Multi-stage Dockerfile for notes-mcp

# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy README and source, then install project
COPY README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Copy virtual environment and source
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Create data directory and set permissions
RUN mkdir -p /app/data && chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/notes.db \
    HOST=0.0.0.0 \
    PORT=3000

USER appuser

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c 'import urllib.request, sys; sys.exit(0 if urllib.request.urlopen("http://127.0.0.1:3000/health").getcode() == 200 else 1)'

CMD ["notes-mcp"]
