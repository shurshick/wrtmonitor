# Установка на TrueNAS Custom App

YAML использует образ:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

При каждом redeploy параметр `pull_policy: always` заставляет TrueNAS скачать актуальный образ.

## Первичная установка

1. Скачайте из последнего релиза `wrtmonitor-truenas-v0.3.0-rc1.yaml`.
2. В YAML замените `WRTMONITOR_PUBLIC_SERVER_URL` на внешний HTTPS-адрес.
3. Замените `POSTGRES_PASSWORD` и такой же пароль в `WRTMONITOR_DATABASE_URL`.
4. Замените `WRTMONITOR_JWT_SECRET` на длинное случайное значение.
5. Создайте Custom App из YAML и запустите его.
6. В Nginx Proxy Manager направьте `https://monitor.example.ru` на `http://truenas-ip:8088`.
7. Откройте `https://monitor.example.ru/setup` и создайте первого администратора.

## Обновление latest

Тег `latest` не обновляет уже работающий контейнер автоматически. Выполните:

1. **Apps**
2. выберите `wrtmonitor`
3. **Edit**
4. **Save**

После redeploy проверьте `https://monitor.example.ru/health`.

PostgreSQL volume удалять не нужно: администратор, устройства и telemetry сохраняются.

Важно: текущий серверный режим `single-owner`. Один развёрнутый экземпляр WrtMonitor рассчитан на одного владельца и его парк роутеров.
