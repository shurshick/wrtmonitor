# Архитектура backend

`main.py` является тонким ASGI entrypoint. `app_factory.py` создаёт FastAPI, подключает security middleware, static files и регистрирует route layer. API постепенно разделяется на `api/`, Web UI находится в `routes.py` и Jinja2 templates, а бизнес-правила вынесены в `services/`.

Web UI использует CSRF и security headers. PostgreSQL schema обновляется Alembic. Telemetry хранится raw JSONB и отдаёт нормализованный summary; lifecycle команд создаётся сервисом и сохраняет статусы, результат и истечение.
