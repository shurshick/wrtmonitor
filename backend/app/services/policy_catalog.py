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
        "firewall_templates": FIREWALL_TEMPLATES,
        "vpn_templates": VPN_TEMPLATES,
    }


__all__ = ["policy_catalog"]
