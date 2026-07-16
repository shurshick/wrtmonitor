# Безопасность

## Текущее состояние

- Первый администратор создаётся через `/setup`.
- Пароли хранятся как Argon2 hash.
- Android получает JWT access token через `/api/v1/auth/login`.
- Android хранит серверный URL, access token и базовую сессию в `EncryptedSharedPreferences`.
- OpenWrt agent использует отдельный device token.
- Device token хранится на сервере только как hash.
- Web UI `/devices` требует вход через `/login`.
- Все Web UI POST-формы защищены CSRF-токеном; детали описаны в [security-web-ui.md](security-web-ui.md).
- API-документация `/docs`, `/redoc`, `/openapi.json` по умолчанию выключена.
- Команды управления выполняются только через allowlist.
- Произвольные shell-команды на роутере не поддерживаются.
- Доступ к серверным устройствам сейчас жёстко ограничен моделью `single-owner`.

## Startup checks

Сервер не стартует, если:

- `WRTMONITOR_JWT_SECRET` пустой;
- `WRTMONITOR_JWT_SECRET` короче 32 символов;
- `WRTMONITOR_JWT_SECRET` равен дефолтному `change-me-*`;
- пароль PostgreSQL в `WRTMONITOR_DATABASE_URL` пустой;
- пароль PostgreSQL начинается с `change-me`;
- используется не PostgreSQL URL.

Исключение для тестов и CI возможно только при явном:

```env
WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS=true
```

На реальном сервере этот параметр должен быть:

```env
WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS=false
```

## HTTPS

Production `server_url` должен быть HTTPS. Локальный HTTP разрешается только для временного теста:

```env
WRTMONITOR_ALLOW_INSECURE_LOCAL=true
```

## Что намеренно не включено

- произвольное выполнение shell-команд на роутере;
- входящий порт из интернета на OpenWrt;
- хранение device token в открытом виде на сервере;
- SQLite-режим для production.
