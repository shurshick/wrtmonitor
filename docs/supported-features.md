# Поддерживаемые возможности

`WrtMonitor` до версии `1.0.0` остаётся тестовым проектом. Интерфейс показывает только функции, подтверждённые capability конкретного роутера. Отсутствующий Wi-Fi-модуль или пакет OpenWrt отображается как «не поддерживается», а не как пустая форма.

| Раздел | Web | Android | Проверка результата |
|---|:---:|:---:|---|
| Состояние роутера, графики и hardware health | да | да | свежесть telemetry и единая truth model |
| Интернет: DHCP, static, PPPoE, IPv4/IPv6 | да | да | read-after-write |
| DNS, DoT и DoH | да | да | конфигурация и runtime сервиса |
| LAN, DHCP, bridge, VLAN и физические порты | да | да | UCI и runtime интерфейсов |
| Wi-Fi 2.4/5/6 ГГц, SSID, guest и расписание | да | да | UCI, ubus и radio runtime |
| Клиенты, постоянный IP, блокировка и профили | да | да | клиентская политика и UCI |
| Firewall, NAT, зоны, маршруты | да | да | фактическая UCI section |
| WireGuard, OpenVPN и policy routing | да | да | профиль и runtime tunnel |
| Пакеты, backup, sysupgrade, службы и cron | да | да | package/service/config state |
| События, автоматизация и диагностика | да | да | command lifecycle |
| Безопасный отчёт и обратная связь | да | да | фильтрация секретов и PostgreSQL E2E |
| Web SSH с интерактивной PTY | да | нет | browser-server-agent E2E |
| Произвольный административный shell script | да | нет | осознанное исключение Android |

Полный контракт из 94 команд, риски, rollback и post-condition находятся в [command-matrix.md](command-matrix.md). Исключения поверхностей перечислены в `contracts/surface-exclusions.json` и проверяются CI.

Аппаратная применимость:

- Netis NX31: 90 команд поддержаны, 4 не применимы;
- OpenWrt x86 без Wi-Fi: 76 команд поддержаны, 18 не применимы;
- новые модели определяются по telemetry и не получают неподтверждённые органы управления.
