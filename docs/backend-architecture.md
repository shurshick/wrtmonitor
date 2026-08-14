# Архитектура backend

`main.py` является тонким ASGI entrypoint. `app_factory.py` создаёт FastAPI, подключает security middleware, static files и регистрирует route layer. API разделён на `api/`, Web UI — на компактные маршруты и сборщики контекста, а предметные правила находятся в `services/`.

На текущем этапе backend работает в честной модели `single-owner`: авторизованный пользователь считается владельцем всего сервера, а доступ к устройствам не размазан между несколькими ролями.

Web UI использует CSRF и security headers. PostgreSQL schema обновляется Alembic. Telemetry хранится raw JSONB и отдаёт нормализованный summary; lifecycle команд создаётся сервисом и сохраняет статусы, результат и истечение.

## Границы модулей

- `domain_models/` содержит SQLAlchemy-модели по областям: identity, devices, telemetry, hardware, commands, clients и operations. `models.py` остаётся только совместимым фасадом импортов.
- `web/routes_device.py` отвечает за HTTP-поток страницы, а `web/device_context.py` собирает её данные.
- `web/routes_commands.py` принимает обычные команды; QR и артефакты, backup и preview находятся в отдельных route-модулях.
- `services/client_identity.py` нормализует MAC и тип устройства, `client_presence.py` вычисляет присутствие, `client_registry.py` хранит инвентаризацию и представление клиента.
- `services/hardware_profiles.py` содержит встроенный каталог, `hardware_catalog.py` сопоставляет наблюдения, `hardware_reporting.py` строит пользовательский отчёт.
- telemetry уже разделена по system, network, Wi-Fi, clients, maintenance и history; `services/telemetry.py` — только публичный фасад.

CI ограничивает размер фасадов и предметных модулей. Новая ответственность добавляется в свою область, а не обратно в `models.py`, `routes_device.py` или универсальный service-файл.
