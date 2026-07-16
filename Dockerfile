FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY openwrt-agent /app/openwrt-agent
COPY VERSION /app/VERSION

EXPOSE 8080

CMD ["python", "-m", "backend.app.main"]
