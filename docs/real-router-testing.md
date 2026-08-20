# Проверка на реальном OpenWrt-роутере

Автоматический CI не заменяет испытание реального OpenWrt. Релиз получает отметку `hardware verified` только после полного запуска `hardware_certify.py` и прохождения финального gate.

Установите зависимости в отдельное окружение:

```sh
python -m venv .venv-certification
.venv-certification/bin/pip install -r scripts/requirements-certification.txt
```

В PowerShell используйте `.venv-certification\Scripts\pip.exe`.

Перед запуском задайте адрес сервера и учётные данные только через переменные окружения. Они не записываются в отчёт:

```sh
export WRTMONITOR_SERVER_URL='https://monitor.example.ru'
export WRTMONITOR_ADMIN_USER='admin@example.ru'
export WRTMONITOR_ADMIN_PASSWORD='...'
export WRTMONITOR_ROUTER_PASSWORD='...'
export WRTMONITOR_AGENT_UPDATE_URL='http://192.168.1.10:8799'
```

Полный прогон:

```sh
python scripts/hardware_certify.py \
  --name netis-nx31 \
  --host 192.168.1.1 \
  --device-id DEVICE_UUID
```

Для проверки ещё не опубликованного кандидата добавьте `--deploy-worktree`.
Runner временно установит агент и библиотеки из текущего рабочего дерева, не
перезаписывая UCI-настройки подключения, а затем зафиксирует версию и источник
агента в отчёте:

```sh
python scripts/hardware_certify.py \
  --name netis-nx31 \
  --host 192.168.1.1 \
  --device-id DEVICE_UUID \
  --deploy-worktree
```

`WRTMONITOR_AGENT_UPDATE_URL` нужен для безопасной проверки update/rollback на локально собранном агенте. Каталог `openwrt-agent/` должен раздаваться с указанного URL.

Повторить отдельные команды и объединить результат с отчётом можно так:

```sh
python scripts/hardware_certify.py \
  --name netis-nx31 \
  --host 192.168.1.1 \
  --device-id DEVICE_UUID \
  --commands wifi.set_mesh,vpn.policy.delete \
  --resume
```

Финальный gate для каждого стенда:

```sh
python scripts/command_validation_report.py certification/netis-nx31.json --require-complete
python scripts/command_validation_report.py certification/openwrt-x86.json --require-complete
```

После архитектурных изменений агента обязателен дополнительный runtime gate:

```sh
python scripts/runtime_validation_report.py \
  certification/netis-nx31.json \
  certification/openwrt-x86.json
```

Он не принимает старый `online` за доказательство восстановления. В evidence должны быть смена `boot_id`, новая telemetry, фактическая остановка/запуск daemon и полный браузерный lifecycle PTY.

`not_applicable` допустим только для capability, которую роутер явно объявил неподдерживаемой. `pass` без ссылки на лог, JSON result или снимок UCI не принимается.

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
| Agent update | установка текущего bundle и rollback успешны | | | |
| Agent rollback | предыдущая версия восстанавливается | | | |
| Command lifecycle | видны `sent`, `running` и terminal status | | | |

## Порядок

1. Подключите стенд по кабелю и сохраните внешний recovery-доступ.
2. Установите agent и выполните:

   ```sh
   wrtmonitor-agent capabilities --json
   wrtmonitor-agent diagnostics --json
   ```

3. Запустите полный `hardware_certify.py`. Runner сам создаёт backup, применяет команды через сервер и восстанавливает исходную конфигурацию.
4. Проверьте отчёт через `--require-complete`.
5. Убедитесь, что agent снова отправляет telemetry и исходный адрес управления доступен.

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
