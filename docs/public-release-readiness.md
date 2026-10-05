# Подготовка публичного релиза

05.10.2026. Основа: v0.55.5. По поручению владельца подготовлены VERSION/RELEASE_TAG кандидата 1.0.0 и Android versionCode 126. Git tag не создан, latest не менялся, v1.0.0 не опубликован.

## Заключение: NOT READY

Не рекомендую помечать текущую ветку stable: нет полного аппаратного отчёта именно изменённого кандидата и ручного прогона Android на телефоне. Лицензия Apache-2.0 выбрана владельцем и оформлена; юридический блокер устранён.

## Выполнено

1. После явного решения владельца оформлена Apache License 2.0: корневой LICENSE, README, копии для агента/Android и release inventory. [Решение владельца](license-decision.md).
2. README объясняет продукт, single-owner и целевой сценарий 1–20 устройств, не enterprise/multitenant; это позиционирование, не performance certification.
3. Добавлены [сравнение](comparison.md), [Quick Start](quick-start.md), [hardware matrix](hardware-compatibility.md), [troubleshooting](troubleshooting.md), [stable checklist](release-checklist-1.0.md).
4. Исправлены публичные отчёты/архивы, проверка backup tar и decompression limits, JWT обязательные claims, Android URL validation, bounded agent connection errors и обязательный DB password. [Security review](security-review-1.0.md).
5. Добавлены version mismatch/missing asset tests, Ed25519/RSA signing/tamper dry-run, APK metadata validation и полный подписанный release inventory с registry digest.
6. Stable gate требует отдельного решения владельца и полного физического E2E exact candidate; тестовые исключения и исторические отчёты не заменяют его.

## Проверки

Локальный PostgreSQL + backend/agent на кандидате 1.0.0: 453 tests passed; OpenWrt harness PASS, responsive browser smoke PASS. Android debug build, unit tests, lint и APK signature/version metadata прошли до повышения версии; новый APK 1.0.0 ещё должен пройти CI. Финальный CI фиксируется в [PR #53](https://github.com/shurshick/wrtmonitor/pull/53), не подменяется результатами прошлых релизов. Одна известная Starlette/httpx deprecation warning, обновление dependencies вынесено в issue #38.

Новая ветка должна пройти CI: Ruff, ShellCheck, contracts, migrations/restore, Android unit/build/lint/emulator, signed agent metadata и Docker clean install/upgrade с 0.55.5; Security: Gitleaks, CodeQL, dependency review. До завершения этих runs их статус не считается passed. Production inventory на реальных release keys/digest будет проверен только при отдельном теге.

## Железо и ограничения

- Netis NX31: исторический полный E2E 0.49.0 от 24.08.2026 (91 pass / 4 not applicable); отдельный короткий PTY-тест 0.55.4 не заменяет полный прогон нового кандидата.
- OpenWrt x86/VirtualBox: исторический полный E2E 0.49.0 (76 pass / 19 not applicable), без Wi-Fi/температур. Владелец запустил VM; SSH отвечает, но ключ отличается от сохранённого. У Netis также нет совпадения с доверенным ключом. Запрошена сверка через консоли стендов; пароли не отправляются до подтверждения.
- Новый backend/agent этой ветки не установлен на аппаратный стенд: новый полный E2E не выполнен. Нельзя писать, что 1.0 сертифицирован.
- Android emulator не заменяет ручную установку APK и сон/возобновление/смену сети на телефоне.
- Backup и terminal output приватны. Для issue используется ограниченный support report, не raw архив конфигурации.

## Решение владельца

Утвердить конкретный кандидат и окно полного физического прогона с резервной копией/доступом для восстановления; проверить Android на телефоне; после зелёного CI и доказательств отдельно одобрить stable. Только затем синхронно менять VERSION/RELEASE_TAG/VERSION_CODE и публиковать v1.0.0, проверять подписи/версии/образ и переводить latest.

[#51 — лицензия](https://github.com/shurshick/wrtmonitor/issues/51): решение владельца выполнено в PR #53. [#52 — кандидат/physical E2E](https://github.com/shurshick/wrtmonitor/issues/52) остаётся 1.0-blocker. [#38 — coordinated dependency upgrade](https://github.com/shurshick/wrtmonitor/issues/38) классифицирован post-1.0; открытых CodeQL/Dependabot security alerts на момент аудита нет.
