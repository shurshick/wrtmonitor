# Аудит границ OpenWrt-агента 0.48.0

## Результат

OpenWrt runtime разделён по предметным подсистемам без изменения внешнего command API, UCI identity, update URL и протокола terminal broker.

## Устранённые монолиты

- `update.sh` оставлен тонким фасадом над version, crypto, storage и validation;
- `command_network.sh` оставлен фасадом над core, topology, services и policy;
- `telemetry_network.sh` оставлен совместимым фасадом над пятью источниками наблюдений;
- `transactions.sh` разделён на specification, state и recovery;
- `verification.sh` разделён на modes, runtime и client verifiers;
- `command_runtime.sh` разделён на result, DNS и Wi-Fi helpers;
- PTY transport отделён от terminal command handler.

## Ограничения роста

- любой файл `openwrt-agent/lib/*.sh` не может превышать 300 строк;
- entrypoint загружает библиотеки только в явном порядке;
- manifest и checksum обязаны содержать каждый runtime-файл;
- неизвестная post-condition проверка считается ошибкой;
- shell syntax, update compatibility и OpenWrt harness запускаются в CI.

## Совместимость

Серверная БД, Android DTO, Web URL, capability schema и command names не менялись. Обновление агента использует существующий подписанный manifest и атомарное поколение runtime.
