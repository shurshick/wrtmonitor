# Router Management Core

Документ фиксирует фундамент ветки `v0.2.0` (актуальная сборка `rc2`).

## Что закреплено

- `agent capabilities`
- command metadata и risk levels
- backend validation payload
- diagnostics commands
- backup `wireless` перед Wi-Fi-изменениями
- telemetry schema v2 и нормализованные `system`, `services`, `clients`, `wifi`, `network` summary
- compact capabilities UX в Web UI и Android
- модульная структура OpenWrt-агента

## OpenWrt-агент

Новая структура агента:

```text
wrtmonitor-agent
lib/common.sh
lib/status.sh
lib/update.sh
lib/telemetry.sh
lib/capabilities.sh
lib/diagnostics.sh
lib/commands.sh
lib/api.sh
```

`wrtmonitor-agent` теперь отвечает только за:

- `AGENT_VERSION`
- `CONFIG`
- определение `LIB_DIR`
- загрузку модулей в фиксированном порядке
- вызов `main "$@"`

## Capabilities

Агент публикует JSON с:

- `agent.version`
- `agent.platform`
- `agent.capabilities_version`
- набором булевых capabilities

Интерфейсы по умолчанию показывают краткий summary capabilities, а полный список раскрывается по запросу.

Если capabilities отсутствуют, управление скрывается до обновления или переустановки агента.

## Update/install pipeline

Для новой структуры используется manifest:

```text
openwrt-agent-files.txt
```

Installer и updater:

- скачивают manifest;
- скачивают все перечисленные файлы;
- проверяют `SHA256SUMS.txt`;
- выполняют `sh -n` для entrypoint, installer, init и `lib/*.sh`;
- устанавливают `/usr/bin/wrtmonitor-agent`, `/etc/init.d/wrtmonitor`, `/usr/lib/wrtmonitor/*.sh`.

Обычный переход с `rc9` выполняется встроенным обновлением агента. Clean reinstall остаётся аварийным сценарием.

## Risk levels

- `level_1_readonly`
- `level_2_safe_action`
- `level_3_reversible_config`
- `level_4_disruptive`

`level_3_reversible_config` требует подтверждения и должен сопровождаться понятным UI.

`level_4_disruptive` используется для действий, которые временно обрывают связь с сервером, например полного перезапуска сети.

## Diagnostics

Поддерживаются:

- `check-server`
- `check-dns`
- `check-route`
- `check-wifi`
- `check-dependencies`
- `diagnostics --json`

Backend использует `diagnostics.run` как обычную queued-команду.

## Config backup before change

Перед изменением `wireless`, `system` или `dhcp` агент создаёт:

- `.bak` файл конфигурации;
- `.meta` файл с metadata.

Rollback/backup сохраняются в новой структуре и не зависят от старого layout `rc7/rc8`.

## Secret masking

Секреты не должны попадать в:

- command history
- command result
- telemetry
- agent status
- support bundle
- Web UI
- Android UI
