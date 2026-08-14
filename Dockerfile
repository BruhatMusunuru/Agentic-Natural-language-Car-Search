FROM python:3.12-slim

# uv gives us fast, reproducible installs from the lockfile.
COPY --from=ghcr.io/astral-sh/uv:0.9.1 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# App code and static assets. The listings data is expected to be mounted
# as a volume at /app/data (see README) rather than baked into the image.
COPY rag_assistant ./rag_assistant
COPY static ./static
COPY main.py ./

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    LISTINGS_DATA_DIR=/app/data/data

# Run as a non-root user rather than the container default root.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "rag_assistant.server:app", "--host", "0.0.0.0", "--port", "8000"]
