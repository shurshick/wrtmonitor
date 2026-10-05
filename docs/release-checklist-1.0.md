# Переход к v1.0.0

Текущая опубликованная версия 0.55.5 остаётся тестовой. Эта подготовка не выпускает 1.0, не меняет latest и не означает stable.

## Обязательные решения

- [ ] Владелец выбрал лицензию; корневой LICENSE и README согласованы. [Открытый вопрос](license-decision.md).
- [ ] Зафиксированы версия, commit и runtime fingerprint кандидата, состав APK/образа/агента.
- [ ] Минимум один **полный E2E кандидата на физическом OpenWrt-роутере**, включая повторную доставку, timeout, post-condition и восстановление связи.
- [ ] Отчёт содержит exact server/agent version, hardware_kind=physical_router и проверяемые evidence. Старые отчёты и VM не заменяют этот минимум.
- [ ] Владелец отдельно одобрил public stable и известные ограничения.

Для 1.x `scripts/verify_release_readiness.py` требует LICENSE, `certification/stable-readiness-v1.0.0.json` с решением владельца и полные физические отчёты именно кандидата. Исключения тестовых 0.x не применяются. Это минимальный stable gate по данной задаче, а не утверждение о завершённом 7–14-дневном soak.

## Backend и развёртывание

- [ ] Unit/PostgreSQL/API tests, Ruff, contracts/architecture зелёные на commit кандидата.
- [ ] Alembic: чистая установка и обновление с immutable 0.55.5, данные владельца/роутеров сохранены.
- [ ] `/setup`, owner login, `/ready`, QR pairing, первая telemetry и безопасная команда проверены.
- [ ] PostgreSQL backup создан, проверен и восстановлен в отдельной БД; инструкция [здесь](server-operations.md).
- [ ] Docker/TrueNAS compose воспроизводимы без dev defaults; HTTPS proxy передаёт WebSocket/SSE.

## Агент

- [ ] ShellCheck, sh -n, unit/simulation и OpenWrt harness.
- [ ] Физические installation/registration/telemetry, signed upgrade, rollback и command lifecycle.
- [ ] Неподдерживаемые функции не показываются как доступные; timeout и неизвестный verifier не дают ложный success.
- [ ] DNS/TLS/auth/offline ошибки имеют код и действие; публичный архив не содержит raw config/log/process arguments.

## Web

- [ ] Login, роутеры, dashboard, clients, WAN/LAN, Wi-Fi, firewall, VPN, system, events/logs.
- [ ] Terminal: ввод/вывод/resize, разрыв, повторное подключение, закрытие и expiry.
- [ ] Desktop/mobile, светлая/тёмная тема, подтверждения опасных действий.

## Android

- [ ] Unit, build, lint, emulator UI tests; APK signature/versionCode/versionName проверены.
- [ ] На реальном телефоне: установка APK, login, QR pairing, refresh, все основные экраны, безопасная команда.
- [ ] Подтверждение опасной операции, offline/online, background/resume, истечение токена, logout/login.
- [ ] Доступ по внешнему HTTP запрещён; private LAN HTTP остаётся осознанным тестовым исключением.

## Безопасность и публикация

- [ ] History/current-tree secret scan, CodeQL, dependency audit/review без новых high/critical.
- [ ] CSRF, owner/device authorization, WS Origin/session binding, token rotation, upload/archive tests.
- [ ] Имя Git tag и версии server/APK/agent/TrueNAS совпадают, VERSION_CODE монотонный.
- [ ] Immutable image digest записан в RELEASE_INVENTORY.json, все файлы покрыты RELEASE_SHA256SUMS.txt и Ed25519/RSA подписями.
- [ ] Release notes содержат фактические изменения, ограничения и инструкции обновления.
- [ ] Тег публикуется сначала как prerelease; stable/latest переводятся только после отдельного решения владельца и проверки файлов.

Зелёный CI проверяет код и воспроизводимость, но не заменяет аппаратный прогон, телефон и юридическое решение. [Текущий отчёт](public-release-readiness.md).

## Проверка файлов при выпуске

RELEASE_SHA256SUMS покрывает APK, agent tar.gz, TrueNAS YAML, agent manifest/signatures/version и RELEASE_INVENTORY.json. Сам манифест имеет отдельные Ed25519/RSA подписи; inventory содержит immutable registry digest и исходный commit. SHA256SUMS.txt отдельно описывает файлы внутри agent archive, а не APK/контейнер.

Публичные ключи берутся из заранее доверенного checkout, не из того же непроверенного download. В каталоге загруженных release assets:

```sh
base64 -d RELEASE_SHA256SUMS.sig > /tmp/release-ed.sig
openssl pkeyutl -verify -pubin -inkey /trusted/wrtmonitor/openwrt-agent/update-ed25519-public-key.pem \
  -rawin -in RELEASE_SHA256SUMS.txt -sigfile /tmp/release-ed.sig
base64 -d RELEASE_SHA256SUMS.rsa.sig > /tmp/release-rsa.sig
openssl dgst -sha256 -verify /trusted/wrtmonitor/openwrt-agent/update-rsa-public-key.pem \
  -signature /tmp/release-rsa.sig RELEASE_SHA256SUMS.txt
sha256sum --check RELEASE_SHA256SUMS.txt
```

Затем сравнить registry digest и OCI version/revision labels с inventory; версия приложения внутри запущенного образа также должна совпадать. Подпись APK и agent manifest проверяются отдельно. Эти файлы будут созданы новым workflow при отдельном теге; существующий 0.55.5 задним числом ими не объявляется покрытым.
