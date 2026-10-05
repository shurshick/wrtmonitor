# Как выбрать инструмент

WrtMonitor нужен, когда один владелец хочет единый обзор нескольких домашних/удалённых OpenWrt-роутеров и мобильное управление. Для одного устройства LuCI обычно проще. Для конфигурации из playbook подходит SSH/Ansible; для организаций и множества операторов стоит рассматривать OpenWISP.

| Критерий | LuCI | SSH / Ansible | OpenWISP | WrtMonitor |
|---|---|---|---|---|
| Размещение | На роутере | Свой компьютер/сервер | Self-hosted сервер | Self-hosted сервер |
| Несколько устройств | Отдельный UI каждого | Inventory и playbook | Централизованный контроллер | Общий Web UI и Android |
| Web UI | Да | SSH нет; UI зависит от выбранных дополнений | Да | Да |
| Android | Мобильный браузер | Сторонний SSH-клиент | В данном сравнении нативный клиент не оценён | Собственный клиент |
| Удалённый доступ | Нужен защищённый путь к роутеру | Нужна SSH-доступность | OpenWrt configuration/monitoring agents; транспорт зависит от модулей | Исходящие запросы агента к серверу |
| Агент | Не требуется отдельный контроллерный агент | SSH; raw-модуль может работать без Python на роутере | openwisp-config, monitoring agent | wrtmonitor-agent |
| Общий мониторинг | Нет между несколькими LuCI | Нужны дополнительные средства | Monitoring module | Telemetry, история, события |
| Общая конфигурация | Отдельно на роутере | Playbook | Controller module | Типизированные команды и проверки результата |
| Терминал | Не предполагается этим сравнением | SSH | Не оценён | Web PTY через исходящий канал |
| Сложность | Минимальная для одного роутера | Требует SSH и playbook | Набор серверных модулей | Docker + PostgreSQL + агент |
| Пользователи / организации | Администрирование роутера | Определяется внешним окружением | Users и multi-tenancy | Один владелец, без RBAC |
| Размер сценария | Отдельное устройство | Зависит от automation | Организации и управляемые сети | Целевой сценарий 1–20; не benchmark |

Неизмеренные характеристики не объявлены недостатками других проектов. WrtMonitor не обещает весь набор LuCI-пакетов и не заменяет локальный аварийный доступ.

Источники проверены 2026-10-05: [LuCI](https://openwrt.org/docs/guide-user/luci/start), [защищённый доступ LuCI](https://openwrt.org/docs/guide-user/luci/luci.secure), [Ansible raw](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/raw_module.html), [OpenWISP architecture](https://openwisp.io/docs/24.11/general/architecture.html), [текущая документация OpenWISP](https://openwisp.io/docs/index.html). Данные WrtMonitor основаны на коде и [матрице функций](supported-features.md).
