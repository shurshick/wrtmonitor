# WrtMonitor

`WrtMonitor` - self-hosted сервер, Web UI, Android-приложение и OpenWrt-агент для мониторинга и удалённого управления роутерами OpenWrt.

## Текущая версия

Текущая тестовая версия: `0.43.0`. Публичного стабильного релиза пока нет; тестовые базы можно пересоздавать между несовместимыми версиями.

Главное в `0.43.0`:

- политика клиента показывает отдельные состояния отправки, подтверждения и ошибки вместо преждевременного успеха;
- блокировка, расписание, профиль, DNS-ограничения и постоянный адрес проверяются после применения на роутере;
- индивидуальные лимиты приёма и передачи работают через `tc flower + police` по MAC;
- Web UI и Android скрывают лимиты, если OpenWrt не подтвердил необходимые модули;
- installer и автообновление агента ставят `tc-full` и kernel-модули автоматически.

Полная история изменений: [CHANGELOG.md](CHANGELOG.md).

## Что уже есть

- сервер `FastAPI + PostgreSQL + Alembic`;
- текущая модель доступа: `single-owner`, без ролей и мультипользовательского режима;
- Web UI со светлой и тёмной dashboard-темой;
- Android-клиент;
- OpenWrt-агент для регистрации, telemetry, очереди команд, Web SSH, diagnostics и автообновления;
- установка через Docker Compose, VPS, домашний Linux-сервер, NAS с Docker и TrueNAS Custom App;
- управление Wi-Fi, сетью, DHCP, системными сервисами, диагностикой и жизненным циклом агента;
- release artifacts для сервера, агента и Android.

## Интерфейс

### Обзор роутера

[![Обзор состояния роутера в WrtMonitor](docs/images/web-overview.png)](docs/images/web-overview.png)

### Клиенты домашней сети

[![Список клиентов домашней сети в WrtMonitor](docs/images/web-home-network.png)](docs/images/web-home-network.png)

### Интернет и интерфейсы

[![Состояние интернет-подключения и сетевых интерфейсов в WrtMonitor](docs/images/web-internet.png)](docs/images/web-internet.png)

### Web-терминал OpenWrt

[![Интерактивная PTY-сессия OpenWrt через Web SSH в WrtMonitor](docs/images/web-terminal.png)](docs/images/web-terminal.png)

## Быстрый старт

1. Разверните сервер и PostgreSQL через Docker Compose или TrueNAS.
2. Откройте `/setup`.
3. Создайте первого администратора.
4. Проверьте `/ready`.
5. Откройте **Аккаунт -> Подключить мобильное приложение**, создайте QR и отсканируйте его в Android. Ручной ввод адреса и вход по паролю остаются доступны.
6. Установите OpenWrt-агент.

Для reverse proxy указывайте внешний HTTPS-адрес:

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

Базовый YAML лежит в `deploy/truenas/wrtmonitor-truenas.yaml`.

В релизе он публикуется как:

```text
wrtmonitor-truenas-v<VERSION>.yaml
```

Контейнер использует:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

`latest` скачивается при redeploy через **Edit -> Save**, но не обновляет уже запущенный контейнер сам по себе.

## OpenWrt-агент

OpenWrt-агент можно установить:

- с GitHub Release;
- прямо с уже развернутого сервера `https://monitor.example.ru/downloads/openwrt/`.

Сервер раздаёт:

- `wrtmonitor-agent`
- `wrtmonitor.init`
- `install-openwrt.sh`
- `agent-version.txt`
- `openwrt-agent-files.txt`
- `SHA256SUMS.txt`
- `SHA256SUMS.sig`
- `lib/*.sh`

Подробности:

- [OpenWrt agent](docs/openwrt-agent.md)
- [Развёртывание сервера](docs/server-deployment.md)
- [Эксплуатация и восстановление](docs/server-operations.md)
- [События, уведомления и автоматизация](docs/events-and-automation.md)
- [Router management core](docs/router-management-core.md)

## Документация

- [OpenWrt agent](docs/openwrt-agent.md)
- [Развёртывание сервера](docs/server-deployment.md)
- [API](docs/api.md)
- [Архитектура](docs/architecture.md)
- [Жизненный цикл команд](docs/command-lifecycle.md)
- [Проверка на реальном роутере](docs/real-router-testing.md)
- [Android](docs/android.md)
- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)

История релизов теперь ведётся в одном месте: [CHANGELOG.md](CHANGELOG.md). Отдельные старые промежуточные release notes больше не поддерживаются.

