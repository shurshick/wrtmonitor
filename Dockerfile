FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY openwrt-agent /app/openwrt-agent
COPY VERSION /app/VERSION

RUN mkdir -p /backups

EXPOSE 8080

CMD ["python", "-m", "backend.app.main"]
