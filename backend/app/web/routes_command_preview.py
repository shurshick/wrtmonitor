from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..services.auth import settings, web_user_from_session
from ..services.command_web_payloads import build_command_payload_from_web_form
from ..services.command_store import validate_command_request
from ..services.config_transactions import build_command_preview
from ..services.devices import (
    device_supports,
    get_user_device_or_404,
    latest_device_telemetry,
)
from .csrf import require_web_csrf

router = APIRouter()


@router.post("/devices/{device_id}/web-command-preview")
async def web_device_command_preview(
    request: Request,
    device_id: UUID,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> JSONResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    form = await request.form()
    require_web_csrf(wrtmonitor_session, str(form.get("csrf_token") or ""), config)
    get_user_device_or_404(db, user, device_id)

    def value(name: str, default: str = "") -> str:
        return str(form.get(name) or default)

    command_type = value("command_type")
    try:
        payload = build_command_payload_from_web_form(
            command_type,
            ssid=value("ssid"),
            enabled=value("enabled", "true"),
            wifi_password=value("wifi_password"),
            channel=value("channel"),
            country=value("country"),
            interval_seconds=value("interval_seconds"),
            radio=value("radio"),
            iface=value("iface"),
            interface=value("interface"),
            hostname=value("hostname"),
            service=value("service"),
            mac=value("mac"),
            ip=value("ip"),
            protocol=value("protocol"),
            ip_address=value("ip_address"),
            netmask=value("netmask"),
            gateway=value("gateway"),
            dns=value("dns"),
            username=value("username"),
            password=value("password"),
            mtu=value("mtu"),
            start=value("start"),
            limit=value("limit"),
            leasetime=value("leasetime"),
            servers=value("servers"),
            name=value("name"),
            external_port=value("external_port"),
            internal_ip=value("internal_ip"),
            internal_port=value("internal_port"),
            blocked=value("blocked", "true"),
            zonename=value("zonename"),
            timezone=value("timezone"),
            download_kbps=value("download_kbps"),
            upload_kbps=value("upload_kbps"),
            htmode=value("htmode"),
            txpower=value("txpower"),
            network=value("network"),
            encryption=value("encryption"),
            hidden=value("hidden", "false"),
            isolate=value("isolate", "false"),
            ieee80211r=value("ieee80211r", "false"),
            ieee80211k=value("ieee80211k", "false"),
            bss_transition=value("bss_transition", "false"),
            mobility_domain=value("mobility_domain"),
            weekdays=[str(item) for item in form.getlist("weekdays")],
            stop=value("stop"),
            mesh_id=value("mesh_id"),
            public_key=value("public_key"),
            preshared_key=value("preshared_key"),
            allowed_ips=value("allowed_ips"),
            endpoint=value("endpoint"),
            config_text=value("config_text"),
            source=value("source"),
            destination=value("destination"),
            url=value("url"),
            sha256=value("sha256"),
            archive_base64=value("archive_base64"),
            content=value("content"),
            pid=value("pid"),
            signal=value("signal"),
            uci_section=value("uci_section"),
            diagnostics_checks=[
                str(item) for item in form.getlist("diagnostics_checks")
            ],
        )
        payload = validate_command_request(
            command_type=command_type,
            payload=payload,
            confirmed=True,
            device_supports=lambda capability: device_supports(
                db, device_id, capability
            ),
        )
        telemetry = latest_device_telemetry(db, device_id)
        preview = build_command_preview(
            command_type, payload, telemetry.payload if telemetry else {}
        )
    except (ValueError, HTTPException) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return JSONResponse({"detail": detail}, status_code=400)
    return JSONResponse(preview)


__all__ = ["router", "web_device_command_preview"]
