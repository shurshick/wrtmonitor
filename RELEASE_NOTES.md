# v0.20.0-internet-network — интернет и сеть

Тестовый релиз завершает единый контур управления WAN, IPv6, DNS, сегментами и резервным подключением.

## Изменения

- WAN-редакторы Web UI и Android показывают только поля выбранного протокола DHCP, static или PPPoE;
- IPv4/IPv6, RA, DHCPv6, DNS, DoT и DoH управляются через проверяемые команды;
- физические порты передают реальные carrier, speed, duplex, MTU, traffic, errors и dropped counters;
- сегменты, bridge и VLAN 802.1Q используют реальные UCI-секции и read-after-write;
- Multi-WAN создаёт monitor-интерфейсы mwan3, health-check, приоритеты, failover и возврат на основной канал;
- Web UI и Android отображают фактическую конфигурацию и состояние Multi-WAN;
- post-condition расширен на IPv6, VLAN и Multi-WAN.

## Проверка

Автоматически проверены backend, Android, shell syntax, OpenWrt harness и контракты команд. Переключение физических WAN требует отдельного роутера с двумя подключёнными каналами.

## Артефакты

- `wrtmonitor-android-v0.20.0.apk`
- `wrtmonitor-openwrt-agent-v0.20.0.tar.gz`
- `wrtmonitor-truenas-v0.20.0.yaml`
