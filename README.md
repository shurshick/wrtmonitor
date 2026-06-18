# wrtmonitor

`wrtmonitor` — self-hosted система мониторинга и управления OpenWrt-роутерами.

Цель проекта: дать единый сервер и мобильное Android-приложение для просмотра состояния, настройки и безопасного управления OpenWrt-роутером по модели, близкой к мобильному приложению Keenetic, но для собственного сервера и своих устройств.

## Компоненты

- Сервер: FastAPI + PostgreSQL.
- OpenWrt-клиент: shell-agent для регистрации, telemetry, heartbeat и выполнения разрешенных команд.
- Android-приложение: Material 3 клиент для мониторинга и управления.
- Docker Compose: запуск на Docker-сервере, VPS, домашнем Linux-сервере, NAS с Docker.
- TrueNAS Custom App: отдельный сценарий развёртывания через Docker.

## Первый запуск

```sh
cp .env.example .env
docker compose up --build
```

После запуска откройте:

```text
http://server-ip:8088/setup
```

На первой настройке задаются:

- внешний HTTPS-адрес сервера;
- администратор;
- пароль администратора.

Внешний адрес сервера должен быть доступен Android-приложению и OpenWrt-роутеру.

## Архитектура управления

Android не подключается напрямую к роутеру. Все команды идут через сервер:

```text
Android -> wrtmonitor server -> OpenWrt agent -> OpenWrt
```

OpenWrt agent выполняет только команды из allowlist:

- перезагрузка роутера;
- чтение статуса Wi-Fi;
- включение/выключение Wi-Fi;
- изменение SSID;
- чтение сетевых интерфейсов;
- применение подготовленных UCI-настроек.

Опасные действия требуют отдельного подтверждения на сервере и аудит-лог.

## Статус

Проект начат заново. Текущий каркас содержит:

- backend API;
- PostgreSQL-схему;
- очередь команд для OpenWrt agent;
- минимальный OpenWrt agent;
- минимальный Android Material 3 scaffold;
- Docker Compose;
- CI.

## Документация

- [Архитектура](docs/architecture.md)
- [OpenWrt agent](docs/openwrt-agent.md)
- [Android-приложение](docs/android.md)
- [TrueNAS Custom App](docs/truenas-custom-app.md)
- [Безопасность](docs/security.md)
