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

Статус: выпущен.

## После v0.27.0

## v0.28.0 - Operations And Notifications

- уведомления и эксплуатационные метрики;
- плановая очистка данных;
- диагностический архив сервера;
- canary-выдержка перед `latest`;
- исправленный источник клиентского трафика `nlbwmon`.

Статус: выпущен в canary.

## v0.29.0 - Network Policy

SQM/QoS, клиентские DNS-политики, история Multi-WAN, шаблоны Firewall/VPN и каталог прошивок.

Статус: выпущен в canary.

## v0.30.0 - OpenWrt Modules

USB, накопители, сетевые службы, принтеры и модемы с capability-driven интерфейсом.

Статус: выпущен в canary.

## v0.31.1 - Hardware Certification

- полный прогон 91 команды на Netis NX31 и OpenWrt x86;
- доказательства idempotency, timeout, redelivery, post-condition и rollback;
- исправления mesh, VPN policy и PBR, найденные аппаратными тестами;
- совместимая со старым OpenSSL подпись обновлений агента;
- воспроизводимый certification runner и опубликованные обезличенные отчёты.

Статус: `hardware verified`, тестовый релиз.

## v0.31.2 - DNS Recovery

- безопасная установка компонентов DoH/DoT без потери системного DNS;
- восстановление конфигурации `dnsmasq` после отключения или ошибки установки;
- обязательная проверка реального DNS-разрешения после команды;
- повторный аппаратный прогон на Netis NX31 и OpenWrt x86.

Статус: проверен на аппаратных стендах, тестовый hotfix.

## v0.32.0 - Push And Reliability

- long-poll доставки команд с сохранением короткого polling для старых агентов;
- единый SSE-поток для Web UI и Android;
- независимые deadlines команд, telemetry и автообновления агента;
- reconnect с backoff и резервный периодический refresh интерфейсов;
- метрики long-poll, подписчиков и потерянных событий;
- нагрузочная проверка 100 одновременно ожидающих агентов.

Статус: тестовый релиз.
