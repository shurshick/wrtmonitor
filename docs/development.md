# Разработка

## Требования

- Python 3.12;
- JDK 17 и Android SDK platform 35;
- Docker Desktop или Docker Engine для PostgreSQL и проверки образа;
- ShellCheck для OpenWrt agent.

## Проверки перед отправкой изменений

```sh
pip install -r backend/requirements.txt
ruff check backend --select E9,F63,F7,F82
ruff format --check backend
pytest backend/tests openwrt-agent/tests
sh -n openwrt-agent/wrtmonitor-agent
shellcheck openwrt-agent/wrtmonitor-agent
./gradlew :android:app:testDebugUnitTest :android:app:assembleDebug
```

Для backend-тестов требуется PostgreSQL и переменные окружения из workflow `CI`.
Локально не используйте SQLite: production и тестовый контракт проекта основаны на PostgreSQL.
