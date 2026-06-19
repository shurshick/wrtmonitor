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

Образ тестовой версии:

```text
ghcr.io/shurshick/wrtmonitor:0.1.0-test.10
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
- локальный поиск OpenWrt-роутера из Android и подключение агента к серверу;
- реальные Android API-клиенты вместо статических экранов;
- расширенная телеметрия OpenWrt через `ubus`;
- управление клиентами, Wi-Fi и сетевыми профилями;
- сборка установочных артефактов.

## Документация

- [Развёртывание серверной части](docs/server-deployment.md)
- [Архитектура](docs/architecture.md)
- [OpenWrt agent](docs/openwrt-agent.md)
- [Android-приложение](docs/android.md)
- [TrueNAS Custom App](docs/truenas-custom-app.md)
- [Безопасность](docs/security.md)
- [Roadmap](docs/roadmap.md)

