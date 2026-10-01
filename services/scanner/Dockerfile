FROM python:3.12-slim

RUN pip install --no-cache-dir "uv>=0.8,<0.9"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY scanner ./scanner
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 scanner
USER scanner

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "scanner.main"]
