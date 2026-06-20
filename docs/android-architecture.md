# Архитектура Android

`MainActivity` создаёт только root Compose. `WrtMonitorApp` содержит navigation shell. HTTP transport и JSON parsing находятся в `api/WrtMonitorApi`, результаты проходят через `ApiResult`, DTO лежат в `api/dto`.

Session URL и token централизованы в `data/SessionStore`. Вынесенные domain helpers покрываются unit tests; UI компоненты постепенно выносятся в `ui/components`.
