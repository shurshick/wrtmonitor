# Разработка

## Требования

- Python 3.12 или локальное `.venv`, созданное скриптом проекта;
- JDK 17 и Android SDK platform 35;
- Docker Desktop или Docker Engine для PostgreSQL и проверки образа;
- ShellCheck для OpenWrt agent.

## Автоматическая подготовка окружения

Рекомендуемый способ для Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-dev.ps1
```

Скрипт:

- ищет совместимый Python 3.12/3.13;
- при необходимости использует bundled Python Codex runtime;
- создает `.venv`;
- ставит `backend/requirements.txt`.

Повторные локальные проверки:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-local.ps1
```

## Проверки перед отправкой изменений

```sh
python -m pip install -r backend/requirements.txt
ruff check backend --select E9,F63,F7,F82
ruff format --check backend
pytest backend/tests openwrt-agent/tests
sh -n openwrt-agent/wrtmonitor-agent
shellcheck openwrt-agent/wrtmonitor-agent
./gradlew :android:app:testDebugUnitTest :android:app:assembleDebug
```

Для backend-тестов требуется PostgreSQL и переменные окружения из workflow `CI`.
Локально не используйте SQLite: production и тестовый контракт проекта основаны на PostgreSQL.
