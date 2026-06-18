# Развёртывание серверной части

Этот документ описывает установку сервера `wrtmonitor` для тестовой версии `0.1.0-test.4`.

Сервер состоит из двух контейнеров:

- `wrtmonitor` — API и веб-страница первичной настройки;
- `postgres` — база данных PostgreSQL.

Сервер можно запускать на Docker-сервере, VPS, домашнем Linux-сервере, NAS с Docker или через TrueNAS Custom App.

## Что понадобится

- Docker или TrueNAS SCALE с Custom App.
- Доступный внешний HTTPS-адрес сервера для Android-приложения и OpenWrt-роутеров.
- Nginx Proxy Manager или другой reverse proxy для публикации HTTPS.
- Пароль для PostgreSQL.
- Длинный секрет для JWT.

Основной тестовый сценарий предполагает внешний доступ через Nginx Proxy Manager:

```text
https://monitor.example.ru
```

Внутренний HTTP-порт `8088` нужен только как upstream для NPM:

```text
http://truenas-ip:8088
```

## Важные переменные

```env
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_HTTP_PORT=8088
WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
POSTGRES_PASSWORD=replace-with-db-password
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
WRTMONITOR_ALLOW_INSECURE_LOCAL=false
```

Назначение:

- `WRTMONITOR_PUBLIC_SERVER_URL` — адрес, по которому сервер будет доступен Android-приложению и OpenWrt-агенту.
- `WRTMONITOR_HTTP_PORT` — порт на TrueNAS/Docker-хосте, по умолчанию `8088`.
- `WRTMONITOR_JWT_SECRET` — длинная случайная строка для токенов входа.
- `POSTGRES_PASSWORD` — пароль базы данных.
- `POSTGRES_DB` — имя базы, можно оставить `wrtmonitor`.
- `POSTGRES_USER` — пользователь базы, можно оставить `wrtmonitor`.
- `WRTMONITOR_ALLOW_INSECURE_LOCAL` — для NPM/HTTPS ставьте `false`. `true` нужен только для временного локального HTTP-теста без прокси.

## Схема с Nginx Proxy Manager

```text
Android / OpenWrt
        |
        | https://monitor.example.ru
        v
Nginx Proxy Manager
        |
        | http://truenas-ip:8088
        v
wrtmonitor container
        |
        v
PostgreSQL container
```

В NPM создайте Proxy Host:

- `Domain Names`: ваш домен, например `monitor.example.ru`;
- `Scheme`: `http`;
- `Forward Hostname / IP`: IP TrueNAS или имя сервиса, доступное NPM;
- `Forward Port`: `8088`;
- включите `Websockets Support` не обязательно, но можно оставить включённым;
- во вкладке SSL выпустите сертификат Let's Encrypt;
- включите `Force SSL`.

## Установка на TrueNAS Custom App

