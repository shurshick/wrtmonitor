# Roadmap WrtMonitor

Цель проекта - максимально полное удалённое управление OpenWrt через Android и Web UI. Ориентир по удобству - мобильное приложение Keenetic, а фактический набор возможностей определяется UCI, ubus и capability report конкретного роутера.

## v0.3.0 - стабильная основа

- telemetry schema v2: система, hardware, WAN/LAN, Wi-Fi, клиенты и сервисы;
- capability report v5 с динамическим определением функций и причинами недоступности;
- управление WAN, LAN, DHCP, DNS, Wi-Fi, клиентами, firewall и системными сервисами;
- одинаковые capability-aware действия в Android и Web UI;
- lifecycle команд `queued -> sent -> running -> success/failed`, retry, expiry и аудит;
- безопасное обновление агента, rollback и config backup;
- PostgreSQL E2E, Chromium desktop/mobile smoke-test и Android build в CI;
- refresh token и автоматическое восстановление Android-сессии;
- Docker/TrueNAS deployment, GitHub Release и GHCR `latest`.

## v0.4.0 - безопасная конфигурация

Статус: реализовано.

- единый transaction layer для сетевых изменений;
- preflight-проверка payload, UCI-секций и конфликтов адресов;
- backup затрагиваемых конфигураций до команды;
- подтверждение восстановления связи после применения;
- автоматический rollback по timeout;
- diff текущей и предлагаемой конфигурации в Web UI и Android;
- E2E success/rollback для WAN, LAN, DHCP, DNS, Wi-Fi и firewall.

## v0.5.0 - клиенты и политики

Статус: реализовано.

- единый реестр клиентов с историей, именами и vendor lookup;
- блокировка, пауза интернета и расписания доступа;
- профили для групп устройств;
- приоритет клиентов и общий лимит канала через SQM;
- статистика трафика по клиентам;
- одинаковое управление политиками в Web UI и Android.

## v0.6.0 - расширенный Wi-Fi

- несколько SSID на каждом radio;
- guest network и client isolation;
- канал, ширина, мощность и режим radio;
- расписание Wi-Fi;
- 802.11r/mesh там, где это поддерживает сборка OpenWrt;
- signal, noise, bitrate, airtime и roaming клиентов.

## v0.7.0 - маршрутизация и периметр

- IPv6, RA и DHCPv6;
- несколько WAN, приоритет и failover;
- firewall zones, forwarding и расширенные правила;
- статические маршруты;
- DDNS;
- UPnP и список активных динамических пробросов.

## v0.8.0 - VPN и policy routing

- WireGuard server/client;
- импорт и экспорт peer-конфигураций;
- OpenVPN client;
- policy-based routing по клиентам, подсетям и назначениям;
- статусы туннелей, handshake и трафик;
- безопасный rollback сетевых изменений VPN.

## v0.9.0 - обслуживание роутера

- управление пакетами opkg;
- backup/restore конфигурации;
- sysupgrade с проверкой модели, checksum и свободного места;
- журналы, процессы, cron и сервисы;
- download диагностического bundle;
- recovery mode после неудачной команды.

## v0.10.0 - эксплуатация сервера

- управляемые refresh-сессии и их отзыв;
- смена пароля владельца;
- журнал аудита в интерфейсе;
- уведомления о недоступности, обновлениях и ошибках команд;
- backup/restore PostgreSQL с проверкой восстановления;
- production-signed Android build pipeline;
- итоговый security, upgrade и disaster-recovery прогон.

## После v0.10.0 - локальное подключение

- поиск OpenWrt в LAN из Android;
- защищённый setup endpoint агента;
- одноразовый PIN или физически подтверждаемое окно настройки;
- передача адреса сервера и device token без терминала.

Локальный поиск остаётся последним: автоматическое подключение имеет смысл только после стабилизации всех удалённых операций и восстановления после ошибок.
