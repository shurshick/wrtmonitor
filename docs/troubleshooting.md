# Если роутер не подключается

Начните с `wrtmonitor-agent diagnostics`, `wrtmonitor-agent version` и `logread -e wrtmonitor`. Для сервера проверьте `/ready`, затем PostgreSQL и reverse proxy. Не отправляйте UCI export, ключи, `.env` или cookies в issue.

| Код / состояние | Что произошло | Что проверить |
|---|---|---|
| `dns_failed` / wget unable to resolve | Роутер не разрешает имя сервера | DNS WAN, `nslookup monitor.example.org`, правильность hostname |
| `server_unreachable` | Соединение не установлено | URL, порт, маршрут, firewall и работа сервера |
| `connection_timeout` | Нет ответа за отведённое время | WAN, доступность backend/proxy, не увеличивать timeout бесконечно |
| `tls_failed` | Не прошёл TLS | `date`, NTP, ca-bundle, срок/цепочка сертификата; не использовать `curl -k` |
| `authorization_failed` / 401 / 403 | Ключ или регистрация не приняты | Отзыв/ротация device token; повторная регистрация штатным installer, не выводить токен |
| `backend_unavailable` / 503 | Сервер не готов | `/ready`, PostgreSQL, логи контейнера |
| `http_error` | Неожиданный HTTP ответ | Адрес без лишнего path, proxy, технический HTTP status |
| outdated agent | Версия/контракт агента отстают | Обновление по подписанному manifest; дождаться новой telemetry |
| `skipped / downgrade blocked` | При последней проверке источник предлагал версию ниже установленной; агент безопасно отказался от отката | Обновить сервер, затем нажать «Проверить и обновить». В 1.0.1 Web/Android не выдают это за доступное обновление или аварию |
| offline / stale | Данные давно не приходили | Питание, WAN, служба wrtmonitor, интервал telemetry; не трактовать старые данные как текущие |
| unsupported capability | Компонент реально недоступен | PHY, пакеты/kernel modules и feeds; unsupported не является ошибкой обновления страницы |
| expired / timeout command | Команда не завершилась вовремя | Связь, журнал результата и post-condition; опасную команду не повторять вслепую |
| `post_condition_failed` | Изменение не подтверждено | Фактический runtime/UCI и результат rollback, а не только exit code процесса |

Код диагностики, HTTP status и `curl_exit` - технические детали для обращения. Проблемы часов могут вызвать TLS failure на роутере или отказ JWT на Android; синхронизируйте время сервера, роутера и телефона.

Пустой installer после неудачного wget не запускайте: повторите download с `&& test -s`, как в [Quick Start](quick-start.md). Обычное обновление не требует удаления роутера из БД и потери истории.

Web SSH требует owner session, same-origin WebSocket и проксирование upgrade. Открытие команды `agent.ssh_session` ещё не доказывает ввод/вывод PTY. Проверьте output, затем disconnect/reconnect. Инициализация сессии зависит от получения команды агентом; сама PTY работает через отдельный транспорт, не ждёт очередного интервала telemetry.

Для публичного hardware issue используйте [аппаратный JSON](hardware-compatibility.md). Диагностический архив и backup считаются приватными до отдельной проверки содержимого.

Для проверки обновлений без перезагрузки: `wrtmonitor-agent update-status --json`, затем `wrtmonitor-agent update`. Не используйте принудительный downgrade и не отключайте проверку подписей. Исправление отображения в Web требует обновления контейнера сервера до 1.0.1; новый APK также правильно обрабатывает данные старого сервера.
