# TrueNAS Custom App

Короткая инструкция для TrueNAS SCALE Custom App.

Полная инструкция: [Развёртывание серверной части](server-deployment.md).

## Актуальная версия

```text
v0.1.0-test.11
```

## Файл YAML

Скачайте из релиза:

```text
wrtmonitor-truenas-v0.1.0-test.11.yaml
```

## Что заменить перед запуском

```yaml
WRTMONITOR_PUBLIC_SERVER_URL: https://monitor.example.ru
POSTGRES_PASSWORD: replace-with-db-password
WRTMONITOR_DATABASE_URL: postgresql+psycopg://wrtmonitor:replace-with-db-password@postgres:5432/wrtmonitor
WRTMONITOR_JWT_SECRET: replace-with-long-random-jwt-secret
```

Значения `change-me-*` оставлять нельзя. Сервер не стартует с дефолтными секретами.

## Порядок

1. Создайте Custom App из подготовленного YAML.
2. Запустите приложение.
3. Настройте Nginx Proxy Manager на `http://truenas-ip:8088`.
4. Откройте `https://monitor.example.ru/setup`.
5. Создайте первого администратора.
6. Проверьте `https://monitor.example.ru/health`.

## Обновление

PostgreSQL volume удалять не нужно. Обновите image tag/YAML до `0.1.0-test.11`, проверьте секреты и перезапустите приложение.
