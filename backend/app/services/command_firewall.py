from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .command_common import (
    _boolean,
    _integer,
    _ipv4,
    _name,
    _optional_string,
    _require_string,
    _safe_identifier,
    _string_list,
    _uci_section,
)


def _normalize_port_forward_payload(
    payload: dict[str, Any], *, delete: bool = False
) -> dict[str, Any]:
    name = _safe_identifier(
        _require_string(payload, "name", max_length=40), "name", r"[A-Za-z0-9_.-]+"
    )
    section = _uci_section(payload)
    if delete:
        return {"section": section, "name": name}
    protocol = str(payload.get("protocol") or "tcp").lower()
    if protocol not in {"tcp", "udp", "tcpudp"}:
        raise HTTPException(
            status_code=400, detail="Protocol must be tcp, udp or tcpudp"
        )
    return {
        "section": section,
        "name": name,
        "protocol": protocol,
        "external_port": _integer(payload, "external_port", 1, 65535),
        "internal_ip": _ipv4(payload, "internal_ip"),
        "internal_port": _integer(payload, "internal_port", 1, 65535),
    }


def _normalize_redirect_payload(
    payload: dict[str, Any], *, delete: bool = False
) -> dict[str, Any]:
    section = _uci_section(payload)
    name = _name(payload)
    if delete:
        if not section:
            raise HTTPException(status_code=400, detail="Redirect section is required")
        return {"section": section, "name": name}
    protocol = str(payload.get("protocol") or "tcp").lower()
    if protocol not in {"tcp", "udp", "tcpudp", "all"}:
        raise HTTPException(status_code=400, detail="Invalid redirect protocol")
    target = str(payload.get("target") or "DNAT").upper()
    if target not in {"DNAT", "SNAT"}:
        raise HTTPException(status_code=400, detail="Invalid redirect target")
    result: dict[str, Any] = {
        "section": section,
        "name": name,
        "enabled": _boolean(payload, "enabled", default=True),
        "src": _optional_string(payload, "src") or "wan",
        "dest": _optional_string(payload, "dest") or "lan",
        "protocol": protocol,
        "src_ip": _optional_string(payload, "src_ip") or "",
        "src_port": _optional_string(payload, "src_port") or "",
        "dest_ip": _optional_string(payload, "dest_ip") or "",
        "dest_port": _optional_string(payload, "dest_port") or "",
        "target": target,
    }
    if target == "DNAT" and not result["dest_ip"]:
        raise HTTPException(
            status_code=400, detail="DNAT destination address is required"
        )
    return result


def _normalize_zone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def policy(key: str) -> str:
        return _safe_identifier(
            str(payload.get(key) or "REJECT").upper(),
            key,
            r"(?:ACCEPT|REJECT|DROP)",
        )

    return {
        "section": _uci_section(payload),
        "name": _name(payload),
        "networks": [
            _safe_identifier(v, "networks", r"[A-Za-z0-9_.-]+")
            for v in _string_list(payload, "networks", required=True)
        ],
        "input": policy("input"),
        "output": policy("output"),
        "forward": policy("forward"),
        "masquerade": _boolean(payload, "masquerade", default=False),
    }


def _normalize_forwarding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": _uci_section(payload),
        "src": _name(payload, "src"),
        "dest": _name(payload, "dest"),
        "enabled": _boolean(payload, "enabled"),
    }


def _normalize_firewall_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    protocol = str(payload.get("protocol") or "tcpudp").lower()
    if protocol not in {"tcp", "udp", "tcpudp", "icmp", "all"}:
        raise HTTPException(status_code=400, detail="Invalid firewall protocol")
    target = str(payload.get("target") or "ACCEPT").upper()
    if target not in {"ACCEPT", "REJECT", "DROP"}:
        raise HTTPException(status_code=400, detail="Invalid firewall target")
    return {
        "section": _uci_section(payload),
        "name": _name(payload),
        "src": _optional_string(payload, "src") or "*",
        "dest": _optional_string(payload, "dest") or "*",
        "protocol": protocol,
        "src_ip": _optional_string(payload, "src_ip") or "",
        "dest_ip": _optional_string(payload, "dest_ip") or "",
        "src_port": _optional_string(payload, "src_port") or "",
        "dest_port": _optional_string(payload, "dest_port") or "",
        "target": target,
    }


__all__ = [
    "_normalize_port_forward_payload",
    "_normalize_redirect_payload",
    "_normalize_zone_payload",
    "_normalize_forwarding_payload",
    "_normalize_firewall_rule_payload",
]