1. Откройте релиз:
   [v0.1.0-test.4](https://github.com/shurshick/wrtmonitor/releases/tag/v0.1.0-test.4)

2. Скачайте файл:

   ```text
   wrtmonitor-truenas-0.1.0-test.4.yaml
   ```

3. Если пакет GHCR приватный, добавьте в TrueNAS учётные данные для `ghcr.io`.

   Образ сервера:

   ```text
   ghcr.io/shurshick/wrtmonitor:0.1.0-test.4
   ```

4. Перед вставкой YAML в TrueNAS замените тестовые значения.

   TrueNAS проверяет compose-файл до запуска, поэтому файл не должен зависеть от незаданных `${...}` переменных.

   Пароль базы должен совпадать в двух местах:

   ```yaml
   POSTGRES_PASSWORD: change-me-postgres-password
   WRTMONITOR_DATABASE_URL: postgresql+psycopg://wrtmonitor:change-me-postgres-password@postgres:5432/wrtmonitor
   ```

   Также замените внешний HTTPS-адрес и JWT-секрет:

   ```yaml
   WRTMONITOR_PUBLIC_SERVER_URL: https://monitor.example.ru
   WRTMONITOR_JWT_SECRET: change-me-long-random-jwt-secret
   ```

5. В TrueNAS создайте Custom App из подготовленного YAML.

6. Запустите приложение.

7. Дождитесь, пока оба контейнера перейдут в состояние `running` или `healthy`.

8. В Nginx Proxy Manager настройте Proxy Host на внутренний адрес:

   ```text
   http://truenas-ip:8088
   ```

9. Откройте в браузере внешний адрес:

   ```text
   https://monitor.example.ru/setup
   ```

10. Создайте первого администратора.

   На этом шаге задаются:

   - имя администратора;
   - пароль администратора;
   - публичный адрес сервера.

11. Проверьте состояние сервера через внешний адрес:

    ```text
    https://monitor.example.ru/health
    ```

    Ожидаемый ответ:

    ```json
    {"status":"ok","database":"postgresql"}
    ```

## Временный локальный HTTP-тест без NPM

Используйте только для проверки в локальной сети:

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

## Установка на обычный Docker-сервер

1. Скачайте исходники или используйте `docker-compose.yml` из репозитория.

2. Создайте `.env`:

   ```env
   WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
   WRTMONITOR_DATABASE_URL=postgresql+psycopg://wrtmonitor:replace-with-db-password@postgres:5432/wrtmonitor
   WRTMONITOR_BIND_HOST=0.0.0.0
   WRTMONITOR_BIND_PORT=8080
   WRTMONITOR_JWT_SECRET=replace-with-long-random-secret
   WRTMONITOR_DEFAULT_LOCALE=ru
   WRTMONITOR_ALLOW_INSECURE_LOCAL=false
   POSTGRES_DB=wrtmonitor
   POSTGRES_USER=wrtmonitor
   POSTGRES_PASSWORD=replace-with-db-password
   ```

3. Запустите:

   ```sh
   docker compose up -d
   ```

4. Настройте Nginx Proxy Manager или другой reverse proxy на внутренний адрес:

   ```text
   http://server-ip:8088
   ```

5. Откройте внешний адрес `https://monitor.example.ru/setup`.

6. Создайте администратора и проверьте `/health`.

## После установки сервера

1. Установите Android APK из релиза.
2. При первом запуске Android-приложение спросит адрес сервера.
3. Затем приложение попросит логин и пароль администратора, созданного на `/setup`.
4. Установите OpenWrt agent из релиза.
5. Установщик агента также спросит адрес сервера и логин/пароль администратора.
6. После входа агент получит отдельный device token. Пароль администратора на роутере не сохраняется.

## Типичные проблемы

### `/setup` не открывается

Проверьте:

- контейнер `wrtmonitor` запущен;
- порт `8088` не занят другим приложением;
- в TrueNAS порт опубликован наружу;
- `WRTMONITOR_HTTP_PORT` совпадает с портом, который вы открываете в браузере.

### `/health` возвращает ошибку

Проверьте:

- контейнер `postgres` запущен;
- пароль `POSTGRES_PASSWORD` одинаковый для PostgreSQL и строки подключения;
- volume PostgreSQL не содержит старую базу с другим паролем.

### Сервер не принимает HTTP-адрес

Для локального теста должен быть включён:

```env
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
```

Для NPM/HTTPS используйте:

```env
WRTMONITOR_ALLOW_INSECURE_LOCAL=false
```

### Android или OpenWrt не подключаются

Проверьте, что `WRTMONITOR_PUBLIC_SERVER_URL` доступен именно с телефона и роутера, а не только с компьютера.

При NPM в Android и OpenWrt указывайте внешний HTTPS-адрес:

```text
https://monitor.example.ru
```

Не указывайте внутренний `http://truenas-ip:8088`, если телефон или роутер должны работать извне.

## Обновление тестовой версии

1. Остановите Custom App или Docker Compose.
2. Обновите image tag в YAML или `.env`.
3. Запустите приложение снова.
4. PostgreSQL volume удалять не нужно, если хотите сохранить администратора и устройства.

Для чистой переустановки удалите volume PostgreSQL. Это удалит администратора, устройства и всю телеметрию.

