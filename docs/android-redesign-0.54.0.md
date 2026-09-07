# Android redesign 0.54.0

## Аудит до изменений

Приложение уже использовало Compose Material 3, Repository/ViewModel/DTO и безопасный command lifecycle. Реализованы onboarding, QR pairing, список и обзор роутеров, клиенты, Wi-Fi, WAN/LAN, firewall, VPN, system, hardware, maintenance, events и настройки.

Основные проблемы были в UI-слое:

- палитры, формы и тема находились в `WrtMonitorApp.kt`;
- повторялись локальные размеры и визуальные решения;
- кнопки имели высоту 34 dp и слишком маленькую область касания;
- loading/error/empty отображались по-разному;
- статусы часто различались только цветом;
- edge-to-edge не управлял цветом системных иконок после смены темы;
- на широком экране сохранялась телефонная нижняя навигация;
- «Настройки» и «О приложении» создавали два конкурирующих уровня возврата;
- светлая onboarding-тема не закрашивала тёмный фон окна.

Placeholder telemetry и фиктивные метрики в Android не найдены. `placeholder` используется только как подсказка полей ввода. История трафика не строится без данных backend.

## Изменения

- Введены `WrtMonitorTheme`, `WrtSpacing`, `WrtSizes`, `WrtMotion` и `WrtStatus`.
- Палитры получили tonal surface hierarchy и отдельные semantic colors для normal, warning и critical.
- Переработаны `SectionCard`, `ExpandableSettingsCard`, `MetricTile`, `DestinationRow`, кнопки и status badge.
- Добавлены `WrtRouterStatusPanel`, `WrtLoadingState`, `WrtEmptyState`, `WrtErrorState` и `WrtOfflineState`.
- Оболочка использует safe drawing insets, ограничение ширины контента, нижнюю навигацию на телефоне и Navigation Rail от 720 dp.
- Заголовок выбранного роутера стал компактным переключателем с понятной областью нажатия.
- Исправлены системные status/navigation bars при ручной смене темы.
- Onboarding и QR scanner учитывают safe drawing и IME.
- Экран роутеров и обзор переведены на общие состояния и семантику.
- Убрана конкурирующая верхняя стрелка в настройках; системная кнопка «Назад» сохраняет иерархию.
- Минимальная область касания кнопок увеличена до 48 dp.

## Что не менялось

API-контракты, команды, DTO, Repository, ViewModel, сервер и агент функционально не менялись. Private keys, пароли и токены в UI не выводятся. Raw shell и обход backend validation не добавлялись.

Web SSH остаётся только в Web UI. Android не показывает эту операцию согласно `contracts/surface-exclusions.json`. Показатели и формы, для которых роутер не объявляет capability, не выдумываются.

## Проверка

- Android 15 emulator, API 35;
- чистая установка и ручной вход;
- живой список роутеров и telemetry Netis NX31;
- overview, clients, Wi-Fi, settings и about;
- RU и EN resources;
- light/dark и переключение без перезапуска;
- portrait, landscape и широкая конфигурация;
- системные insets и экранная клавиатура;
- APK install/launch;
- unit tests, lint и instrumented tests выполняются release pipeline.

Скриншоты находятся в `docs/images/android/`. Они сняты с собранного APK, подключённого к тестовому WrtMonitor Server, а не нарисованы отдельно.

## Ручная проверка после установки релиза

На физическом Android-устройстве остаётся проверить TalkBack с OEM-шрифтом, foldable posture и установку release APK поверх предыдущего production-signed APK. Изменения конфигурации роутера не повторялись в рамках визуального редизайна: они используют прежний сертифицированный command lifecycle.
