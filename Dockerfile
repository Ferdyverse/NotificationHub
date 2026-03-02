FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python - <<'PY'\nimport sys, urllib.request\ntry:\n    urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)\n    sys.exit(0)\nexcept Exception:\n    sys.exit(1)\nPY

ENTRYPOINT ["/app/docker/entrypoint.sh"]
