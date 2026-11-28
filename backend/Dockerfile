# Spec 11 FR-DP-01: backend image. Build context: backend/
FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Runtime dependencies only (no dev extras), read from pyproject.toml so there is one list.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" \
        > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# The source tree, templates included. .dockerignore keeps tests, caches and secrets out.
COPY app ./app

# Non-root user; /data is the storage root (a volume in compose, the container disk on Render).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data
USER appuser

ENV DB_PATH=/data/app.db \
    STORAGE_ROOT=/data \
    LOG_TO_FILE=false

EXPOSE 8000

# FR-DP-06: exactly one worker. FR-DP-25: Render's $PORT, else 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 25"]
