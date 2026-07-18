# TrueNAS Custom App

## Образ

TrueNAS использует образ:

```text
ghcr.io/shurshick/wrtmonitor:latest
```

Это стабильная ссылка на текущую тестовую сборку проекта.

## Что важно про `latest`

- `latest` не обновляет уже работающий контейнер автоматически;
- новый образ скачивается при redeploy;
- в TrueNAS это делается через **Edit -> Save**;
- PostgreSQL volume удалять нельзя, иначе потеряются пользователи, роутеры и история telemetry.
- `WRTMONITOR_TELEMETRY_METRIC_RETENTION_DAYS` задаёт срок хранения компактных метрик графиков; по умолчанию 45 дней.

## Обновление до нового релиза

1. Откройте App в TrueNAS.
2. Нажмите **Edit**.
3. Убедитесь, что image это `ghcr.io/shurshick/wrtmonitor:latest`.
4. Нажмите **Save**.
5. Дождитесь статуса `Running`.
6. Проверьте:

```text
/health
/health/config
/downloads/openwrt/agent-version.txt
/downloads/openwrt/SHA256SUMS.txt
```

## Что должно раздаваться после обновления

Сервер обязан отдавать:

- `/downloads/openwrt/wrtmonitor-agent`
- `/downloads/openwrt/wrtmonitor.init`
- `/downloads/openwrt/install-openwrt.sh`
- `/downloads/openwrt/agent-version.txt`
- `/downloads/openwrt/SHA256SUMS.txt`

Это важно для безопасного auto-update OpenWrt agent.
