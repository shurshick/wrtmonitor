# Подготовка публичного релиза

05.10.2026. Основа: v0.55.5. VERSION/RELEASE_TAG: 1.0.0/v1.0.0, Android versionCode 126. Runtime-код аппаратного прогона: `02a839063de3c2f8d60e63ba0bda39305f256ab3`. Последующие изменения evidence/документации/подписей не меняют runtime fingerprint.

## Заключение: готов к публичному выпуску

Владелец поручил аппаратный прогон, merge PR и выпуск. Новый полный E2E выполнен именно на 1.0.0: физический Netis и OpenWrt x86/VirtualBox. Лицензия Apache-2.0 оформлена. Решение с source fingerprint: [stable readiness](../certification/stable-readiness-v1.0.0.json). Публикация и перевод latest разрешаются только после успешных проверок окончательного коммита и собранных релизных файлов.

## Выполнено

1. После явного решения владельца оформлена Apache License 2.0: корневой LICENSE, README, копии для агента/Android и release inventory. [Решение владельца](license-decision.md).
2. README объясняет продукт, single-owner и целевой сценарий 1–20 устройств, не enterprise/multitenant; это позиционирование, не performance certification.
3. Добавлены [сравнение](comparison.md), [Quick Start](quick-start.md), [hardware matrix](hardware-compatibility.md), [troubleshooting](troubleshooting.md), [stable checklist](release-checklist-1.0.md).
4. Исправлены публичные отчёты/архивы, проверка backup tar и decompression limits, JWT обязательные claims, Android URL validation, bounded agent connection errors и обязательный DB password. [Security review](security-review-1.0.md).
5. Добавлены version mismatch/missing asset tests, Ed25519/RSA signing/tamper dry-run, APK metadata validation и полный подписанный release inventory с registry digest.
6. Stable gate требует отдельного решения владельца и полного физического E2E exact candidate; тестовые исключения и исторические отчёты не заменяют его.

## Проверки

Локальный PostgreSQL + backend/agent: **468 tests passed**, OpenWrt harness PASS, responsive browser smoke PASS. CI точного runtime commit: [push](https://github.com/shurshick/wrtmonitor/actions/runs/37285088002), [PR](https://github.com/shurshick/wrtmonitor/actions/runs/37285095206), [Security](https://github.com/shurshick/wrtmonitor/actions/runs/37285095019) - success. Проверены Ruff, ShellCheck, contracts/architecture, migrations/restore, Android debug/unit/lint/emulator, signed agent metadata, Docker smoke и PR deployment acceptance: clean install/upgrade с immutable 0.55.5. Изолированный PostgreSQL backup/restore drill также прошёл локально.

Окончательные CI/main/tag runs доступны в [PR #53](https://github.com/shurshick/wrtmonitor/pull/53) и [GitHub Actions](https://github.com/shurshick/wrtmonitor/actions). Release workflow отдельно собирает production-signed APK, проверяет versionName/versionCode и подпись. После публикации проверяются обе подписи release manifest и агента, все checksum, APK signer относительно 0.55.5, inventory commit, registry digest и OCI labels. Promotion переносит один immutable digest одновременно в GHCR latest и GitHub latest.

Одна известная Starlette/httpx deprecation warning; согласованное обновление dependencies вынесено в issue #38. Открытых CodeQL/Dependabot alerts на 05.10.2026 не обнаружено. Это не независимый пентест.

## Железо и ограничения

- [Netis NX31 1.0.0](../certification/netis-nx31-v1-0-0.json): 91 pass / 4 not applicable. Исправлена обнаруженная на реальном BusyBox ошибка проверки поднятого Wi-Fi SSID; гостевой профиль и rollback согласованы.
- [OpenWrt x86/VirtualBox 1.0.0](../certification/openwrt-x86-v1-0-0.json): 76 pass / 19 not applicable. Нет Wi-Fi PHY/температурных датчиков. Исправлен ложный отказ короткой PTY-сессии.
- На обоих стендах отдельная реальная повторная доставка/expiry и восстановление связи; хеши 60 установленных runtime-файлов совпадают с исходниками. Прежние отчёты 0.49.0 не изменены. [Метод проверки](hardware-validation-1.0.md).
- Владельцем подтверждены login, resume после сна, потеря сети и повторный вход Android. [Сообщение владельца](../certification/android-owner-validation-v1.0.0.json) не содержит версии APK: не объявляем финальный release APK вручную проверенным на телефоне. QR/все экраны/forced token expiry отдельно не подтверждены на телефоне.
- Многодневного soak, реальной перепрошивки и проверки внешнего VPN-трафика не было. Матрица проверяет API-дедупликацию всей области; fault injection проверяет реальную повторную доставку и expiry отдельно, не для каждой из 95 команд.
- Backup и terminal output приватны. Для issue используется ограниченный support report, не raw архив конфигурации.

## Решение владельца

Владелец выбрал Apache-2.0, предоставил recovery-доступ и доверенные SSH-ключи, запустил оба стенда и поручил выпуск после аппаратного прогона. Основные сценарии телефона подтверждены им отдельно. Gate 1.x принимает новый полный физический E2E с точным fingerprint; VM указан дополнительно, а не вместо физического стенда. Публичные evidence обезличены, оригиналы сохранены приватно.

[#51 — лицензия](https://github.com/shurshick/wrtmonitor/issues/51) и [#52 — кандидат/physical E2E](https://github.com/shurshick/wrtmonitor/issues/52) закрываются PR #53 с новыми доказательствами и явно ограниченным owner phone report. [#38 — coordinated dependency upgrade](https://github.com/shurshick/wrtmonitor/issues/38) остаётся post-1.0, не скрыт из roadmap.
