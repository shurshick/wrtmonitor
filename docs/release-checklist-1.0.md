# Переход к v1.0.0

Checklist публичного выпуска 1.0.0. Фактические результаты и ограничения фиксируются в [отчёте](public-release-readiness.md); проверка артефактов выполняется после сборки тега, перед переводом latest.

## Обязательные решения

- [x] Владелец выбрал Apache License 2.0; корневой LICENSE и README согласованы. [Решение](license-decision.md).
- [x] Зафиксированы версия 1.0.0, Android versionCode 126 и runtime исходники `02a8390`; состав APK/образа/агента проверяется inventory при сборке.
- [x] Полный E2E кандидата на физическом Netis; отдельные real delivery/expiry проверки на обоих стендах. [Метод](hardware-validation-1.0.md) не приписывает forced faults каждой команде.
- [x] Отчёт содержит exact server/agent version, hardware_kind=physical_router и проверяемые evidence. Старые отчёты и VM не заменяют этот минимум.
- [x] Владелец поручил аппаратный прогон, merge PR и выпуск; границы проверки явно опубликованы.

Для 1.x `scripts/verify_release_readiness.py` требует LICENSE, `certification/stable-readiness-v1.0.0.json` с решением владельца и полные физические отчёты именно кандидата. Исключения тестовых 0.x не применяются. Это минимальный stable gate по данной задаче, а не утверждение о завершённом 7–14-дневном soak.

## Backend и развёртывание

- [x] 468 локальных PostgreSQL/backend/agent тестов; CI Ruff, contracts/architecture.
- [x] CI deployment acceptance: чистая установка и обновление с immutable 0.55.5, сохранность владельца/роутера.
- [x] Setup/login/ready/pairing/telemetry/commands покрыты интеграционными и браузерными тестами; физический агент подключён к изолированному серверу.
- [x] PostgreSQL backup создан, проверен и восстановлен в отдельной БД; инструкция [здесь](server-operations.md).
- [x] Docker smoke и TrueNAS compose validation в CI. Внешний production reverse proxy владельца не развёртывался заново.

## Агент

- [x] ShellCheck, sh -n, unit/simulation и OpenWrt harness.
- [x] Физические registration/telemetry, установка точного runtime, signed update, rollback и command lifecycle. Это не свежая установка OpenWrt.
- [x] Неподдерживаемые функции не показываются как доступные; timeout и неизвестный verifier не дают ложный success.
- [x] DNS/TLS/auth/offline ошибки имеют код и действие; публичный архив не содержит raw config/log/process arguments.

## Web

- [x] Браузерный smoke: login, роутеры и основные разделы на desktop/mobile.
- [x] Аппаратный Web SSH: ввод/вывод/resize, повторное подключение и закрытие; TTL/expiry покрыты backend regression, не длительным ожиданием физической сессии.
- [x] Desktop/mobile, светлая/тёмная тема, подтверждения опасных действий в browser regression.

## Android

- [x] Unit, debug build, lint, emulator UI tests на 1.0.0 прошли CI; подпись и метаданные release APK проверяются при сборке тега.
- [x] Владелец подтвердил на телефоне login, resume после сна, потерю сети и повторный вход.
- [ ] Версия APK на телефоне, QR pairing, все экраны и принудительное истечение токена не записаны отдельно; не объявлены проверенными вручную. Сценарии сессий покрыты автоматическими тестами.
- [x] Доступ по внешнему HTTP запрещён; private LAN HTTP остаётся осознанным тестовым исключением.

## Безопасность и публикация

- [x] History secret scan, CodeQL, dependency audit/review прошли на runtime commit; новый metadata commit повторно проверяется CI.
- [x] CSRF, owner/device authorization, WS Origin/session binding, token rotation, upload/archive tests.
- [x] VERSION/RELEASE_TAG/agent согласованы, VERSION_CODE 126 больше 125; tag/APK сверяются при публикации.
- [ ] Immutable image digest записан в RELEASE_INVENTORY.json, все файлы покрыты RELEASE_SHA256SUMS.txt и Ed25519/RSA подписями.
- [x] Release notes содержат фактические изменения, ограничения и инструкции обновления.
- [x] Workflow публикует тег сначала как prerelease; stable/latest переводятся после решения владельца, exact-candidate E2E, зелёного CI и проверки файлов.

Зелёный CI проверяет код и воспроизводимость, но не заменяет аппаратный прогон, телефон и юридическое решение. [Текущий отчёт](public-release-readiness.md).

## Проверка файлов при выпуске

RELEASE_SHA256SUMS покрывает APK, agent tar.gz, TrueNAS YAML, agent manifest/signatures/version, LICENSE и RELEASE_INVENTORY.json. Сам манифест имеет отдельные Ed25519/RSA подписи; inventory содержит immutable registry digest и исходный commit. SHA256SUMS.txt отдельно описывает файлы внутри agent archive, а не APK/контейнер.

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

Затем сравнить registry digest и OCI version/revision labels с inventory; версия приложения внутри запущенного образа также должна совпадать. Подпись APK и agent manifest проверяются отдельно. Эти файлы создаёт workflow тега 1.0.0; существующий 0.55.5 задним числом ими не объявляется покрытым.
