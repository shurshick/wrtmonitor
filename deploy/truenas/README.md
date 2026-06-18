# Установка на TrueNAS Custom App

Тестовая установка использует готовый Docker image:

```text
ghcr.io/shurshick/wrtmonitor:0.1.0-test.3
```

Если пакет GHCR приватный, сначала добавьте в TrueNAS Docker registry credentials для `ghcr.io`.

## Быстрый порядок

1. Скачайте `wrtmonitor-truenas-0.1.0-test.3.yaml` из релиза.
2. Создайте Custom App из YAML.
3. Задайте переменные.
4. Запустите приложение.
5. Настройте Nginx Proxy Manager на `http://truenas-ip:8088`.
6. Откройте внешний HTTPS-адрес `/setup`.
7. Создайте первого администратора.
8. Проверьте `/health`.

## Переменные для HTTPS через NPM

```env
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_HTTP_PORT=8088
WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
POSTGRES_PASSWORD=replace-with-db-password
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
WRTMONITOR_ALLOW_INSECURE_LOCAL=false
```

В Nginx Proxy Manager:

```text
Scheme: http
Forward Hostname / IP: truenas-ip
Forward Port: 8088
SSL: Let's Encrypt
Force SSL: enabled
```

После запуска откройте:

```text
https://monitor.example.ru/setup
```

Проверка:

```text
https://monitor.example.ru/health
```

## Переменные для временного локального HTTP-теста

```env
WRTMONITOR_PUBLIC_SERVER_URL=http://truenas-ip:8088
WRTMONITOR_HTTP_PORT=8088
WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
POSTGRES_PASSWORD=replace-with-db-password
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
```

В этом режиме открывайте:

```text
http://truenas-ip:8088/setup
```

Проверка:

```text
http://truenas-ip:8088/health
```

Подробная инструкция: [`docs/server-deployment.md`](../../docs/server-deployment.md).
