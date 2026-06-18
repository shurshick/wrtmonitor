# Безопасность

- Первый администратор создаётся через `/setup`.
- Пароли хранятся как Argon2 hash.
- Android получает JWT access token.
- OpenWrt agent использует отдельный device token.
- Device token хранится на сервере только как hash.
- Команды управления выполняются только через allowlist.
- Все команды пишутся в аудит.
- Production `server_url` должен быть HTTPS.
