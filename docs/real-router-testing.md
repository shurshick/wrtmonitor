# Проверка на реальном OpenWrt-роутере

Перед изменением SSID, отключением Wi-Fi или reboot убедитесь, что есть SSH-доступ по кабелю и сохранен backup: `sysupgrade -b /tmp/openwrt-backup.tar.gz`.

## Чек-лист

| Тест | Ожидаемо | Факт | PASS/FAIL | Комментарий |
|---|---|---|---|---|
| `capabilities --json` | JSON валиден и содержит capabilities | | | |
| Telemetry | latest telemetry содержит `agent`, `wifi`, `network` | | | |
| Diagnostics | `diagnostics --json` возвращает structured result | | | |
| Wi-Fi on/off | меняется только выбранный radio | | | |
| SSID | меняется только выбранный iface | | | |
| Wi-Fi password | пароль меняется без утечки в logs/history | | | |
| Backup | перед Wi-Fi-командой появляется backup `wireless-*` | | | |
| Network | interfaces обновляются через `network.interfaces` | | | |
| Reboot | result приходит до reboot | | | |

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
