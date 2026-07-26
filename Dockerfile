FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY backend/requirements-runtime.txt /app/backend/requirements-runtime.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r /app/backend/requirements-runtime.txt

COPY backend /app/backend
COPY openwrt-agent /app/openwrt-agent
COPY VERSION /app/VERSION

RUN groupadd --gid 10001 wrtmonitor \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin wrtmonitor \
    && mkdir -p /backups \
    && chown -R wrtmonitor:wrtmonitor /app /backups

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=3).read()"]

CMD ["python", "-m", "backend.app.main"]
