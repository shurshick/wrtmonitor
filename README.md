# WrtMonitor

`WrtMonitor` - self-hosted сервер, Web UI, Android-приложение и OpenWrt-агент для мониторинга и удалённого управления роутерами OpenWrt.

## Текущая версия

Текущая стабильная версия: `v0.13.0`.

Главное в `0.13.0`:

- telemetry хранится в компактном ряду метрик 45 дней;
- Web UI и Android показывают графики за 2 часа, сутки, неделю и месяц;
- настройки Wi-Fi больше не дублируются в разных блоках;
- выбор 2.4/5 ГГц подставляет реальные параметры конкретного радиомодуля;
- журнал операций перелистывается без перезагрузки страницы.

В предыдущем релизе `0.12.0`:

- Web UI получил живой сетевой dashboard с графиком RX/TX и ресурсами роутера;
- Android получил тот же live monitor и ресурсную сводку;
- добавлена защищённая история telemetry.

В предыдущем релизе `0.11.0`:

- Web UI и Android сгруппированы по пользовательским задачам;
- сетевые правила и VPN вынесены в отдельные рабочие области;
- Android получил пять основных вкладок и иерархическую навигацию.

В предыдущих релизах:

- фактические LAN IPv4, маска, DHCP-пул, часовой пояс и NTP приходят с роутера;
- Web UI и Android больше не подставляют демонстрационные параметры;
- протоколы, маски, интерфейсы, Wi-Fi и системные параметры выбираются из списков;
- журнал операций ограничен, очищается по сроку и поддерживает постраничный просмотр;
- единые аккуратные кнопки в Web UI и Android;
- компактная высота, отступы и типографика без потери удобной области нажатия;
- вторичные и опасные действия визуально отделены от основных;
- кнопки обслуживания больше не растягиваются на всю ширину карточек;
- окончательное удаление роутера вместе с telemetry, командами и связанной историей;
- пользовательские панели системы, интернета, домашней сети и Wi-Fi;
- компактные действия и раскрываемые расширенные настройки вместо длинных технических форм;
- структурированное обслуживание: статус, обновление, обмен данными и диагностика;
- компактный обзор состояния роутера вместо технической свалки данных;
- Android-обзор сети и вынесенное в системный раздел обслуживание агента;
- управление WAN (DHCP, static IPv4, PPPoE), LAN, DHCP и DNS;
- проброс портов, блокировка клиентов и гостевой Wi-Fi;
- настройка timezone/NTP, строгая валидация, подтверждение, аудит и backup конфигурации;
- одинаковый capability-aware набор действий в Web UI и Android.

## Что уже есть

- сервер `FastAPI + PostgreSQL + Alembic`;
- текущая модель доступа: `single-owner`, без ролей и мультипользовательского режима;
- Web UI в тёмной dashboard-теме;
- Android-клиент;
- OpenWrt-агент для регистрации, telemetry, очереди команд, diagnostics и автообновления;
- установка через Docker Compose, VPS, домашний Linux-сервер, NAS с Docker и TrueNAS Custom App;
- управление Wi-Fi, сетью, DHCP, системными сервисами, диагностикой и жизненным циклом агента;
- release artifacts для сервера, агента и Android.

## Быстрый старт

1. Разверните сервер и PostgreSQL через Docker Compose или TrueNAS.
2. Откройте `/setup`.
3. Создайте первого администратора.
4. Проверьте `/health`.
5. Подключите Android-приложение.
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
wrtmonitor-truenas-v0.13.0.yaml
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
- `lib/*.sh`

Подробности:

- [OpenWrt agent](docs/openwrt-agent.md)
- [Развёртывание сервера](docs/server-deployment.md)
- [Эксплуатация и восстановление](docs/server-operations.md)
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
