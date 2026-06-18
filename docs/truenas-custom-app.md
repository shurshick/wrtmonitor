# TrueNAS Custom App

Для тестовой установки используйте готовый YAML:

- [`deploy/truenas/wrtmonitor-truenas.yaml`](../deploy/truenas/wrtmonitor-truenas.yaml)

Внутри два сервиса:

- `postgres`;
- `wrtmonitor`.

Минимальные переменные для TrueNAS:

```text
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_HTTP_PORT=8088
WRTMONITOR_JWT_SECRET=long-random-secret
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
POSTGRES_PASSWORD=password
```

После первого запуска откройте `/setup` и создайте администратора. Если TrueNAS публикует приложение через reverse proxy, в `WRTMONITOR_PUBLIC_SERVER_URL` указывайте внешний адрес, доступный Android-приложению и OpenWrt-роутерам.
