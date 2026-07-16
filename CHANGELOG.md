# Changelog

## v0.3.0-rc3

- Добавлено безвозвратное удаление роутера со всей telemetry, командами и связанными audit-записями.
- Удаление доступно для любого состояния в Web UI, Android и REST API.
- Раздел «Система» перестроен в понятную панель ресурсов, служб и настроек.
- Интернет, домашняя сеть и Wi-Fi разделены на состояние, основные действия и раскрываемые расширенные параметры.
- Сырые размеры переведены в КБ/МБ/ГБ, статусы и предупреждения получили понятные русские названия.
- Все управляющие кнопки приведены к компактному размеру; проверена адаптивность на desktop и mobile.

## v0.3.0-rc2

- Раздел «Обслуживание» разделён на статус, обновление, обмен данными и диагностику.
- Добавлено явное предупреждение об устаревшей версии агента.
- Журнал операций отделён от технических данных.
- Capabilities и raw telemetry перенесены в единый сворачиваемый блок.
- Rollback скрывается, когда резервная версия отсутствует.

## v0.3.0-rc1

- Добавлено управление WAN, LAN, DHCP и DNS.
- Добавлены проброс портов и блокировка доступа клиентов по MAC.
- Добавлена изолированная гостевая Wi-Fi сеть.
- Добавлены timezone и NTP.
- Новые команды доступны в Web UI и Android только по capabilities обновлённого агента.
- Для изменяемых UCI-конфигураций создаются резервные копии.
- Исправлен 500 в разделе «Обслуживание» при наличии истории команд.

## v0.2.0-rc2

- Web UI разделён на обзор, интернет, домашнюю сеть, Wi-Fi, систему и обслуживание.
- Главный экран роутера очищен от диагностики, команд, capabilities и raw telemetry.
- Добавлены новый список роутеров и компактная история команд.
- Android получил обзор состояния сети; управление агентом перенесено в раздел системы.
- Исправлено сохранение текущего раздела Web UI после отправки команды.
- Проверена адаптивность Web UI и обновлён Android `versionCode`.
- Release workflow публикует текущую RC-сборку с GitHub-меткой `Latest`.

## v0.2.0-rc1

- Введена telemetry schema v2 с нормализованными блоками системы, сервисов, Wi-Fi, сети и клиентов.
- Добавлены DHCP leases, neighbour table, conntrack, kernel, hostname, load 1/5/15 и состояние ключевых OpenWrt-сервисов.
- Добавлено управление Wi-Fi каналом и регионом.
- Добавлены переподключение интерфейса и перезапуск сети.
- Добавлены изменение hostname и перезапуск сервисов из allowlist.
- Добавлено управление статическими DHCP-выдачами.
- Web UI и Android синхронно расширены новыми экранами и командами.
- Конфигурационные команды защищены валидацией, capability checks, подтверждением, аудитом и backup.
- FastAPI startup переведён с deprecated `on_event` на lifespan.

## v0.1.1-rc9-agent-modularization-and-ui-fixes

- OpenWrt-агент переведён на модульную структуру `wrtmonitor-agent + lib/*.sh`.
- Installer и update pipeline обновлены под manifest `openwrt-agent-files.txt` и новую схему установки `/usr/lib/wrtmonitor`.
- Сервер, Android и GitHub Actions переведены на единый источник версии через `VERSION`, `VERSION_CODE` и `RELEASE_TAG`.
- Android переведён на `EncryptedSharedPreferences` для хранения сессии и access token.
- Из Android вычищены устаревшие formatter/helper хвосты и добита локализация рабочих экранов.
- Backend явно закреплён как `single-owner` модель доступа и отражает это через `/health/config`.
- Web UI получил compact capabilities UX и явное сообщение о необходимости reinstall `rc9`, если агент ещё не передал capabilities.
- Android получил такой же compact capabilities UX на экране устройства.
- Удаление из активного списка закреплено только для `disabled` устройств в Web UI и Android.

## v0.1.1-rc8-router-management-core

- Добавлены `agent capabilities`, нормализованные `agent/wifi/network` блоки telemetry и endpoint `GET /api/v1/devices/{device_id}/agent`.
- Backend получил `COMMAND_REGISTRY`, risk levels, masking секретов и валидацию payload для управляющих команд.
- OpenWrt agent получил diagnostics CLI, capability report и backup `wireless` перед изменением Wi-Fi.
- Web UI и Android стали capability-aware и показывают diagnostics и metadata команд.

## v0.1.1-rc7-agent-update-safety

- Добавлено безопасное автообновление OpenWrt agent через `SHA256SUMS.txt`.
- Добавлены backup, rollback, защита от downgrade и статус обновления в Web UI и Android.
- Удаление устройства из списка закреплено как soft-archive только для `disabled` устройств.

## v0.1.1-rc2-architecture-refactor

- Вынесены factory, route layer, Jinja2 templates и schemas backend.
- Добавлены Android API/data/domain layers и unit test сравнения версий.

## v0.1.1-rc1 - Real Router Validation and Control Polish

- Добавлены API истории команд, agent version и support bundle.
- Добавлен чек-лист валидации на реальном OpenWrt-роутере.
