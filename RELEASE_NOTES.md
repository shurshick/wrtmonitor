# WrtMonitor v0.48.0 - Agent Boundaries

Тестовый технический релиз завершает разделение OpenWrt-агента. Серверные API, PostgreSQL-схема, Web UI, Android-сценарии и TrueNAS YAML не менялись.

## Изменено

- update runtime разделён на проверку версии, криптографию, хранилище поколений и validation;
- сетевые команды разделены на core, topology, services и policy;
- DHCP, клиенты, интерфейсы, topology и DNS получили отдельные telemetry-модули;
- post-condition verifiers, transaction recovery и PTY transport больше не находятся в общих монолитах;
- command runtime разделён на результат, DNS и Wi-Fi helpers;
- результаты команд получили единый структурированный контракт.

## Проверено

- shell syntax и статические тесты установщика, обновления, telemetry, команд и терминала;
- OpenWrt test harness для post-condition и структурированных ошибок;
- архитектурные ограничения всех agent libraries;
- backend API, Web UI и command lifecycle;
- Android unit tests, lint, сборка APK и монотонный `versionCode`.

Сервер обновляется обычным redeploy образа `latest` после публикации. Агент получает `0.48.0` штатным автообновлением с проверкой подписанного manifest.
