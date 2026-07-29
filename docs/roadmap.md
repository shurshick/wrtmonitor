# Roadmap WrtMonitor

Все версии до `1.0.0` тестовые. История завершённых релизов находится в [CHANGELOG.md](../CHANGELOG.md), а не дублируется здесь.

Статусы функций:

- `code complete` - реализация находится в исходниках;
- `CI verified` - пройдены автоматические тесты;
- `hardware verified` - приложен полный отчёт физического OpenWrt;
- `beta accepted` - функция выдержала публичное тестирование.

## v0.25.0 - Core Certification

- матрица 90 команд и поверхностей управления;
- обязательный fail-closed post-condition verifier;
- x86 harness для timeout, redelivery, idempotency и rollback;
- отдельный аппаратный certification gate;
- атомарный подписанный bundle агента, Docker-образ и GitHub Release;
- актуальные инструкции без старых зафиксированных ссылок.

Статус: выпущен.

## v0.26.0 - Architecture Split

- backend-модули network, Wi-Fi, firewall, VPN, system и maintenance;
- разделение agent commands и telemetry по подсистемам;
- типизированные command request/result schemas;
- Android Repository, ViewModel и DTO/domain без JSON в Compose;
- ограничение размера основных модулей и архитектурный тест.

Статус: выпущен.

## v0.27.0 - Operational Parity

- единая матрица пользовательских операций Web и Android;
- одинаковые названия, состояния, ошибки и подтверждения;
- динамические варианты выбора из capability/runtime API;
- Android emulator UI tests;
- проверка Back, сохранения экрана и восстановления сессии.

## После v0.27.0

Следующий этап определяется по результатам аппаратной сертификации и тестовой эксплуатации. Новые функции не добавляются поверх неподтверждённого core.
