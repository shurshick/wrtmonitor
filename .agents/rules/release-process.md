# WrtMonitor Release Process

При выпуске новых релизов WrtMonitor необходимо соблюдать следующий процесс, чтобы теги Docker-образов и релизы на GitHub корректно получали статус `latest`.

## Проблема с Canary Soak Time

В репозитории настроен CI/CD пайплайн (`ci.yml` и `promote-latest.yml`), который по умолчанию публикует новые релизы как **Pre-release** (предрелиз). 
Это сделано для обкатки (canary soak time), которая длится 24 часа. До истечения этого времени новый релиз не получит метку `latest` в GitHub, а Docker-образ в `ghcr.io` не получит тег `latest`.

## Как выпускать релиз и сразу делать его Latest

Если пользователь запрашивает выпуск релиза и хочет, чтобы он **сразу** стал доступен по тегу `latest` (например, для немедленного деплоя), необходимо выполнить следующие шаги:

1. **Подготовка:**
   - Обновить версию в файлах `VERSION`, `RELEASE_TAG`, `openwrt-agent/agent-version.txt`, `README.md` и других.
   - Обязательно обновить строку `AGENT_VERSION="..."` в скрипте `openwrt-agent/wrtmonitor-agent`.
   - Перегенерировать `openwrt-agent/SHA256SUMS.txt` (можно использовать скрипт на Python с `hashlib.sha256`).
   - Добавить описание релиза в `CHANGELOG.md` и `RELEASE_NOTES.md`.
2. **Коммит и тег:**
   - Сделать коммит: `git commit -m "chore(release): vX.Y.Z"`
   - Создать тег: `git tag vX.Y.Z`
   - Запушить изменения: `git push origin main vX.Y.Z`
3. **Ожидание сборки:**
   - Дождаться успешного завершения пайплайна `ci.yml` для опубликованного тега. Это собирает Docker-образы с тегом версии (например, `v0.33.2`).
4. **Промоут до Latest (КРИТИЧНО):**
   - Чтобы немедленно снять статус Pre-release и обновить тег `latest` для Docker-образа, необходимо вручную запустить workflow `promote-latest.yml` с флагом обхода задержки:
   ```bash
   gh workflow run promote-latest.yml -f version=X.Y.Z -f force_confirmation=PROMOTE_NOW
   ```
   *(где X.Y.Z — версия без префикса "v", например, 0.33.2)*
   - Дождаться завершения этого workflow (`gh run list --workflow promote-latest.yml -L 1`). Только после этого релиз полностью готов к скачиванию через `:latest`.
