from __future__ import annotations

from typing import Any


SQM_PROFILES: list[dict[str, Any]] = [
    {
        "id": "balanced",
        "label": "Сбалансированный",
        "description": "CAKE с компенсацией bufferbloat для обычной домашней сети.",
        "qdisc": "cake",
        "script": "piece_of_cake.qos",
        "overhead": 0,
    },
    {
        "id": "gaming",
        "label": "Игры и звонки",
        "description": "Минимальная задержка и разделение потоков DiffServ4.",
        "qdisc": "cake",
        "script": "layer_cake.qos",
        "qdisc_options": "diffserv4 dual-srchost nat",
    },
    {
        "id": "streaming",
        "label": "Видео и загрузки",
        "description": "Справедливое распределение полосы между устройствами.",
        "qdisc": "cake",
        "script": "layer_cake.qos",
        "qdisc_options": "diffserv3 dual-srchost nat",
    },
]

DNS_POLICY_PRESETS: list[dict[str, Any]] = [
    {
        "id": "none",
        "label": "Без фильтрации",
        "provider": "none",
        "categories": [],
    },
    {
        "id": "security",
        "label": "Защита от вредоносных сайтов",
        "provider": "cloudflare-security",
        "categories": ["malware", "phishing"],
    },
    {
        "id": "family",
        "label": "Семейный фильтр",
        "provider": "cloudflare-family",
        "categories": ["malware", "phishing", "adult"],
    },
]

CLIENT_SPEED_OPTIONS: list[dict[str, Any]] = [
    {"value": 0, "label": "Без ограничения", "label_en": "Unlimited"},
    *[
        {
            "value": megabits * 1000,
            "label": f"{megabits} Мбит/с",
            "label_en": f"{megabits} Mbps",
        }
        for megabits in (1, 5, 10, 25, 50, 100, 250, 500, 1000)
    ],
]

CLIENT_POLICY_PRESETS: list[dict[str, Any]] = [
    {
        "id": "unrestricted",
        "label": "Без ограничений",
        "label_en": "Unrestricted",
        "description": "Постоянный доступ без фильтрации и ограничения скорости.",
        "description_en": "Always allowed without filtering or speed limits.",
        "policy": {
            "blocked": False,
            "schedule": {"enabled": False, "weekdays": [], "start": "", "stop": ""},
            "qos": {"priority": "normal", "download_kbps": 0, "upload_kbps": 0},
            "dns": {"provider": "none", "blocked_domains": []},
        },
    },
    {
        "id": "child",
        "label": "Ребёнок",
        "label_en": "Child",
        "description": "Доступ ежедневно с 07:00 до 22:00 и семейный DNS-фильтр.",
        "description_en": "Daily access from 07:00 to 22:00 with family DNS filtering.",
        "policy": {
            "blocked": False,
            "schedule": {
                "enabled": True,
                "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start": "07:00",
                "stop": "22:00",
            },
            "qos": {"priority": "normal", "download_kbps": 0, "upload_kbps": 0},
            "dns": {"provider": "cloudflare-family", "blocked_domains": []},
        },
    },
    {
        "id": "guest",
        "requires_shaping": True,
        "label": "Гость",
        "label_en": "Guest",
        "description": "Защищённый DNS и лимиты 25/10 Мбит/с.",
        "description_en": "Security DNS with 25/10 Mbps limits.",
        "policy": {
            "blocked": False,
            "schedule": {"enabled": False, "weekdays": [], "start": "", "stop": ""},
            "qos": {"priority": "low", "download_kbps": 25000, "upload_kbps": 10000},
            "dns": {"provider": "cloudflare-security", "blocked_domains": []},
        },
    },
    {
        "id": "iot",
        "requires_shaping": True,
        "label": "Умное устройство",
        "label_en": "IoT device",
        "description": "Низкий приоритет, защищённый DNS и лимиты 10/5 Мбит/с.",
        "description_en": "Low priority, security DNS and 10/5 Mbps limits.",
        "policy": {
            "blocked": False,
            "schedule": {"enabled": False, "weekdays": [], "start": "", "stop": ""},
            "qos": {"priority": "low", "download_kbps": 10000, "upload_kbps": 5000},
            "dns": {"provider": "cloudflare-security", "blocked_domains": []},
        },
    },
]

FIREWALL_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "allow-dns-lan",
        "label": "Разрешить DNS из LAN",
        "command": "firewall.set_rule",
        "payload": {
            "name": "Allow-DNS-LAN",
            "src": "lan",
            "dest": "*",
            "protocol": "tcpudp",
            "dest_port": "53",
            "target": "ACCEPT",
        },
    },
    {
        "id": "block-device-wan",
        "label": "Запретить устройству выход в WAN",
        "command": "client.set_blocked",
        "payload": {"blocked": True},
    },
]

VPN_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "wireguard-full-tunnel",
        "label": "WireGuard: весь трафик",
        "allowed_ips": ["0.0.0.0/0", "::/0"],
        "route_allowed_ips": True,
    },
    {
        "id": "wireguard-remote-lan",
        "label": "WireGuard: доступ к домашней сети",
        "allowed_ips": ["192.168.0.0/16"],
        "route_allowed_ips": False,
    },
]


def policy_catalog() -> dict[str, Any]:
    return {
        "sqm_profiles": SQM_PROFILES,
        "dns_policy_presets": DNS_POLICY_PRESETS,
        "client_policy_presets": CLIENT_POLICY_PRESETS,
        "client_speed_options": CLIENT_SPEED_OPTIONS,
        "firewall_templates": FIREWALL_TEMPLATES,
        "vpn_templates": VPN_TEMPLATES,
    }


__all__ = ["policy_catalog"]
