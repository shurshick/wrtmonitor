# v0.1.0-test.17 — Web UI CSP hotfix

- Исправлен сломанный внешний вид Web UI в `test.16`: строгая CSP блокировала inline CSS.
- Стили вынесены в локальный `/static/app.css`, который разрешён действующей CSP.
- CSP остаётся строгой: не добавлены `unsafe-inline` и внешние источники.
- Android: `versionName 0.1.0-test.17`, `versionCode 17`.
