# WrtMonitor v0.55.0 - Web Control Center

WebUI системно переработан как самостоятельная современная панель управления OpenWrt. Backend API, авторизация, telemetry и команды агента не менялись.

## Главное

- единая светлая и тёмная Web design system, связанная с Android;
- компактная top bar, глобальный router selector и сворачиваемая desktop sidebar;
- адаптивный drawer и одноколоночная компоновка на tablet/mobile;
- согласованные dashboard, tables, forms, statuses, dialogs и служебные экраны;
- review и видимый этап применения конфигурации без преждевременного success;
- keyboard navigation, skip link, focus-visible и reduced motion;
- локальный набор сетевых иконок без CDN и emoji;
- visual regression на шести размерах от 1920 до 390 px;
- новые Web screenshots и полный отчёт в `docs/web-redesign-0.55.0.md`.

Фиктивные данные и неподдерживаемые операции не добавлены. Runtime OpenWrt не менялся; аппаратное soak evidence Netis NX31 и OpenWrt x86 наследуется по совпадающему fingerprint. Android `versionCode`: `120`.

Все версии до `1.0.0` остаются тестовыми.
