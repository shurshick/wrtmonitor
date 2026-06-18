# TrueNAS Custom App

Для TrueNAS используйте Docker Compose/custom app с двумя сервисами:

- `postgres`;
- `wrtmonitor`.

Минимальные переменные:

```text
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_DATABASE_URL=postgresql+psycopg://wrtmonitor:password@postgres:5432/wrtmonitor
WRTMONITOR_JWT_SECRET=long-random-secret
POSTGRES_DB=wrtmonitor
POSTGRES_USER=wrtmonitor
POSTGRES_PASSWORD=password
```
