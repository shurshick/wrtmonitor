# wrtmonitor

`wrtmonitor` — self-hosted система мониторинга и управления OpenWrt-роутерами.

Цель проекта — дать единый сервер и мобильное Android-приложение для просмотра состояния, настройки и безопасного управления OpenWrt-роутером по модели, близкой к мобильному приложению Keenetic, но для собственного сервера и своих устройств.

> Проект начат заново. Текущая ветка `main` — новая чистая основа, без старых релизов и совместимости с прежними прототипами.

## Компоненты

- Сервер: FastAPI + PostgreSQL.
- OpenWrt-клиент: shell-agent для регистрации, telemetry и выполнения разрешённых команд.
- Android-приложение: Material 3 клиент для мониторинга роутеров.
- Docker Compose: запуск на Docker-сервере, VPS, домашнем Linux-сервере, NAS с Docker.
- TrueNAS Custom App: отдельный сценарий развёртывания через Docker.

## Развёртывание сервера

Подробная инструкция:

- [Развёртывание серверной части](docs/server-deployment.md)

Короткий порядок:

1. Запустите сервер и PostgreSQL через Docker Compose или TrueNAS Custom App.
2. Откройте `/setup`.
3. Создайте первого администратора.
4. Проверьте `/health`.
5. Подключите Android-приложение и OpenWrt agent.

При первой настройке задаются:

- публичный адрес сервера;
- имя администратора;
- пароль администратора.

Публичный адрес должен быть доступен Android-приложению и OpenWrt-роутеру.

Если сервер публикуется через Nginx Proxy Manager, в `WRTMONITOR_PUBLIC_SERVER_URL` указывайте внешний HTTPS-адрес:

```env
WRTMONITOR_ALLOW_INSECURE_LOCAL=false
WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.ru
```

Локальный HTTP используйте только для временной проверки без NPM:

```env
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
WRTMONITOR_PUBLIC_SERVER_URL=http://server-ip:8088
```

## Тестовая установка на TrueNAS

Для TrueNAS Custom App подготовлен YAML:

- [`deploy/truenas/wrtmonitor-truenas.yaml`](deploy/truenas/wrtmonitor-truenas.yaml)

В релизе файл называется:

```text
wrtmonitor-truenas-v0.1.0-test.17.yaml
```

Образ тестовой версии:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

## Подключение клиентов

Android-приложение при первом запуске спрашивает адрес сервера, затем логинится логином и паролем администратора, созданного на сервере при `/setup`, и сохраняет JWT access token. Позже адрес можно изменить в настройках приложения.

OpenWrt agent при установке тоже использует администратора: установщик спрашивает адрес сервера, логин/пароль администратора и имя роутера, затем получает отдельный device token через сервер и сохраняет только этот device token. Пароль администратора на роутере не сохраняется.

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

Текущая тестовая версия `v0.1.0-test.17` содержит:

- backend API;
- PostgreSQL и Alembic-миграции;
- очередь команд для OpenWrt agent;
- OpenWrt agent с telemetry через `ubus`, UCI wireless и multi-radio Wi-Fi snapshot;
- API последней телеметрии;
- retention последних 100 telemetry snapshots на устройство;
- Android-экран устройства с telemetry;
- защита от дефолтных JWT/DB секретов;
- Web UI `/devices` с авторизацией;
- Docker Compose;
- CI с backend E2E, agent smoke tests, `sh -n`, shellcheck, Docker и Android build;
- TrueNAS YAML;
- Android debug APK в релизах.
- adaptive icon для Android;
- стабильную debug-подпись и повышенный `versionCode` для обновления APK поверх установленной версии.
- CSRF-защиту Web UI, security headers и command lifecycle с истечением команд.

Следующие крупные блоки:

- полноценная первичная настройка в Android;
- управление клиентами, Wi-Fi и сетевыми профилями;
- более полный UX команд управления;
- signed Android APK;
- локальный поиск OpenWrt-роутера из Android и подключение агента к серверу.

## Документация

- [Развёртывание серверной части](docs/server-deployment.md)
- [Архитектура](docs/architecture.md)
- [Telemetry](docs/telemetry.md)
- [OpenWrt agent](docs/openwrt-agent.md)
- [Android-приложение](docs/android.md)
- [TrueNAS Custom App](docs/truenas-custom-app.md)
- [Безопасность](docs/security.md)
- [Безопасность Web UI](docs/security-web-ui.md)
- [Жизненный цикл команд](docs/command-lifecycle.md)
- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)

