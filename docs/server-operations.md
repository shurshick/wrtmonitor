# Эксплуатация и восстановление сервера

Документ актуален для `WrtMonitor v0.14.1`.

## Аккаунт владельца

Страница `/account` содержит уведомления, подключение Android одноразовым QR, активные Android/API refresh-сессии, смену пароля владельца, последние 100 записей аудита и PostgreSQL backup.

Access-token Android действует 15 минут. Refresh-token действует до 30 дней, хранится на сервере только как SHA-256 hash и заменяется после каждого успешного обновления. Повторное использование старого token отклоняется. Смена пароля отзывает все refresh-сессии.

Pairing QR действует 10 минут. После использования, истечения или ручного отзыва он не принимается. Создание нового QR автоматически отзывает предыдущий активный код владельца. Мобильная сессия после pairing ничем не отличается по срокам и ротации от обычной refresh-сессии и отзывается отдельно на той же странице.

Релиз `v0.14.0` добавляет миграцию `0007_mobile_pairing`: таблицы одноразовых токенов и попыток, а также тип refresh-сессии. Контейнер применяет её при старте; удалять volume PostgreSQL не требуется.

## Создание backup

Через Web UI нажмите **Сервер -> Резервные копии -> Создать копию**. Архив появляется в постоянном volume `/backups` только после успешной проверки `pg_restore --list`.

То же через контейнер:

```sh
docker compose exec wrtmonitor python -m backend.app.backup_cli create
```

## Проверка восстановления

Команда создаёт временную PostgreSQL БД, восстанавливает архив, проверяет `alembic_version` и таблицу владельца, затем удаляет временную БД:

```sh
docker compose exec wrtmonitor \
  python -m backend.app.backup_cli drill /backups/wrtmonitor-YYYYMMDDTHHMMSSZ.dump
```

Успешный результат начинается с `restore drill: OK`.

## Аварийное восстановление

1. Остановите приложение, оставив PostgreSQL запущенным: `docker compose stop wrtmonitor`.
2. Выполните восстановление:

   ```sh
   docker compose run --rm wrtmonitor \
     python -m backend.app.backup_cli restore \
     /backups/wrtmonitor-YYYYMMDDTHHMMSSZ.dump --confirm
   ```

3. Запустите сервер: `docker compose up -d wrtmonitor`.
4. Проверьте `python -m alembic -c backend/alembic.ini current`, `/health`, вход, список роутеров и тестовую диагностику.

Не удаляйте volumes базы и backup при redeploy.
