# Проверка на реальном OpenWrt-роутере

Перед изменением SSID, отключением Wi-Fi или reboot убедитесь, что есть SSH-доступ по кабелю и сохранен backup: `sysupgrade -b /tmp/openwrt-backup.tar.gz`.

## Чек-лист

| Тест | Ожидаемо | Факт | PASS/FAIL | Комментарий |
|---|---|---|---|---|
| `capabilities --json` | JSON валиден и содержит capabilities | | | |
| Capability detection | отсутствующие пакеты/радио имеют `false` и понятную причину | | | |
| Telemetry | latest telemetry содержит `agent`, `wifi`, `network` | | | |
| Diagnostics | `diagnostics --json` возвращает structured result | | | |
| Wi-Fi on/off | меняется только выбранный radio | | | |
| SSID | меняется только выбранный iface | | | |
| Wi-Fi password | пароль меняется без утечки в logs/history | | | |
| Backup | перед Wi-Fi-командой появляется backup `wireless-*` | | | |
| Network | interfaces обновляются через `network.interfaces` | | | |
| Reboot | result приходит до reboot | | | |
| WAN DHCP/static/PPPoE | настройки применяются, агент восстанавливает связь | | | |
| LAN | адрес меняется только после backup конфигурации | | | |
| DHCP/DNS | pool, static lease и DNS применяются без потери конфигурации | | | |
| Firewall | port forward создаётся и удаляется | | | |
| Clients | блокировка и разблокировка MAC работает | | | |
| Guest Wi-Fi | сеть создаётся с изоляцией | | | |
| System | hostname, timezone, NTP и restart service работают | | | |
| Agent interval | принимаются значения от 5 секунд | | | |
| Agent update | переход `0.1.1-rc9 -> 0.3.x` успешен | | | |
| Agent rollback | предыдущая версия восстанавливается | | | |
| Command lifecycle | видны `sent`, `running` и terminal status | | | |

## Порядок

1. Зафиксируйте модель, версию OpenWrt, target/platform, число radio и исходный SSID.
2. Установите agent и выполните:

   ```sh
   wrtmonitor-agent capabilities --json
   wrtmonitor-agent diagnostics --json
   ```

3. Проверьте latest telemetry в Web UI или API.
4. Сначала сделайте безопасную смену SSID, затем Wi-Fi on/off и только потом reboot.
5. После каждой Wi-Fi-команды проверьте:

   ```sh
   wrtmonitor-agent list-config-backups
   ```

## Recovery

Через SSH можно вернуть wireless:

```sh
uci show wireless
uci set wireless.default_radio0.ssid='старый SSID'
uci commit wireless
wifi reload
wifi
/etc/init.d/network restart
```

Для удаления agent:

```sh
/etc/init.d/wrtmonitor stop
/etc/init.d/wrtmonitor disable
rm -f /usr/bin/wrtmonitor-agent /etc/init.d/wrtmonitor /etc/config/wrtmonitor
```
