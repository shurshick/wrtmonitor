# Первый запуск

Текущая опубликованная версия - тестовая 0.55.5. 1.0.0 ещё не выпущена. Нужны Linux/NAS с Docker Compose v2, доступ к root shell OpenWrt и исходящий доступ роутера к серверу. Android 8.0+ устанавливается из подписанного APK GitHub Release.

## 1. Сервер и PostgreSQL

```sh
git clone https://github.com/shurshick/wrtmonitor.git
cd wrtmonitor
git checkout v0.55.5
cp .env.example .env
openssl rand -hex 24
openssl rand -hex 32
```

Первый случайный результат используйте как пароль БД в **обоих** местах `.env`: `POSTGRES_PASSWORD` и password внутри `WRTMONITOR_DATABASE_URL`. Второй - `WRTMONITOR_JWT_SECRET`. Hex не требует URL-encoding. `.env` содержит секреты: `chmod 600 .env`, не добавляйте его в Git и не отправляйте в issue.

Задайте `WRTMONITOR_PUBLIC_SERVER_URL=https://monitor.example.org` и направьте reverse proxy с действительным сертификатом на порт 8088 сервера. Он должен пропускать WebSocket и не буферизовать SSE. Порт PostgreSQL наружу не публикуется.

Для временного LAN-стенда можно вместо этого задать `http://192.168.1.10:8088` и `WRTMONITOR_ALLOW_INSECURE_LOCAL=true`. Этот адрес замените своим; режим не годится для публичного интернета. `WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS` не включайте.

```sh
docker compose up -d --build
docker compose ps
curl -fsS https://monitor.example.org/ready
```

Корневой Compose собирает код выбранного тега; это не `latest` из registry. Для TrueNAS используйте YAML из соответствующего [релиза](https://github.com/shurshick/wrtmonitor/releases/tag/v0.55.5) и [инструкцию deployment](server-deployment.md). После изменения YAML секреты PostgreSQL и URL подключения также должны совпадать.

`/ready` должен вернуть HTTP 200. Если нет: `docker compose logs --tail=100 wrtmonitor postgres`, проверьте пароли, PostgreSQL и reverse proxy. Не публикуйте логи без проверки личных данных.

## 2. Единственный владелец

Откройте тот же адрес с `/setup`, создайте владельца с собственным паролем. Предустановленного admin/password нет. После настройки войдите через `/login`, повторно проверьте `/ready`. Один владелец управляет всеми устройствами этого сервера.

## 3. Первый роутер

На OpenWrt убедитесь, что работает DNS, настроено время/NTP и есть доступ к HTTPS сервера. На странице добавления устройства используйте предлагаемую сервером установку агента. Альтернативный штатный installer:

```sh
cd /tmp
wget -O install-openwrt.sh https://monitor.example.org/downloads/openwrt/install-openwrt.sh &&
  test -s install-openwrt.sh &&
  sh install-openwrt.sh --server 'https://monitor.example.org' \
    --admin-user 'owner@example.org' --name 'HomeRouter'
```

Пароль владельца installer запрашивает интерактивно: не передавайте его в командной строке. `&&` и `test -s` не дадут выполнить пустой файл при ошибке DNS/download. Сценарий ставит зависимости, регистрирует роутер и проверяет первоначальную связь. Не используйте `--clean` для обычного обновления.

```sh
wrtmonitor-agent version
wrtmonitor-agent diagnostics
logread -e wrtmonitor
```

Роутер должен появиться в списке, а после первой telemetry - online с реальными значениями ресурсов. Наличие строки в БД само по себе не означает работоспособный агент. Ошибки: [Troubleshooting](troubleshooting.md).

## 4. Безопасная проверка и Android

На странице роутера в обслуживании запустите диагностику связи. Дождитесь результата в журнале команд и свежей telemetry; это read-only проверка. Не начинайте onboarding с sysupgrade или смены WAN/LAN.

В Web откройте **Аккаунт → Подключить мобильное приложение**, создайте QR. В Android выберите подключение через QR и отсканируйте. QR одноразовый, действует 10 минут; адрес берётся из `WRTMONITOR_PUBLIC_SERVER_URL`, а не из Host proxy. Убедитесь, что Android видит тот же роутер и результат диагностики. Ручной вход остаётся доступен.

## 5. Перед обычной эксплуатацией

Создайте и проверьте резервную копию сервера по [Backup / Restore](server-operations.md), конфигурацию роутера сохраните в обслуживании. Храните копии вне сервера, не публично. Держите LuCI/SSH или физический доступ для аварийного восстановления.

Штатное обновление, миграции и восстановление: [Database Upgrades](database-upgrades.md). Подготовка stable: [Release Checklist](release-checklist-1.0.md).
