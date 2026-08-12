# WrtMonitor v0.43.0 - Client Policies

Тестовый релиз делает применение клиентских политик проверяемым и добавляет реальные индивидуальные лимиты скорости.

## Изменено

- Web UI, Android и API различают `applying`, `applied` и `error` по фактическому результату команды;
- успешной считается только политика, которую агент прочитал после записи и сопоставил с требуемым состоянием;
- блокировка, расписание, приоритет, DNS-ограничения и DHCP lease получили точные post-condition проверки;
- лимиты upload/download применяются к MAC клиента через `tc flower + police` на LAN bridge;
- лимиты автоматически восстанавливаются после перезапуска агента;
- capability `clients.shaping` включается только при наличии `tc-full`, `kmod-sched-core`, `kmod-sched-flower` и `kmod-sched-act-police`;
- installer и updater автоматически устанавливают эти зависимости через `apk` или `opkg`;
- TrueNAS YAML снова использует `ghcr.io/shurshick/wrtmonitor:latest`.

## Проверки

- backend, OpenWrt agent и Android unit tests;
- hardware-проверка `tc flower + police` на Netis NX31 и OpenWrt x86;
- проверка независимых upload/download filters, чтения результата и очистки;
- Android compile и release metadata checks.

Android `versionCode`: `100`.
