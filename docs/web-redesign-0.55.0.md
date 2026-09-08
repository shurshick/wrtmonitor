# Web Control Center 0.55.0

## Аудит исходного интерфейса

WebUI построен на серверных Jinja-шаблонах FastAPI, обычном CSS и небольших независимых JavaScript-модулях. Routing, авторизация и состояние принадлежат backend; отдельного SPA state manager и дублирующего API client нет. Эта архитектура подходит проекту, поэтому новый framework не добавлялся.

До редизайна рабочие экраны уже покрывали telemetry, clients, network, Wi-Fi, firewall, VPN, system, maintenance, packages, firmware, backup, diagnostics и Web SSH. Главные проблемы были в другом: цвета и интервалы задавались в нескольких местах, верхняя панель не отражала контекст роутера, desktop-навигация не сворачивалась, промежуточные размеры экрана жили по разным правилам, а review закрывался до начала применения. Отдельно найден и исправлен синтаксически сломанный шаблон `/fleet`.

## Новая система

Центральный файл `backend/app/static/css/tokens.css` задаёт семантические цвета, уровни surfaces, типографику, интервалы, радиусы, высоты controls и table rows, motion и размеры shell. Тёмная и светлая темы используют одни и те же роли: primary, secondary, info, success, warning, error, online и offline.

`web-redesign.css` формирует единый визуальный слой для dashboard, таблиц, форм, статусов, dialogs, empty/error блоков и служебных экранов. Случайные page-level цвета в новом слое не используются. Иконки локально встроены в `icons.svg`; внешний CDN не требуется.

## Навигация и responsive

- Desktop: постоянная боковая панель с icon + label, выбранным состоянием и сохранением свёрнутого режима.
- Narrow desktop и tablet: компактная панель, затем drawer с затемнением содержимого.
- Mobile web: одноколоночный layout, drawer, сокращённая top bar и формы без горизонтального выхода.
- Глобальный selector показывает текущий роутер и загружает доступные роутеры через существующую защищённую Web-сессию. Добавлен поиск, новый backend endpoint не понадобился.

Проверяемые ширины: 1920x1080, 1440x900, 1366x768, 1024x768, 768x900 и 390x844.

## Безопасное управление

Существующий поток `validate -> review -> apply -> verify` сохранён. Dialog больше не закрывается сразу после Apply: он показывает завершённую проверку и активный этап применения/резервной точки до перехода к результату. Для изменённых форм появляется общая панель несохранённых изменений с действиями Reset и Review/Apply. Успех не показывается до ответа существующего post-condition verifier.

## Accessibility

Добавлены skip link, семантические navigation landmarks, `aria-expanded`, live region для состояния shell, Escape для закрытия drawer/popover, единый `focus-visible`, область управления не меньше 36 px на desktop и reduced-motion режим. Sidebar, selector, theme и формы доступны с клавиатуры. Статусы не зависят только от цвета.

## Что не выдумывалось

Редизайн не добавляет фиктивную историю, packet loss, signal/noise, firmware availability и другие показатели, которых нет в текущем контракте. Private keys, пароли и tokens не выводятся. API, telemetry, auth и команды агента не изменены.

## Проверки

- 341 backend/OpenWrt tests: passed; 22 hardware-only tests: skipped локально.
- Jinja parse, JavaScript syntax, XML icon sprite и release metadata: passed.
- GitHub browser smoke проходит все разделы, dark/light theme, router selector, configuration review, package lists, Web SSH и отсутствие horizontal overflow на шести viewport.
- Android, deployment acceptance, container build и security scans остаются обязательными release gates.

Операции с реальным OpenWrt не менялись. Физически перепроверять 95 команд только из-за presentation-only релиза не требуется; действующее soak evidence Netis NX31 и OpenWrt x86 наследуется по неизменному runtime fingerprint.
