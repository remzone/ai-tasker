# Stage 1: build the React frontend
FROM node:22-slim AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 gcc git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev
COPY --from=web-builder /web/dist ./static
ENV AGENT_KANBAN_STATIC_DIR=/app/static
EXPOSE 7331
# The server lifespan applies migrations before accepting requests.
CMD ["/app/.venv/bin/kanban", "serve", "--host", "0.0.0.0", "--port", "7331"]
