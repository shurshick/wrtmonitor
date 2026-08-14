from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..services.audit import audit
from ..services.auth import settings, web_user_from_session
from ..services.command_common import ALLOWED_COMMANDS
from ..services.command_store import create_device_command, validate_command_request
from ..services.command_web_payloads import build_command_payload_from_web_form
from ..services.config_transactions import ensure_preflight_valid
from ..services.devices import (
    device_supports,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..services.setup import is_setup_required
from .csrf import require_web_csrf
from .route_shared import DEVICE_SECTIONS
from .routes_command_artifacts import (
    download_command_artifact,
    router as artifacts_router,
    web_wifi_qr,
)
from .routes_command_backup import (
    router as backup_router,
    web_restore_router_backup,
)
from .routes_command_preview import (
    router as preview_router,
    web_device_command_preview,
)

router = APIRouter()


@router.post("/devices/{device_id}/web-command")
def web_device_command(
    device_id: UUID,
    section: str = "overview",
    command_type: str = Form(...),
    ssid: str = Form(default=""),
    enabled: str = Form(default="true"),
    wifi_password: str = Form(default=""),
    channel: str = Form(default=""),
    country: str = Form(default=""),
    interval_seconds: str = Form(default=""),
    radio: str = Form(default=""),
    iface: str = Form(default=""),
    interface: str = Form(default=""),
    hostname: str = Form(default=""),
    service: str = Form(default=""),
    mac: str = Form(default=""),
    ip: str = Form(default=""),
    protocol: str = Form(default=""),
    ip_address: str = Form(default=""),
    netmask: str = Form(default=""),
    gateway: str = Form(default=""),
    dns: str = Form(default=""),
    username: str = Form(default=""),
    password: str = Form(default=""),
    mtu: str = Form(default=""),
    start: str = Form(default=""),
    limit: str = Form(default=""),
    leasetime: str = Form(default=""),
    servers: str = Form(default=""),
    name: str = Form(default=""),
    external_port: str = Form(default=""),
    internal_ip: str = Form(default=""),
    internal_port: str = Form(default=""),
    blocked: str = Form(default="true"),
    zonename: str = Form(default=""),
    timezone: str = Form(default=""),
    download_kbps: str = Form(default=""),
    upload_kbps: str = Form(default=""),
    htmode: str = Form(default=""),
    txpower: str = Form(default=""),
    network: str = Form(default=""),
    encryption: str = Form(default=""),
    hidden: str = Form(default="false"),
    isolate: str = Form(default="false"),
    ieee80211r: str = Form(default="false"),
    ieee80211k: str = Form(default="false"),
    bss_transition: str = Form(default="false"),
    mobility_domain: str = Form(default=""),
    weekdays: list[str] = Form(default=[]),
    stop: str = Form(default=""),
    mesh_id: str = Form(default=""),
    public_key: str = Form(default=""),
    preshared_key: str = Form(default=""),
    allowed_ips: str = Form(default=""),
    endpoint: str = Form(default=""),
    config_text: str = Form(default=""),
    source: str = Form(default=""),
    destination: str = Form(default=""),
    url: str = Form(default=""),
    sha256: str = Form(default=""),
    archive_base64: str = Form(default=""),
    content: str = Form(default=""),
    pid: str = Form(default=""),
    signal: str = Form(default=""),
    uci_section: str = Form(default=""),
    ports: str = Form(default=""),
    bridge: str = Form(default="false"),
    stp: str = Form(default="false"),
    igmp_snooping: str = Form(default="true"),
    dhcp_enabled: str = Form(default="false"),
    dhcp_start: str = Form(default=""),
    dhcp_limit: str = Form(default=""),
    dhcp_leasetime: str = Form(default=""),
    policy: str = Form(default="guest"),
    vlan_id: str = Form(default=""),
    track_ips: str = Form(default=""),
    check_interval: str = Form(default=""),
    failure_interval: str = Form(default=""),
    recovery_interval: str = Form(default=""),
    confirmed: bool = Form(default=False),
    diagnostics_checks: list[str] = Form(default=[]),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    if command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Unsupported command or device")
    try:
        raw_payload = build_command_payload_from_web_form(
            command_type,
            ssid=ssid,
            enabled=enabled,
            wifi_password=wifi_password,
            channel=channel,
            country=country,
            interval_seconds=interval_seconds,
            radio=radio,
            iface=iface,
            interface=interface,
            hostname=hostname,
            service=service,
            mac=mac,
            ip=ip,
            protocol=protocol,
            ip_address=ip_address,
            netmask=netmask,
            gateway=gateway,
            dns=dns,
            username=username,
            password=password,
            mtu=mtu,
            start=start,
            limit=limit,
            leasetime=leasetime,
            servers=servers,
            name=name,
            external_port=external_port,
            internal_ip=internal_ip,
            internal_port=internal_port,
            blocked=blocked,
            zonename=zonename,
            timezone=timezone,
            download_kbps=download_kbps,
            upload_kbps=upload_kbps,
            htmode=htmode,
            txpower=txpower,
            network=network,
            encryption=encryption,
            hidden=hidden,
            isolate=isolate,
            ieee80211r=ieee80211r,
            ieee80211k=ieee80211k,
            bss_transition=bss_transition,
            mobility_domain=mobility_domain,
            weekdays=weekdays,
            stop=stop,
            mesh_id=mesh_id,
            public_key=public_key,
            preshared_key=preshared_key,
            allowed_ips=allowed_ips,
            endpoint=endpoint,
            config_text=config_text,
            source=source,
            destination=destination,
            url=url,
            sha256=sha256,
            archive_base64=archive_base64,
            content=content,
            pid=pid,
            signal=signal,
            uci_section=uci_section,
            ports=ports,
            bridge=bridge,
            stp=stp,
            igmp_snooping=igmp_snooping,
            dhcp_enabled=dhcp_enabled,
            dhcp_start=dhcp_start,
            dhcp_limit=dhcp_limit,
            dhcp_leasetime=dhcp_leasetime,
            policy=policy,
            vlan_id=vlan_id,
            track_ips=track_ips,
            check_interval=check_interval,
            failure_interval=failure_interval,
            recovery_interval=recovery_interval,
            diagnostics_checks=diagnostics_checks,
        )
        payload = validate_command_request(
            command_type=command_type,
            payload=raw_payload,
            confirmed=confirmed,
            device_supports=lambda capability: device_supports(
                db, device_id, capability
            ),
        )
        telemetry = latest_device_telemetry(db, device_id)
        ensure_preflight_valid(
            command_type,
            payload,
            telemetry.payload if telemetry else {},
        )
    except (ValueError, HTTPException) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    command = create_device_command(
        db,
        device_id=device_id,
        command_type=command_type,
        payload=payload,
        created_by=user.id,
        source="web",
    )
    audit(
        db,
        user.id,
        "command.create",
        "device_command",
        str(command.id),
        {"command_type": command_type, "source": "web", "confirmed": confirmed},
    )
    db.commit()
    section = section if section in DEVICE_SECTIONS else "overview"
    return RedirectResponse(f"/devices/{device_id}?section={section}", status_code=303)


router.include_router(artifacts_router)
router.include_router(backup_router)
router.include_router(preview_router)


__all__ = [
    "router",
    "download_command_artifact",
    "web_device_command",
    "web_restore_router_backup",
    "web_device_command_preview",
    "web_wifi_qr",
]
