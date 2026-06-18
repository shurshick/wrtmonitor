# TrueNAS Custom App

Подробная инструкция по серверной части находится здесь:

- [Развёртывание серверной части](server-deployment.md)

Коротко:

1. Скачайте `wrtmonitor-truenas-0.1.0-test.3.yaml` из релиза.
2. Создайте TrueNAS Custom App из YAML.
3. Задайте `WRTMONITOR_PUBLIC_SERVER_URL=https://ваш-домен`, `WRTMONITOR_JWT_SECRET`, `POSTGRES_PASSWORD`.
4. Настройте Nginx Proxy Manager на внутренний адрес `http://truenas-ip:8088`.
5. Откройте внешний адрес `https://ваш-домен/setup` и создайте первого администратора.

Если TrueNAS публикует приложение через reverse proxy, в `WRTMONITOR_PUBLIC_SERVER_URL` указывайте внешний HTTPS-адрес, доступный Android-приложению и OpenWrt-роутерам.
