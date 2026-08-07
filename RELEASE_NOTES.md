## [0.35.12] - 2026-08-07

### Fixed
- Fixed Web SSH upload stream failing instantly due to `PUT` method from `curl -T` being rejected by a `POST` endpoint on the FastAPI backend.

## [0.35.11] - 2026-08-07

### Fixed
- Fixed agent version reporting (agent was stuck reporting `0.35.8`).

## [0.35.10] - 2026-08-07

### Changed
- Removed `websocat` dependency from the OpenWrt-agent script. Web SSH now works via standard `curl` streams natively on OpenWrt, increasing stability and compatibility with older firmwares.

## [0.35.9] - 2026-08-07

### Fixed
- Fixed Web SSH button triggering a full page reload.
- Added proper error handling in UI when agent fails to install websocat.


# v0.35.8 — Advanced Device Management (Продвинутое управление)

Расширение возможностей управления самими роутерами OpenWrt, превращение WrtMonitor в полноценный Fleet Manager.

- **Remote Terminal (Web SSH)**: Реализация интерактивного терминала к командной строке роутера прямо из Web UI через уже существующий защищённый WebSocket туннель (проксируемый через агента). Никаких пробросов портов наружу.
- **Групповые политики (Fleet Management)**: Возможность применить действие (например, запуск скрипта) на несколько устройств одновременно, объединенных в группы.
- **Auto-Update Crypto Signatures**: Внедрена обязательная криптографическая проверка подписи агента (RSA/Ed25519) при автоматических обновлениях.
- **Улучшения мобильного приложения**: Переработан экран настроек для устранения бесконечной прокрутки. Уведомления сервера временно отключены. Логика проверки обновлений переработана для скачивания APK напрямую с GitHub и передачи в системный установщик.
- **Исправление копирайта**: Обновлена информация в разделе "О приложении".

**Патчи (v0.35.1 - v0.35.8)**:
- Исправлена ошибка валидации WebSocket сессии.
- Исправлена ошибка `TypeError` при сохранении команды `agent.ssh_session` в базу данных.
- Исправлено скрытие кнопки Connect во время установки соединения, чтобы отображались ошибки подключения.
- Исправлено падение агента (`exit code 127: command not found`) при обработке команды Web SSH из-за отсутствия функции `submit_command_result`. Команды агента теперь корректно рапортуют статус и лог обратно на сервер.
