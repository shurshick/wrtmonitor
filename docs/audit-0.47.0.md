# Аудит границ backend 0.47.0

## Закрыто

- `models.py`: 689 строк → совместимый фасад на 57 строк, 25 таблиц сохранены;
- `routes_device.py`: 583 → 266 строк, подготовка контекста вынесена отдельно;
- `routes_commands.py`: 503 → 257 строк, артефакты, backup и preview разделены;
- `client_registry.py`: логика идентичности и присутствия вынесена в отдельные сервисы;
- `hardware_catalog.py`: встроенные профили и отчётность отделены от сопоставления наблюдений;
- CSRF-проверка перенесена из общего route helper в профильный модуль;
- telemetry уже использует предметные normalizer-модули и тонкий публичный фасад.

## Защита от возврата долга

`scripts/validate_architecture.py` проверяет размер фасадов, route-модулей, реестра клиентов, аппаратного каталога и каждого файла `domain_models`. Проверка запускается в CI.

## Совместимость

- URL и API-контракты не менялись;
- импорт моделей через `backend.app.models` сохранён;
- SQLAlchemy metadata по-прежнему содержит 25 исходных таблиц;
- новая Alembic-миграция не требуется;
- Android и TrueNAS-конфигурация функционально не менялись.

## Проверки

- backend и OpenWrt tests: 308 passed, 20 environment skips;
- contract и architecture validators;
- shell syntax и SHA-256 manifest агента;
- Android unit tests, lint и debug APK.
