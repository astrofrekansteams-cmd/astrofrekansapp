# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# build-essential is needed for argon2-cffi wheels on some platforms; curl is
# used by the healthcheck and by the ephemeris download step.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

# The JPL kernel is public domain; bake it into the image so the container
# never needs network access at boot.
COPY scripts ./scripts
RUN python scripts/download_ephemeris.py --dest /app/data/ephemeris

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Run as a non-root user.
RUN useradd --create-home --uid 10001 astro \
    && chown -R astro:astro /app
USER astro

ENV EPHEMERIS_PATH=/app/data/ephemeris/de421.bsp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
