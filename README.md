# WrtMonitor

`WrtMonitor` - self-hosted сервер, Web UI, Android-приложение и OpenWrt agent для мониторинга и безопасного управления роутерами OpenWrt.

## Что уже есть

- сервер `FastAPI + PostgreSQL + Alembic`;
- Web UI в темной dashboard-теме;
- Android-клиент;
- OpenWrt agent для регистрации, telemetry, очереди команд и автообновления;
- установка через Docker, Docker Compose и TrueNAS Custom App;
- управление Wi-Fi, базовой сетью, диагностикой и жизненным циклом агента;
- релизные артефакты для сервера, agent и Android.

## Текущий релиз

Текущая release candidate версия: `v0.1.1-rc8`.

Что добавлено в `rc8`:

- `agent capabilities` с safe fallback для старых агентов;
- централизованный `COMMAND_REGISTRY` и risk levels;
- безопасная backend-валидация payload для управляющих команд;
- diagnostics CLI и `diagnostics.run`;
- backup `/etc/config/wireless` перед изменением Wi-Fi;
- нормализованные блоки `agent`, `wifi`, `network` в latest telemetry;
- capability-aware Web UI и Android.

## Быстрый старт сервера

1. Поднимите сервер и PostgreSQL через Docker Compose или TrueNAS.
2. Откройте `/setup`.
3. Создайте первого администратора.
4. Проверьте `/health` и `/health/config`.
5. Подключите Android-приложение.
6. Установите OpenWrt agent.

Если сервер публикуется через Nginx Proxy Manager или другой reverse proxy, указывайте внешний HTTPS-адрес:

```env
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
WRTMONITOR_ALLOW_INSECURE_LOCAL=false
```

Для локального временного теста можно включить HTTP:

```env
WRTMONITOR_PUBLIC_SERVER_URL=http://192.168.1.10:8088
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
```

## TrueNAS

Базовый YAML лежит в [`deploy/truenas/wrtmonitor-truenas.yaml`](deploy/truenas/wrtmonitor-truenas.yaml).

В релизе он публикуется как:

```text
wrtmonitor-truenas-v0.1.1-rc8.yaml
```

Контейнер использует:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

`latest` скачивается при redeploy через **Edit -> Save**, но не обновляет уже запущенный контейнер сам по себе.

## OpenWrt agent

OpenWrt agent можно установить с GitHub Release или прямо с уже развернутого сервера:

```text
https://monitor.example.ru/downloads/openwrt/
```

Начиная с `rc8`, сервер раздает:

- `wrtmonitor-agent`
- `wrtmonitor.init`
- `install-openwrt.sh`
- `agent-version.txt`
- `SHA256SUMS.txt`

Agent умеет:

- `capabilities --json`
- `diagnostics --json`
- `update-status`
- `rollback`
- `list-config-backups`
- `support-bundle`

Подробно:

- [OpenWrt agent](docs/openwrt-agent.md)
- [Развертывание сервера](docs/server-deployment.md)
- [Архитектура](docs/architecture.md)
- [Router management core](docs/router-management-core.md)

## Документация

- [OpenWrt agent](docs/openwrt-agent.md)
- [API](docs/api.md)
- [Архитектура](docs/architecture.md)
- [Жизненный цикл команд](docs/command-lifecycle.md)
- [Проверка на реальном роутере](docs/real-router-testing.md)
- [Android](docs/android.md)
- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)
