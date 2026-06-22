# Развертывание серверной части

## Перед первым запуском обязательно замените секреты

Замените все `change-me-*` значения: `POSTGRES_PASSWORD`, пароль в `WRTMONITOR_DATABASE_URL` и `WRTMONITOR_JWT_SECRET`.

Для JWT secret используйте, например:

```sh
openssl rand -base64 32
```

`WRTMONITOR_PUBLIC_SERVER_URL` должен содержать внешний HTTPS URL сервера.

Документ актуален для `WrtMonitor v0.1.1-rc8`.

## Переменные

```env
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_HTTP_PORT=8088
WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
POSTGRES_PASSWORD=replace-with-db-password
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
WRTMONITOR_ALLOW_INSECURE_LOCAL=false
WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS=false
WRTMONITOR_ENABLE_API_DOCS=false
```

## TrueNAS Custom App

1. Откройте релиз:
   [v0.1.1-rc8-router-management-core](https://github.com/shurshick/wrtmonitor/releases/tag/v0.1.1-rc8-router-management-core)
2. Скачайте файл:

   ```text
   wrtmonitor-truenas-v0.1.1-rc8.yaml
   ```

3. При необходимости скачайте и проверьте:

   ```text
   SHA256SUMS.txt
   ```

4. В YAML замените `WRTMONITOR_PUBLIC_SERVER_URL`, `POSTGRES_PASSWORD`, `WRTMONITOR_DATABASE_URL`, `WRTMONITOR_JWT_SECRET`.
5. Создайте TrueNAS Custom App.
6. Настройте reverse proxy на `http://truenas-ip:8088`.
7. Откройте `https://monitor.example.ru/setup`.
8. Создайте первого администратора.
9. Проверьте `https://monitor.example.ru/health`.

## Обычный Docker Compose

1. Создайте `.env`.
2. Запустите:

   ```sh
   docker compose up -d
   ```

3. Настройте reverse proxy на `http://server-ip:8088`.
4. Откройте `https://monitor.example.ru/setup`.

## Обновление TrueNAS через latest

YAML использует `ghcr.io/shurshick/wrtmonitor:latest` и `pull_policy: always`.

После публикации новой версии выполните в TrueNAS:

1. **Apps -> wrtmonitor -> Edit**
2. **Save**

Это запускает redeploy и повторный pull образа. PostgreSQL volume удалять не нужно.
