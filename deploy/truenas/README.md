# Установка на TrueNAS Custom App

Тестовая установка использует готовый Docker image:

```text
ghcr.io/shurshick/wrtmonitor:0.1.0-test.10
```

Если пакет GHCR приватный, сначала добавьте в TrueNAS Docker registry credentials для `ghcr.io`.

## Быстрый порядок

1. Скачайте `wrtmonitor-truenas-0.1.0-test.10.yaml` из релиза.
2. Откройте YAML и замените тестовые значения на свои.
3. Создайте Custom App из YAML.
4. Запустите приложение.
5. Настройте Nginx Proxy Manager на `http://truenas-ip:8088`.
6. Откройте внешний HTTPS-адрес `/setup`.
7. Создайте первого администратора.
8. Проверьте `/health`.

## Что заменить в YAML для HTTPS через NPM

TrueNAS проверяет compose-файл до запуска. Поэтому тестовый YAML сделан самодостаточным и не требует `${POSTGRES_PASSWORD}` или других внешних переменных.

Перед вставкой в TrueNAS замените одинаковый пароль базы в двух местах:

```yaml
POSTGRES_PASSWORD: change-me-postgres-password
WRTMONITOR_DATABASE_URL: postgresql+psycopg://wrtmonitor:change-me-postgres-password@postgres:5432/wrtmonitor
```

Затем замените внешний адрес и JWT-секрет:

```yaml
WRTMONITOR_PUBLIC_SERVER_URL: https://monitor.example.ru
WRTMONITOR_JWT_SECRET: change-me-long-random-jwt-secret
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

## Временный локальный HTTP-тест

Для проверки без NPM можно временно заменить в YAML:

```yaml
WRTMONITOR_PUBLIC_SERVER_URL: http://truenas-ip:8088
WRTMONITOR_ALLOW_INSECURE_LOCAL: "true"
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

