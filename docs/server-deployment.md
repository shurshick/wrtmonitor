# Развёртывание серверной части

Документ актуален для `wrtmonitor v0.1.0-test.15`.

Сервер состоит из двух контейнеров:

- `wrtmonitor` — backend API, первичная настройка, Web UI;
- `postgres` — PostgreSQL база данных.

Сервер можно запускать на обычном Docker-сервере, VPS, домашнем Linux-сервере, NAS с Docker или через TrueNAS Custom App.

## Важное про безопасность

Начиная с `v0.1.0-test.11`, сервер не стартует с дефолтными секретами:

- `WRTMONITOR_JWT_SECRET` не должен быть пустым, коротким или `change-me-*`;
- пароль PostgreSQL в `WRTMONITOR_DATABASE_URL` не должен быть пустым или `change-me-*`;
- `POSTGRES_PASSWORD` и пароль внутри `WRTMONITOR_DATABASE_URL` должны совпадать.

Внешний рабочий адрес сервера должен быть HTTPS:

```text
https://monitor.example.ru
```

Внутренний HTTP-порт `8088` используется только как upstream для reverse proxy:

```text
http://truenas-ip:8088
```

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

Назначение:

- `WRTMONITOR_PUBLIC_SERVER_URL` — внешний адрес, доступный Android-приложению и OpenWrt-роутерам.
- `WRTMONITOR_HTTP_PORT` — порт на Docker/TrueNAS-хосте, по умолчанию `8088`.
- `WRTMONITOR_JWT_SECRET` — длинная случайная строка для токенов входа.
- `POSTGRES_PASSWORD` — пароль базы данных.
- `POSTGRES_DB` — имя базы, можно оставить `wrtmonitor`.
- `POSTGRES_USER` — пользователь базы, можно оставить `wrtmonitor`.
- `WRTMONITOR_ALLOW_INSECURE_LOCAL` — `true` только для временного локального HTTP-теста.
- `WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS` — `true` только для CI/dev. На сервере оставляйте `false`.
- `WRTMONITOR_ENABLE_API_DOCS` — включает `/docs`, `/redoc`, `/openapi.json`. На внешнем сервере оставляйте `false`.

## TrueNAS Custom App

1. Откройте релиз:
   [v0.1.0-test.15](https://github.com/shurshick/wrtmonitor/releases/tag/v0.1.0-test.15)

2. Скачайте файл:

   ```text
   wrtmonitor-truenas-v0.1.0-test.15.yaml
   ```

3. При необходимости скачайте и проверьте checksums:

   ```text
   SHA256SUMS.txt
   ```

4. В YAML замените внешний адрес:

   ```yaml
   WRTMONITOR_PUBLIC_SERVER_URL: https://monitor.example.ru
   ```

5. Замените пароль PostgreSQL в двух местах на один и тот же реальный пароль:

   ```yaml
   POSTGRES_PASSWORD: replace-with-db-password
   WRTMONITOR_DATABASE_URL: postgresql+psycopg://wrtmonitor:replace-with-db-password@postgres:5432/wrtmonitor
   ```

6. Замените JWT secret:

   ```yaml
   WRTMONITOR_JWT_SECRET: replace-with-long-random-jwt-secret
   ```

7. Создайте TrueNAS Custom App из подготовленного YAML.

8. Запустите приложение и дождитесь состояния `running` или `healthy`.

9. В Nginx Proxy Manager создайте Proxy Host:

   ```text
   Domain Names: monitor.example.ru
   Scheme: http
   Forward Hostname / IP: truenas-ip
   Forward Port: 8088
   SSL: Let's Encrypt
   Force SSL: enabled
   ```

10. Откройте:

    ```text
    https://monitor.example.ru/setup
    ```

11. Создайте первого администратора.

12. Проверьте:

    ```text
    https://monitor.example.ru/health
    ```

    Ожидаемый ответ:

    ```json
    {"status":"ok","database":"postgresql"}
    ```

## Обычный Docker Compose

1. Скачайте репозиторий или используйте `docker-compose.yml`.

2. Создайте `.env`:

   ```env
   WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
   WRTMONITOR_DATABASE_URL=postgresql+psycopg://wrtmonitor:replace-with-db-password@postgres:5432/wrtmonitor
   WRTMONITOR_BIND_HOST=0.0.0.0
   WRTMONITOR_BIND_PORT=8080
   WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
   WRTMONITOR_DEFAULT_LOCALE=ru
   WRTMONITOR_ALLOW_INSECURE_LOCAL=false
   WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS=false
   WRTMONITOR_ENABLE_API_DOCS=false
   POSTGRES_DB=wrtmonitor
   POSTGRES_USER=wrtmonitor
   POSTGRES_PASSWORD=replace-with-db-password
   ```

3. Запустите:

   ```sh
   docker compose up -d
   ```

4. Настройте reverse proxy на:

   ```text
   http://server-ip:8088
   ```

5. Откройте `https://monitor.example.ru/setup`.

## Временный локальный HTTP-тест

Только для локальной проверки без NPM:

```env
WRTMONITOR_PUBLIC_SERVER_URL=http://truenas-ip:8088
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
```

Открывайте:

```text
http://truenas-ip:8088/setup
```

## Обновление TrueNAS через latest

YAML использует `ghcr.io/shurshick/wrtmonitor:latest` и `pull_policy: always`.

После публикации нового релиза Docker не заменяет уже запущенный контейнер самостоятельно. В TrueNAS откройте **Apps → wrtmonitor → Edit → Save**. Это запускает redeploy и повторный pull образа. PostgreSQL volume не удаляйте.

Если версия не изменилась, остановите App, снова выполните **Edit → Save**, дождитесь статуса `Running` и проверьте `/health`.

## Обновление с v0.1.0-test.10

1. PostgreSQL volume удалять не нужно.
2. Проверьте, что пароль БД не начинается с `change-me`.
3. Проверьте, что `WRTMONITOR_JWT_SECRET` не дефолтный и длиннее 32 символов.
4. Обновите image на:

   ```text
   ghcr.io/shurshick/wrtmonitor:latest
   ```

5. Перезапустите сервер.
6. Обновите OpenWrt agent на роутере.
7. Обновите Android APK.

## После установки сервера

1. Установите Android APK из релиза.
2. В Android укажите внешний HTTPS-адрес сервера.
3. Войдите логином и паролем администратора.
4. Установите OpenWrt agent.
5. Проверьте `/devices` и экран устройства в Android.

## Типичные проблемы

### Сервер не стартует после обновления

Проверьте:

- `WRTMONITOR_JWT_SECRET` заменён на реальное значение;
- `POSTGRES_PASSWORD` заменён на реальное значение;
- пароль в `WRTMONITOR_DATABASE_URL` совпадает с `POSTGRES_PASSWORD`;
- `WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS=false` на сервере.

### `/setup` не открывается

Проверьте:

- контейнер `wrtmonitor` запущен;
- порт `8088` не занят другим приложением;
- reverse proxy направляет на правильный IP и порт.

### Android или OpenWrt не подключаются

Проверьте, что `WRTMONITOR_PUBLIC_SERVER_URL` доступен именно с телефона и роутера.

При NPM указывайте внешний HTTPS-адрес:

```text
https://monitor.example.ru
```

Не указывайте внутренний `http://truenas-ip:8088`, если устройство должно работать извне.

## Данные и миграции

Схема базы ведётся через Alembic. Новая пустая PostgreSQL база поднимается миграциями. Существующая база `v0.1.0-test.10` помечается как базовая без удаления данных.

PostgreSQL volume удалять нужно только для чистой переустановки. Это удалит администратора, устройства и telemetry.
