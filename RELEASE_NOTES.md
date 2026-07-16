# v0.2.0-rc1-full-router-foundation

Первый релиз новой функциональной ветки WrtMonitor. Основная цель - перейти от набора отдельных кнопок к единой модели управления OpenWrt через сервер, Android и Web UI.

## Что изменилось

- OpenWrt agent отправляет telemetry schema v2: система, hostname, kernel, load 1/5/15, conntrack, сервисы, интерфейсы, расширенный Wi-Fi, DHCP leases и сетевые клиенты.
- Сервер нормализует `system`, `services`, `network`, `wifi` и `clients`, поэтому интерфейсы больше не разбирают сырой `ubus` самостоятельно.
- Добавлены команды изменения Wi-Fi канала и региона.
- Добавлены переподключение отдельного интерфейса и полный перезапуск сети.
- Добавлены изменение hostname и перезапуск сервисов из allowlist: `network`, `dnsmasq`, `firewall`, `odhcpd`.
- Добавлено создание, изменение и удаление статических DHCP-выдач.
- Все изменения UCI проходят серверную валидацию, требуют подтверждение, попадают в аудит и создают backup затронутого config-файла.
- Web UI получил отдельный блок клиентов и новые элементы управления сетью, Wi-Fi и системой.
- Android получил вкладку клиентов и тот же набор capability-aware команд.
- Настройки Android вынесены из нижней навигации в кнопку верхней панели; нижняя навигация теперь посвящена управлению роутером.
- FastAPI startup переведён на lifespan API, старые deprecation warnings тестового контура убраны.

## Обновление

Сервер обновляется обычным redeploy образа `ghcr.io/shurshick/wrtmonitor:latest`. PostgreSQL volume сохраняется.

Агент `0.2.0-rc1` можно обновить через Web UI/Android или вручную:

```sh
wrtmonitor-agent update
wrtmonitor-agent version
wrtmonitor-agent send-now
```

После обновления проверьте `agent capabilities`: новая панель управления появляется только после первой telemetry от нового агента.

## Артефакты

- `wrtmonitor-truenas-v0.2.0-rc1.yaml`
- `wrtmonitor-openwrt-agent-v0.2.0-rc1.tar.gz`
- `wrtmonitor-android-v0.2.0-rc1-debug.apk`
- `SHA256SUMS.txt`

Это prerelease для тестирования. Полное управление OpenWrt остаётся направлением развития; этот релиз закладывает расширяемый и проверяемый фундамент.
