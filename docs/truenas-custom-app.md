# TrueNAS Custom App

Полная инструкция: [развёртывание серверной части](server-deployment.md).

## Образ

В TrueNAS YAML используется стабильная ссылка на текущую тестовую сборку:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

В сервисе включён `pull_policy: always`. Это означает: при redeploy TrueNAS всегда проверяет и скачивает новый образ `latest`.

## Важное ограничение Docker

`latest` не является автообновлением работающего контейнера. Если новый релиз опубликован, старый контейнер продолжит работать до ручного redeploy.

## Обновление

1. Apps → `wrtmonitor` → **Edit**.
2. Проверьте image `ghcr.io/shurshick/wrtmonitor:latest`.
3. Нажмите **Save** и дождитесь redeploy.
4. Убедитесь, что App перешёл в `Running`.
5. Откройте `/health` через внешний HTTPS-адрес.

PostgreSQL volume не удаляйте. Его удаление стирает администратора, роутеры и историю telemetry.
