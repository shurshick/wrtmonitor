from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models import ClientProfile
from .client_registry import validate_client_policy
from .devices import latest_device_telemetry
from .telemetry_wifi import normalize_wifi_summary


def wifi_access_profile_payload(iface: str, profile: ClientProfile | None) -> dict:
    if profile is None:
        return {"iface": iface, "enabled": False}
    policy = validate_client_policy(profile.policy)
    return {
        "iface": iface,
        "enabled": True,
        "profile_id": str(profile.id),
        "profile_name": profile.name,
        "blocked": policy["blocked"],
        "schedule": policy["schedule"],
        "qos": {
            "download_kbps": policy["qos"]["download_kbps"],
            "upload_kbps": policy["qos"]["upload_kbps"],
        },
    }


def assigned_wifi_interfaces(
    db: Session, device_id: UUID, profile_id: UUID
) -> list[str]:
    telemetry = latest_device_telemetry(db, device_id)
    if telemetry is None or not isinstance(telemetry.payload, dict):
        return []
    wifi = normalize_wifi_summary(telemetry.payload)
    expected = str(profile_id)
    return sorted(
        {
            str(network.get("id") or "")
            for network in wifi.get("networks") or []
            if isinstance(network, dict)
            and isinstance(network.get("access_profile"), dict)
            and str(network["access_profile"].get("profile_id") or "") == expected
            and str(network.get("id") or "")
        }
    )


__all__ = ["assigned_wifi_interfaces", "wifi_access_profile_payload"]
