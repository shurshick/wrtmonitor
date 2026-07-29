from __future__ import annotations

from typing import Any


def normalize_vpn_summary(payload: dict[str, Any]) -> dict[str, Any]:
    vpn = payload.get("vpn") or {}
    wireguard = vpn.get("wireguard") or {}
    interfaces: list[dict[str, Any]] = []
    for interface in wireguard.get("interfaces") or []:
        if not isinstance(interface, dict):
            continue
        peers = [
            peer for peer in interface.get("peers") or [] if isinstance(peer, dict)
        ]
        interfaces.append(
            {
                "name": interface.get("name"),
                "section": interface.get("section") or interface.get("name"),
                "configured": bool(interface.get("configured", False)),
                "enabled": bool(interface.get("enabled", False)),
                "runtime": bool(interface.get("runtime", False)),
                "addresses": interface.get("addresses") or [],
                "public_key": interface.get("public_key"),
                "listen_port": interface.get("listen_port"),
                "peers": peers,
                "peer_count": len(peers),
                "rx_bytes": sum(int(peer.get("rx_bytes") or 0) for peer in peers),
                "tx_bytes": sum(int(peer.get("tx_bytes") or 0) for peer in peers),
            }
        )
    openvpn = vpn.get("openvpn") or {}
    policy = vpn.get("policy") or {}
    return {
        "wireguard": {"interfaces": interfaces},
        "openvpn": {
            "service": openvpn.get("service") or "unavailable",
            "clients": openvpn.get("clients") or [],
        },
        "policy": {
            "service": policy.get("service") or "unavailable",
            "policies": policy.get("policies") or [],
        },
    }


__all__ = ["normalize_vpn_summary"]
