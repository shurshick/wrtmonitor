# Установка на TrueNAS Custom App

YAML использует образ:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

При каждом redeploy параметр `pull_policy: always` заставляет TrueNAS скачать актуальный образ.

## Первичная установка

1. Скачайте из последнего релиза `wrtmonitor-truenas-v0.1.0-test.15.yaml`.
2. В YAML замените `WRTMONITOR_PUBLIC_SERVER_URL` на внешний HTTPS-адрес.
3. Замените `POSTGRES_PASSWORD` и такой же пароль в `WRTMONITOR_DATABASE_URL`.
4. Замените `WRTMONITOR_JWT_SECRET` на длинное случайное значение.
5. Создайте Custom App из YAML и запустите его.
6. В Nginx Proxy Manager направьте `https://monitor.example.ru` на `http://truenas-ip:8088`.
7. Откройте `https://monitor.example.ru/setup` и создайте первого администратора.

## Обновление latest

Тег `latest` не обновляет уже работающий контейнер автоматически. Выполните в TrueNAS:

1. Откройте **Apps** и выберите `wrtmonitor`.
2. Нажмите **Edit**.
3. Убедитесь, что image указан именно так:

   ```text
   ghcr.io/shurshick/wrtmonitor:latest
   ```

4. Сохраните изменения и дождитесь redeploy приложения.
5. В списке Apps дождитесь статуса `Running`.
6. Проверьте `https://monitor.example.ru/health`.

PostgreSQL volume удалять не нужно: администратор, устройства и telemetry сохранятся.

Если TrueNAS всё ещё показывает старую версию, остановите App, снова нажмите **Edit → Save** и запустите его. Это запускает повторный pull благодаря `pull_policy: always`.
