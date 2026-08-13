# SentinelX API — production container (Cloud Run compatible).
#
# Build context is the REPOSITORY ROOT, not backend/, because the image needs
# migrations/ alongside backend/:
#   docker build -f backend/Dockerfile -t sentinelx-api .

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /install

# Dependencies are installed into a throwaway prefix so the final image carries
# no pip cache or build metadata. requirements.txt is fully pinned, so this is
# deterministic for a given index state.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --prefix=/install/deps -r requirements.txt


FROM python:3.12-slim AS runtime

# PYTHONDONTWRITEBYTECODE keeps the filesystem clean for a read-only rootfs;
# PYTHONUNBUFFERED makes the JSON log lines reach Cloud Logging immediately
# rather than sitting in a stdio buffer until the instance is reclaimed.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080

# Non-root: Cloud Run does not require it, but a container escape should not
# begin as uid 0.
RUN useradd --system --create-home --uid 10001 sentinelx

COPY --from=builder /install/deps /usr/local

WORKDIR /app
COPY --chown=sentinelx:sentinelx backend/app ./app
COPY --chown=sentinelx:sentinelx migrations ./migrations

USER sentinelx

EXPOSE 8080

# Cloud Run injects $PORT and may change it — never hard-code 8080 in the CMD.
#
# Single uvicorn worker on purpose: the SlowAPI rate limiter keeps its counters
# in process memory, so multiple workers (or instances) would each enforce
# their own independent limit. Scale with max-instances=1 plus this one worker
# until a shared limiter backend exists.
#
# Uvicorn drains in-flight requests on SIGTERM, which is what Cloud Run sends
# before reclaiming an idle instance.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 --no-server-header
