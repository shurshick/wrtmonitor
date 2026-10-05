# Security review перед 1.0

Дата: 05.10.2026. Scope: ветка подготовки от v0.55.5, не независимый пентест и не сертификат безопасности.

## Исправлено

- Hardware/support report использовал вложенные runtime dictionaries и мог включать hostname, SSID, адреса или произвольные поля. Теперь экспорт ограничен явной схемой: модель/CPU/датчики/версии/коды проверок; рекурсивные regression tests.
- Архив сервера включал public URL, имена устройств и свободные сообщения уведомлений. Теперь только обезличенные отчёты, агрегированные счётчики и типы событий.
- Архив агента содержал raw network, logread и `ps w`. Даже без UCI эти файлы могут раскрывать токены и адреса. Эти источники исключены, CLI и команда используют один ограниченный сборщик.
- JWT декодирование не требовало обязательного exp. Access/refresh теперь требуют exp/iat/sub/type, refresh также jti; regression test токенов без exp.
- Android принимал домены с префиксом fc/fd за private IPv6. Проверка теперь принимает только корректный IP literal, а не DNS-имя; IPv4 также проверяется целиком.
- Compose больше не запускает PostgreSQL со скрытым fallback change-me: пароль обязателен.
- Restore раньше проверял только gzip header и пути. Теперь сервер проверяет содержимое tar, запрещает symlink/hardlink/devices/traversal и ограничивает распакованный размер 16 MiB/4096 entries; агент дополнительно запрещает ссылки и special files. Regression tests проверяют повреждённый gzip и decompression bomb.
- PostgreSQL backup теперь создаётся через уникальный temporary file с POSIX mode 0600 вместо предсказуемого `.tmp`; regression test проверяет права и защиту от подставленного symlink.
- Добавлены полный history secret scan и подписанный inventory всех релизных файлов с image digest. Проверка изменения манифеста после подписи должна завершаться отказом.

## Проверенные границы

| Область | Реализация/покрытие | Ограничение |
|---|---|---|
| Credentials/debug/CORS | startup validation, setup owner, Argon2; API docs default off; broad CORS middleware отсутствует | dev/local switches нельзя включать в production |
| CSRF/cookies | Web POST CSRF, HttpOnly/Secure/SameSite, тесты Web security | HTTPS proxy обязан сохранять канонический host |
| Refresh/pairing | hash-only storage, rotation/revocation, одноразовый QR, rate limit | QR и refresh token нельзя публиковать |
| Device/commands | device token + owner device lookup, allowlist/typed command schemas, validation/post-condition | owner shell/cron намеренно способны выполнять произвольный код |
| Web SSH | cookie owner, same Origin, session/device binding, TTL и ограничения frames; PTY E2E mock | новый физический прогон кандидата ещё нужен |
| Upload/download | authenticated artifact endpoints, bounded backup upload, проверка archive members | backup специально содержит приватную конфигурацию |
| Shell/UCI | quoted arguments, параметры по схемам, команды не формируются из shell=True; harness и ShellCheck | это аудит существующих границ, не доказательство отсутствия любых injection |
| Android | EncryptedSharedPreferences без plaintext fallback; URL validator перед login/pairing/settings | usesCleartextTraffic=true нужен для private LAN; ОС не ограничивает его до LAN, это делает приложение |
| Logs/reports | токены не пишутся в auth audit; public reports allowlist | raw logs, terminal output и owner backup не обезличены и не должны уходить в issue |
| Signing | Ed25519/RSA agent trust, APK signing; полный inventory/hash dry-run | production signatures и registry digest нового тега проверяются при фактической публикации |

## Secret scan

Gitleaks v8.30.1, официальная сборка с проверенным SHA-256: полный git history `--all`, 361 commit до изменений этой ветки. Найден false positive на присваивании JavaScript FourKeyMap/TwoKeyMap в vendored xterm. Его цитата в первом commit аудита также сработала как false positive. В `.gitleaksignore` исключены только два точных fingerprint этих commit/file/line, не vendor-директория и не документация целиком. Новый CI повторяет полный scan для новых commit; ключи, тестовые credentials и dev switches не скрыты широким allowlist.

Модель/firmware в публичном отчёте нужны для совместимости и не считаются секретом автоматически. Перед публикацией всё равно просмотрите файл. Backup, UCI, terminal transcript, raw telemetry и локальные credentials не являются публичным support report.

## Остаётся

Свежий полный физический E2E кандидата, ручные сценарии Android и проверка production release artifacts при отдельном выпуске. Лицензия Apache-2.0 выбрана владельцем и оформлена. Не выдаём старую сертификацию за новую. [Checklist](release-checklist-1.0.md).
