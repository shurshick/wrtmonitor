# Установка на TrueNAS Custom App

Тестовая установка использует готовый Docker image:

```text
ghcr.io/shurshick/wrtmonitor:0.1.0-test.3
```

Если пакет GHCR приватный, сначала добавьте в TrueNAS Docker registry credentials для `ghcr.io`.

## Переменные

Минимально задайте:

```env
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_HTTP_PORT=8088
WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
POSTGRES_PASSWORD=replace-with-db-password
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
```

Для теста в локальной сети без HTTPS:

```env
WRTMONITOR_PUBLIC_SERVER_URL=http://truenas-ip:8088
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
```

После запуска откройте `/setup` и создайте администратора.
