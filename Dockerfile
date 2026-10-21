FROM mcr.microsoft.com/playwright/python:v1.58.0-noble AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

FROM base AS production
COPY pyproject.toml README.md config.example.toml ./
COPY src ./src
RUN cp config.example.toml config.toml && \
    pip install . && \
    mkdir -p /data && \
    chown -R pwuser:pwuser /app /data
USER pwuser
CMD ["python", "-m", "schloss_monitor"]

FROM base AS development
COPY pyproject.toml README.md config.example.toml ./
COPY src ./src
RUN cp config.example.toml config.toml && \
    pip install ".[dev]" && \
    mkdir -p /data
# Docker Desktop bind mounts are writable for root but not reliably for pwuser.
# The development service intentionally runs as root; production remains non-root.
WORKDIR /workspace
ENV PYTHONPATH=/workspace/src
CMD ["sleep", "infinity"]
