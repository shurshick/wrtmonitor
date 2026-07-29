# v0.25.0-core-certification

Тестовый стабилизационный релиз фиксирует исполнимый контракт 90 команд.

## Изменения

- для каждой команды опубликована матрица Web, Android, API, agent, capability, риска, timeout, post-condition и rollback;
- неизвестный post-condition verifier теперь завершает команду ошибкой, а не ложным успехом;
- проверки конфигурации после записи, состояния пакетов, служб и агента разделены явно;
- генерация и Ed25519-подпись agent manifest выполняются один раз и используются Docker-образом и GitHub Release;
- публикация Release ждёт успешные backend, Android, Docker и agent metadata jobs;
- инструкции очищены от устаревших ссылок на версии и отделяют CI-проверку от испытания на физическом роутере.

## Проверка

- backend и OpenWrt static tests;
- Linux OpenWrt command harness;
- Android unit, lint и build;
- PostgreSQL E2E в CI;
- физический Netis NX31 требует отдельного заполненного certification report и не подменяется CI.
