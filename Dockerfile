# Multi-stage build for optimized image size
# Stage 1: Builder
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir --user -r /build/requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Update PATH to use local pip packages
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . /app

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import sys, urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2); sys.exit(0)" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
