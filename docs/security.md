# Безопасность

## Текущее состояние

- Первый администратор создаётся через `/setup`.
- Пароли хранятся как Argon2 hash.
- Android получает 15-минутный JWT access token и управляемый refresh-token через `/api/v1/auth/login`.
- Refresh-token хранится на сервере только как hash, ротируется при каждом использовании и отзывается при выходе или смене пароля.
- Android хранит server URL и tokens в `EncryptedSharedPreferences`.
- Plaintext fallback Android удалён: ошибка Android Keystore не переключает приложение на обычные `SharedPreferences`.
- Mobile pairing token действует 10 минут, используется один раз и хранится в PostgreSQL только как hash.
- Попытки pairing ограничиваются по hash источника и token; исходные pairing/access/refresh tokens не записываются в аудит.
- OpenWrt agent использует отдельный device token.
- Device token хранится на сервере только как hash.
- Web UI `/devices` требует вход через `/login`.
- Production cookies имеют `HttpOnly`, `Secure` и `SameSite=Lax`.
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

Даже при включённом параметре HTTP принимается только для loopback, link-local и private LAN адресов. Внешний домен с HTTP отклоняется. QR использует канонический `WRTMONITOR_PUBLIC_SERVER_URL`, а не заголовок `Host` от reverse proxy.

При `false` Web UI использует cookie `Secure` и должен открываться по внешнему
HTTPS-адресу. Вход через прямой `http://IP:порт` в этом режиме намеренно
блокируется. Android использует bearer/refresh-токены и от browser cookie не
зависит.

## Что намеренно не включено

- произвольное выполнение shell-команд на роутере;
- входящий порт из интернета на OpenWrt;
- хранение device token в открытом виде на сервере;
- SQLite-режим для production.
