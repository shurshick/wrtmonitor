# Архитектура Android

`MainActivity` включает edge-to-edge и создаёт только root Compose. `WrtMonitorApp` содержит адаптивный navigation shell: нижнюю навигацию на телефоне и Navigation Rail на экранах от 720 dp. HTTP transport и JSON parsing находятся в `api/WrtMonitorApi`, результаты проходят через `ApiResult`, DTO лежат в `api/dto`.

Тема и визуальные токены находятся в `ui/theme`, общие компоненты и состояния - в `ui/components`. Экраны не определяют собственные палитры. Светлая и тёмная темы управляют также контрастом системных status/navigation bars.

Session URL и token централизованы в `data/SessionStore`. Вынесенные domain helpers покрываются unit tests; UI компоненты постепенно выносятся в `ui/components`.

QR подключение находится в `pairing/MobilePairing.kt` и `ui/screens/QrScannerScreen.kt`. Сканер использует CameraX и ML Kit, разрешение камеры запрашивается только при открытии экрана. JSON v1 разбирается строго: внешний HTTP, путь, userinfo, query и неподдерживаемая версия отклоняются до сетевого запроса.

Pairing response сохраняется тем же атомарным `SessionStore`, что и ручной вход. `SessionStore` использует только `EncryptedSharedPreferences`; fallback в plaintext отсутствует.
