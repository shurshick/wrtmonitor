# v0.3.0-rc1

Первый релиз расширенного управления конфигурацией OpenWrt. Он добавляет реальные UCI-операции поверх уже работающей telemetry и очереди команд.

## Что изменилось

- WAN: DHCP, static IPv4 и PPPoE, DNS, gateway и MTU.
- LAN: адрес роутера и маска сети.
- DHCP: диапазон, срок аренды и статические выдачи.
- DNS: собственные upstream-серверы.
- Firewall: создание и удаление проброса портов.
- Клиенты: блокировка и восстановление доступа в интернет по MAC.
- Wi-Fi: гостевая сеть с изоляцией, SSID и WPA2-паролем.
- Система: timezone и NTP-серверы.
- Все новые конфигурационные действия проходят backend validation, capability check, подтверждение и аудит; агент создаёт backup затрагиваемых UCI-файлов.
- Web UI и Android получили соответствующие элементы управления.
- Исправлен `Internal Server Error` раздела «Обслуживание» при отображении времени команд из API.

## Обновление

Сервер: выполните redeploy образа `ghcr.io/shurshick/wrtmonitor:latest`. PostgreSQL volume сохраняется.

Android: установите `wrtmonitor-android-v0.3.0-rc1-debug.apk` поверх предыдущей версии. `versionCode` увеличен до `28`.

OpenWrt agent необходимо обновить до `0.3.0-rc1`: старые версии не объявляют и не выполняют новые команды.

## Артефакты

- `wrtmonitor-truenas-v0.3.0-rc1.yaml`
- `wrtmonitor-openwrt-agent-v0.3.0-rc1.tar.gz`
- `wrtmonitor-android-v0.3.0-rc1-debug.apk`
- `SHA256SUMS.txt`

Это тестовая RC-сборка, опубликованная как `Latest` для штатного обновления тестового контура.
