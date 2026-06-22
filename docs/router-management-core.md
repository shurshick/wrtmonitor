# Router Management Core

Документ фиксирует фундамент `v0.1.1-rc8-router-management-core`.

## Что добавлено

- `agent capabilities`
- command metadata и risk levels
- backend validation payload
- diagnostics commands
- backup `wireless` перед Wi-Fi-изменениями
- нормализованные `wifi` и `network` summary
- capability-aware Web UI и Android

## Capabilities

Agent публикует JSON с:

- `agent.version`
- `agent.platform`
- `agent.capabilities_version`
- набором булевых capabilities

Если capabilities отсутствуют, интерфейсы переходят в read-only fallback.

## Risk levels

- `level_1_readonly`
- `level_2_safe_action`
- `level_3_reversible_config`

`level_3_reversible_config` требует подтверждения и должен сопровождаться понятным UI.

## Diagnostics

Поддерживаются:

- `check-server`
- `check-dns`
- `check-route`
- `check-wifi`
- `check-dependencies`
- `diagnostics --json`

Backend использует `diagnostics.run` как обычную queued-команду.

## Wi-Fi backup before change

Перед командами Wi-Fi agent создает:

- `.bak` файл конфигурации
- `.meta` файл с metadata

Restore в `rc8` специально не реализован как отдельная команда, но backup/list уже есть.

## Secret masking

В `rc8` секреты не должны попадать в:

- command history
- command result
- telemetry
- agent status
- support bundle
- Web UI
- Android UI

## Что специально не реализовано в rc8

- LuCI app
- DHCP write management
- firewall write management
- VPN management
- WAN/LAN write configuration
- sysupgrade
- factory reset
