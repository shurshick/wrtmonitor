# Установка на TrueNAS Custom App

Актуальная тестовая версия: `v0.1.0-test.11`.

Docker image:

```text
ghcr.io/shurshick/wrtmonitor:0.1.0-test.11
```

## Быстрый порядок

1. Скачайте из релиза `wrtmonitor-truenas-v0.1.0-test.11.yaml`.
2. Замените в YAML внешний адрес сервера.
3. Замените `POSTGRES_PASSWORD`.
4. Замените пароль в `WRTMONITOR_DATABASE_URL` на тот же пароль.
5. Замените `WRTMONITOR_JWT_SECRET`.
6. Создайте TrueNAS Custom App из YAML.
7. Настройте Nginx Proxy Manager на `http://truenas-ip:8088`.
8. Откройте `https://monitor.example.ru/setup`.

## Что обязательно заменить

```yaml
POSTGRES_PASSWORD: replace-with-db-password
WRTMONITOR_DATABASE_URL: postgresql+psycopg://wrtmonitor:replace-with-db-password@postgres:5432/wrtmonitor
WRTMONITOR_PUBLIC_SERVER_URL: https://monitor.example.ru
WRTMONITOR_JWT_SECRET: replace-with-long-random-jwt-secret
```

Сервер `v0.1.0-test.11` не запустится с `change-me-*` секретами. Это нормально и сделано специально.

## Nginx Proxy Manager

```text
Scheme: http
Forward Hostname / IP: truenas-ip
Forward Port: 8088
SSL: Let's Encrypt
Force SSL: enabled
```

Проверка:

```text
https://monitor.example.ru/health
```

Подробная инструкция: [`docs/server-deployment.md`](../../docs/server-deployment.md).
