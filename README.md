# wrtmonitor

`wrtmonitor` — self-hosted система мониторинга и управления OpenWrt-роутерами.

Цель проекта — дать единый сервер и мобильное Android-приложение для просмотра состояния, настройки и безопасного управления OpenWrt-роутером по модели, близкой к мобильному приложению Keenetic, но для собственного сервера и своих устройств.

> Проект начат заново. Текущая ветка `main` — новая чистая основа, без старых релизов и совместимости с прежними прототипами.

## Компоненты

- Сервер: FastAPI + PostgreSQL.
- OpenWrt-клиент: shell-agent для регистрации, телеметрии, heartbeat и выполнения разрешённых команд.
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

При первой настройке задаются:

- внешний HTTPS-адрес сервера;
- администратор;
- пароль администратора.

Внешний адрес сервера должен быть доступен Android-приложению и OpenWrt-роутеру.

Для локальной лабораторной установки можно временно включить HTTP:

```env
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
WRTMONITOR_PUBLIC_SERVER_URL=http://server-ip:8088
```

## Тестовая установка на TrueNAS

Для TrueNAS Custom App подготовлен YAML:

- [`deploy/truenas/wrtmonitor-truenas.yaml`](deploy/truenas/wrtmonitor-truenas.yaml)

Образ тестовой версии:

```text
ghcr.io/shurshick/wrtmonitor:0.1.0-test.2
```

## Подключение клиентов

Android-приложение при первом запуске спрашивает адрес сервера и сохраняет его локально. Позже адрес можно изменить в настройках приложения.

OpenWrt agent можно установить с параметрами `--server`, `--token` и `--name`. Если параметры не переданы, установщик спросит адрес сервера, device token и имя роутера в консоли.

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
- чтение сетевых интерфейсов.

Все действия управления должны попадать в аудит-лог. Низкоуровневые UCI-команды намеренно не открыты как произвольный remote shell.

## Статус

Текущий каркас содержит:

- backend API;
- PostgreSQL-схему;
- очередь команд для OpenWrt agent;
- минимальный OpenWrt agent;
- минимальный Android Material 3 scaffold;
- Docker Compose;
- CI.
- TrueNAS YAML;
- Android debug APK в CI artifacts.

Следующие крупные блоки:

- полноценная первичная настройка в Android;
- реальные Android API-клиенты вместо статических экранов;
- расширенная телеметрия OpenWrt через `ubus`;
- управление клиентами, Wi-Fi и сетевыми профилями;
- сборка установочных артефактов.

## Документация

- [Архитектура](docs/architecture.md)
- [OpenWrt agent](docs/openwrt-agent.md)
- [Android-приложение](docs/android.md)
- [TrueNAS Custom App](docs/truenas-custom-app.md)
- [Безопасность](docs/security.md)
