# Аудит WrtMonitor перед v0.45.2

Аудит выполнен по исходникам, тестам, release workflow, актуальным GitHub-релизам и результату восстановления физического OpenWrt x86.

## Закрыто в v0.45.2

- неатомарная замена entrypoint, init-скрипта и библиотек агента;
- возможность получить смешанный runtime после сбоя записи или read-only root;
- отсутствие проверки записи и свободного места до изменения установки;
- неполный backup, ошибочно считавшийся пригодным для rollback;
- потеря `device_id` при повторной установке с существующим token;
- бесконтрольное накопление старых поколений runtime;
- ложные локальные `skip` shell-тестов из-за неверного обнаружения Git Bash;
- жёстко зафиксированный Android `versionCode` в governance-тесте.

## Проверено

- backend и OpenWrt agent: 308 тестов пройдено, 20 platform/integration сценариев пропущено по условиям среды;
- отдельный agent static/harness прогон: 74 теста пройдено, 3 ожидаемых пропуска;
- контракт: 94 команды, command schema v1, telemetry schema v2;
- архитектурные границы backend/Android;
- Android unit tests, lint и debug APK;
- согласованность `VERSION`, `RELEASE_TAG`, версии агента и Android `VERSION_CODE`.

## Оставшийся долг

- `WrtMonitorApi.kt` остаётся слишком крупным транспортным фасадом;
- `NetworkControlScreen.kt`, `SystemControlScreen.kt` и `WifiControlScreen.kt` близки к установленному пределу размера;
- `app.css` требует разбиения по областям интерфейса;
- старые ветки RSA/Ed25519 trust и legacy API пока намеренно сохраняются для обновления установленных тестовых агентов;
- destructive hardware certification выполняется отдельным прогоном, а не в обычном CI.

Следующий разумный релиз: `v0.46.0 Architecture Cleanup` без расширения пользовательского функционала. Его задача — уменьшить крупные Android и Web-файлы, не меняя контракты и поведение.
