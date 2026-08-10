from fastapi import APIRouter
from .route_shared import (
    APP_VERSION,
    ClientProfile,
    Cookie,
    DEVICE_SECTIONS,
    Depends,
    DeviceCommand,
    HTMLResponse,
    HTTPException,
    JSONResponse,
    NETMASK_OPTIONS,
    NetworkClient,
    Query,
    RedirectResponse,
    Request,
    Session,
    Settings,
    TIMEZONE_OPTIONS,
    UTC,
    UUID,
    WIFI_CHANNELS,
    WIFI_COUNTRIES,
    capabilities_hint,
    capability_summary,
    cleanup_device_command_history,
    client_response,
    command_history_entry,
    datetime,
    device_telemetry_history,
    format_timestamp,
    func,
    generate_csrf_token,
    get_db,
    get_user_device_or_404,
    grouped_capabilities,
    is_setup_required,
    json,
    latest_device_telemetry,
    normalize_clients_summary,
    normalize_maintenance_summary,
    normalize_network_summary,
    normalize_services_summary,
    normalize_system_summary,
    normalize_vpn_summary,
    normalize_wifi_summary,
    percent,
    select,
    settings,
    telemetry_alerts,
    templates,
    web_user_from_session,
)
from ..models import AuditLog
from ..services.firmware_catalog import firmware_catalog
from ..services.hardware_catalog import hardware_report, hardware_summary
from ..services.health_monitoring import build_health_snapshot
from ..services.policy_catalog import policy_catalog

router = APIRouter()


@router.get("/devices/{device_id}", response_class=HTMLResponse)
def device_page(
    request: Request,
    device_id: UUID,
    section: str = "overview",
    command_page: int = 1,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        from urllib.parse import quote

        next_url = quote(
            str(request.url.path)
            + ("?" + str(request.url.query) if request.url.query else ""),
            safe="",
        )
        return RedirectResponse(f"/login?next={next_url}", status_code=303)
    device = get_user_device_or_404(db, user, device_id)
    section = section if section in DEVICE_SECTIONS else "overview"
    csrf_token = generate_csrf_token(wrtmonitor_session or "", config.jwt_secret)
    telemetry = latest_device_telemetry(db, device_id)
    payload = telemetry.payload if telemetry else {}
    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    cpu = payload.get("cpu") or {}
    storage = payload.get("storage") or {}
    thermal = payload.get("thermal") or {}
    traffic = payload.get("traffic") or {}
    processes = system.get("processes") or {}
    board = payload.get("board") or {}
    wifi = normalize_wifi_summary(payload)
    agent = dict(payload.get("agent") or {})
    network = normalize_network_summary(payload)
    vpn = normalize_vpn_summary(payload)
    telemetry_clients = normalize_clients_summary(payload)
    maintenance = normalize_maintenance_summary(payload)
    dhcp_config = (
        payload.get("dhcp") or (payload.get("clients") or {}).get("dhcp") or {}
    )
    registry_clients = db.scalars(
        select(NetworkClient)
        .where(NetworkClient.device_id == device_id)
        .order_by(NetworkClient.online.desc(), NetworkClient.last_seen_at.desc())
    ).all()
    clients = [client_response(db, item) for item in registry_clients]
    presence_rank = {"online": 0, "recent": 1, "offline": 2}
    clients.sort(
        key=lambda item: (
            presence_rank.get(str(item.get("presence_state")), 3),
            str(item.get("display_name") or item.get("hostname") or item.get("mac")),
        )
    )
    online_client_count = sum(1 for item in clients if item.get("online"))
    recent_client_count = sum(
        1 for item in clients if item.get("presence_state") == "recent"
    )
    lease_ipv4_by_mac = {
        str(item.get("mac") or "").lower(): str(item.get("ip") or "")
        for item in dhcp_config.get("leases") or []
        if isinstance(item, dict) and "." in str(item.get("ip") or "")
    }
    static_ipv4_by_mac = {
        str(item.get("mac") or "").lower(): str(item.get("ip") or "")
        for item in dhcp_config.get("static_leases") or []
        if isinstance(item, dict) and "." in str(item.get("ip") or "")
    }
    for client in clients:
        mac_key = str(client.get("mac") or "").lower()
        registry_address = str(client.get("ip_address") or "")
        client["current_ipv4"] = (
            lease_ipv4_by_mac.get(mac_key)
            or static_ipv4_by_mac.get(mac_key)
            or (registry_address if "." in registry_address else "")
        )
        client["static_ipv4"] = static_ipv4_by_mac.get(mac_key) or ""
    client_profiles = db.scalars(
        select(ClientProfile)
        .where(ClientProfile.device_id == device_id)
        .order_by(ClientProfile.name)
    ).all()
    system_summary = normalize_system_summary(payload)
    services = normalize_services_summary(payload)
    network_devices = payload.get("network_devices") or {}
    radios = wifi.get("radios") or []
    interfaces = network.get("interfaces") or []
    lan_interface = next(
        (item for item in interfaces if item.get("interface") == "lan"), {}
    )
    wan_interface = next(
        (item for item in interfaces if item.get("interface") == "wan"), {}
    )
    interface_options = sorted(
        {
            str(value)
            for item in interfaces
            for value in (item.get("interface"), item.get("device"))
            if value
        }
    )
    topology = network.get("topology") or {}
    network_segments = [
        item
        for item in (topology.get("segments") or [])
        if item.get("name") not in {"wan", "wan6", "loopback"}
    ]
    network_bridges = topology.get("bridges") or []
    network_vlans = topology.get("vlans") or []
    physical_port_options = sorted(
        name
        for name in network_devices
        if name != "lo" and not name.startswith(("br-", "phy", "wlan"))
    )
    bridge_options = sorted(
        {str(item.get("name")) for item in network_bridges if item.get("name")}
    )
    network_options = sorted(
        {str(item.get("interface")) for item in interfaces if item.get("interface")}
    )
    firewall_zone_options = sorted(
        {
            str(item.get("name"))
            for item in network.get("firewall_zones") or []
            if item.get("name")
        }
    )
    lan_dhcp_pool = next(
        (
            item
            for item in dhcp_config.get("pools") or []
            if isinstance(item, dict) and item.get("interface") == "lan"
        ),
        {},
    )
    lan_ipv6 = {
        "enabled": bool(lan_interface.get("ip6assign")),
        "assignment_length": str(lan_interface.get("ip6assign") or "64"),
        "hint": str(lan_interface.get("ip6hint") or ""),
        "addresses": lan_interface.get("ipv6") or [],
        "ra": str(lan_dhcp_pool.get("ra") or "disabled"),
        "dhcpv6": str(lan_dhcp_pool.get("dhcpv6") or "disabled"),
        "ndp": str(lan_dhcp_pool.get("ndp") or "disabled"),
        "ra_management": str(lan_dhcp_pool.get("ra_management") or "0"),
    }
    capabilities = agent.get("capabilities") or {}
    capability_details = agent.get("capability_details") or {}
    capabilities_summary = capability_summary(capabilities)
    capabilities_groups = grouped_capabilities(capabilities, capability_details)
    capabilities_message = capabilities_hint(capabilities)

    def has(name: str) -> bool:
        return bool(capabilities.get(name, False))

    supports = {
        "agent_update": has("agent.update"),
        "agent_ssh_session": has("agent.ssh_session"),
        "agent_bash_script": has("agent.bash_script"),
        "agent_set_interval": has("agent.set_interval"),
        "agent_rotate_token": has("agent.rotate_token"),
        "agent_rollback": has("agent.rollback"),
        "diagnostics": has("diagnostics.check_server"),
        "network_read": has("network.read"),
        "network_interface_restart": has("network.interface_restart"),
        "network_restart": has("network.restart"),
        "network_wan_configure": has("network.wan.configure"),
        "network_lan_configure": has("network.lan.configure"),
        "network_ipv6": has("network.ipv6.configure"),
        "network_segments": has("network.segments.configure"),
        "network_vlan": has("network.vlan.configure"),
        "network_multiwan": has("network.multiwan.configure"),
        "network_routes": has("network.routes.configure"),
        "network_ddns": has("network.ddns.configure"),
        "firewall_zones": has("firewall.zones.configure"),
        "firewall_rules": has("firewall.rules.configure"),
        "firewall_upnp": has("firewall.upnp.configure"),
        "vpn_wireguard_read": has("vpn.wireguard.read"),
        "vpn_wireguard_configure": has("vpn.wireguard.configure"),
        "vpn_openvpn_read": has("vpn.openvpn.read"),
        "vpn_openvpn_configure": has("vpn.openvpn.configure"),
        "vpn_policy_read": has("vpn.policy.read"),
        "vpn_policy_configure": has("vpn.policy.configure"),
        "clients_read": has("clients.read"),
        "clients_block": has("clients.block"),
        "clients_policy": has("clients.policy"),
        "qos_sqm": has("qos.sqm"),
        "dhcp_set_lease": has("dhcp.set_lease"),
        "dhcp_delete_lease": has("dhcp.delete_lease"),
        "dhcp_configure": has("dhcp.configure"),
        "dns_configure": has("dns.configure"),
        "dns_encrypted_install": has("dns.encrypted.install"),
        "dns_dot": has("dns.dot.configure"),
        "dns_doh": has("dns.doh.configure"),
        "firewall_port_forward": has("firewall.port_forward"),
        "system_reboot": has("system.reboot"),
        "system_set_hostname": has("system.set_hostname"),
        "system_restart_service": has("system.restart_service"),
        "wifi_toggle": has("wifi.enable") or has("wifi.disable"),
        "wifi_ssid": has("wifi.set_ssid"),
        "wifi_password": has("wifi.set_password"),
        "wifi_channel": has("wifi.set_channel"),
        "wifi_country": has("wifi.set_country"),
        "wifi_guest": has("wifi.guest"),
        "wifi_radio_configure": has("wifi.radio.configure"),
        "wifi_manage_ssid": has("wifi.manage_ssid"),
        "wifi_schedule": has("wifi.schedule"),
        "wifi_roaming": has("wifi.roaming"),
        "wifi_mesh": has("wifi.mesh"),
        "wifi_stations": has("telemetry.wifi.stations"),
        "client_traffic": has("telemetry.clients.traffic"),
        "system_timezone": has("system.set_timezone"),
        "system_ntp": has("system.set_ntp"),
        "maintenance_packages_read": has("maintenance.packages.read"),
        "maintenance_packages_write": has("maintenance.packages.write"),
        "maintenance_backup": has("maintenance.backup"),
        "maintenance_sysupgrade_check": has("maintenance.sysupgrade.check"),
        "maintenance_sysupgrade_apply": has("maintenance.sysupgrade.apply"),
        "maintenance_logs": has("maintenance.logs"),
        "maintenance_processes": has("maintenance.processes"),
        "maintenance_cron": has("maintenance.cron"),
        "maintenance_bundle": has("maintenance.diagnostics.bundle"),
        "maintenance_recovery": has("maintenance.recovery"),
        "maintenance_modules": has("maintenance.modules.write"),
    }
    cleanup_device_command_history(
        db,
        device_id,
        config.command_history_retention_days,
        config.command_history_max_per_device,
    )
    command_page_size = 5
    command_total = int(
        db.scalar(
            select(func.count(DeviceCommand.id)).where(
                DeviceCommand.device_id == device_id
            )
        )
        or 0
    )
    command_pages = max(1, (command_total + command_page_size - 1) // command_page_size)
    command_page = min(max(command_page, 1), command_pages)
    commands = db.scalars(
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device_id)
        .order_by(DeviceCommand.created_at.desc())
        .offset((command_page - 1) * command_page_size)
        .limit(command_page_size)
    ).all()
    command_entries = [command_history_entry(command) for command in commands]
    support_commands = db.scalars(
        select(DeviceCommand)
        .where(
            DeviceCommand.device_id == device_id,
            DeviceCommand.command_type.in_(
                (
                    "diagnostics.run",
                    "maintenance.backup.create",
                    "maintenance.diagnostics.bundle",
                )
            ),
        )
        .order_by(DeviceCommand.created_at.desc())
        .limit(20)
    ).all()
    download_artifacts = [
        {
            "id": str(command.id),
            "kind": "backup"
            if command.command_type == "maintenance.backup.create"
            else "diagnostics",
            "label": "Скачать резервную копию"
            if command.command_type == "maintenance.backup.create"
            else "Скачать диагностический архив",
        }
        for command in support_commands
        if command.status == "success"
        and isinstance(command.result, dict)
        and (
            command.result.get("archive_base64") or command.result.get("bundle_base64")
        )
    ]
    latest_diagnostics = next(
        (
            command
            for command in (command_history_entry(item) for item in support_commands)
            if command["command_type"] == "diagnostics.run"
        ),
        None,
    )
    latest = format_timestamp(telemetry.created_at) if telemetry else "нет данных"
    dashboard_history = device_telemetry_history(db, device_id, 120, range_name="live")
    wan_events = []
    if section == "internet":
        wan_events = [
            {
                "created_at": format_timestamp(item.created_at),
                "details": item.details or {},
            }
            for item in db.scalars(
                select(AuditLog)
                .where(
                    AuditLog.object_type == "device",
                    AuditLog.object_id == str(device_id),
                    AuditLog.action == "wan.failover",
                )
                .order_by(AuditLog.created_at.desc())
                .limit(20)
            ).all()
        ]
    firmware_images = (
        firmware_catalog(payload) if section == "management" else {"images": []}
    )
    hardware_view = hardware_summary(db, device_id, payload)
    db.commit()

    age = (
        max(0, int((datetime.now(UTC) - telemetry.created_at).total_seconds()))
        if telemetry
        else None
    )
    memory_total = int(memory.get("total_kb", 0) or 0)
    memory_available = int(memory.get("available_kb", memory.get("free_kb", 0)) or 0)
    memory_used = max(0, memory_total - memory_available)
    storage_total = int(storage.get("total_kb", 0) or 0)
    storage_used = int(storage.get("used_kb", 0) or 0)
    conntrack_count = int(system_summary.get("conntrack_count", 0) or 0)
    conntrack_max = int(system_summary.get("conntrack_max", 0) or 0)
    try:
        load_1m = float(system.get("load"))
    except (TypeError, ValueError):
        load_1m = None
    try:
        cpu_cores = max(1, int(cpu.get("cores")))
    except (TypeError, ValueError):
        cpu_cores = None
    load_capacity_percent = (
        max(0, round(load_1m / cpu_cores * 100))
        if load_1m is not None and cpu_cores
        else None
    )
    system_view = {
        "memory_total": memory_total,
        "memory_available": memory_available,
        "memory_used": memory_used,
        "memory_percent": percent(memory_used, memory_total),
        "storage_total": storage_total,
        "storage_used": storage_used,
        "storage_percent": percent(storage_used, storage_total),
        "conntrack_percent": percent(conntrack_count, conntrack_max),
        "load_1m": load_1m,
        "cpu_cores": cpu_cores,
        "load_capacity_percent": load_capacity_percent,
        "load_level": (
            "низкая"
            if load_capacity_percent is not None and load_capacity_percent < 50
            else "умеренная"
            if load_capacity_percent is not None and load_capacity_percent < 100
            else "высокая"
            if load_capacity_percent is not None
            else None
        ),
        "telemetry_state": "Актуальные данные"
        if age is not None and age <= 120
        else "Данные устарели",
    }
    return templates.TemplateResponse(
        request,
        "device_detail.html",
        {
            "device": device,
            "server_version": APP_VERSION,
            "section": section,
            "csrf_token": csrf_token,
            "latest": latest,
            "dashboard_history": dashboard_history,
            "health": build_health_snapshot(payload, age, agent=agent),
            "telemetry_alerts": telemetry_alerts(payload, age),
            "age": age,
            "system": system,
            "memory": memory,
            "cpu": cpu,
            "storage": storage,
            "thermal": thermal,
            "hardware_view": hardware_view,
            "traffic": traffic,
            "processes": processes,
            "board": board,
            "agent": agent,
            "capabilities": capabilities,
            "capabilities_summary": capabilities_summary,
            "capabilities_groups": capabilities_groups,
            "capabilities_message": capabilities_message,
            "supports": supports,
            "wifi": wifi,
            "radios": radios,
            "interfaces": interfaces,
            "lan_interface": lan_interface,
            "wan_interface": wan_interface,
            "interface_options": interface_options,
            "network_options": network_options,
            "network_segments": network_segments,
            "network_bridges": network_bridges,
            "network_vlans": network_vlans,
            "physical_port_options": physical_port_options,
            "bridge_options": bridge_options,
            "lan_dhcp_pool": lan_dhcp_pool,
            "lan_ipv6": lan_ipv6,
            "firewall_zone_options": firewall_zone_options,
            "netmask_options": NETMASK_OPTIONS,
            "timezone_options": TIMEZONE_OPTIONS,
            "timezone_names": {item[0] for item in TIMEZONE_OPTIONS},
            "wifi_countries": WIFI_COUNTRIES,
            "wifi_channels": WIFI_CHANNELS,
            "network": network,
            "wan_events": wan_events,
            "policy_catalog": policy_catalog(),
            "firmware_catalog": firmware_images,
            "vpn": vpn,
            "network_devices": network_devices,
            "clients": clients,
            "client_profiles": client_profiles,
            "client_count": len(clients)
            if clients
            else telemetry_clients.get("count", 0),
            "online_client_count": online_client_count
            if clients
            else telemetry_clients.get("online_count", 0),
            "recent_client_count": recent_client_count
            if clients
            else telemetry_clients.get("recent_count", 0),
            "client_traffic_available": bool(
                supports["client_traffic"]
                and telemetry_clients.get("traffic_available")
            ),
            "client_traffic_status": telemetry_clients.get("traffic_status"),
            "client_traffic_diagnostics": telemetry_clients.get("traffic_diagnostics")
            or {},
            "system_summary": system_summary,
            "system_view": system_view,
            "services": services,
            "maintenance": maintenance,
            "module_labels": {
                "storage": "USB и накопители",
                "smb": "SMB-файлы",
                "nfs": "NFS-файлы",
                "ftp": "FTP-сервер",
                "dlna": "DLNA-медиасервер",
                "printer": "USB-принтер",
                "modem": "LTE/USB-модем",
            },
            "commands": command_entries,
            "command_pagination": {
                "page": command_page,
                "pages": command_pages,
                "total": command_total,
                "page_size": command_page_size,
                "start": (command_page - 1) * command_page_size + 1
                if command_total
                else 0,
                "end": min(command_page * command_page_size, command_total),
                "retention_days": config.command_history_retention_days,
                "max_per_device": config.command_history_max_per_device,
            },
            "download_artifacts": download_artifacts,
            "latest_diagnostics": latest_diagnostics,
            "raw_telemetry": json.dumps(payload, ensure_ascii=False, indent=2),
        },
    )


@router.get("/devices/{device_id}/hardware-report", response_class=JSONResponse)
def download_device_hardware_report(
    device_id: UUID,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> JSONResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    device = get_user_device_or_404(db, user, device_id)
    telemetry = latest_device_telemetry(db, device_id)
    return JSONResponse(
        hardware_report(db, device_id, telemetry.payload if telemetry else {}, device),
        headers={
            "Content-Disposition": f'attachment; filename="wrtmonitor-hardware-{device_id}.json"'
        },
    )


@router.get("/devices/{device_id}/live", response_class=JSONResponse)
def device_live_data(
    device_id: UUID,
    limit: int = 60,
    range_name: str = Query(
        default="live", alias="range", pattern="^(live|24h|7d|30d)$"
    ),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> JSONResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    device = get_user_device_or_404(db, user, device_id)
    return JSONResponse(
        {
            "device_id": str(device.id),
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat()
            if device.last_seen_at
            else None,
            "range": range_name,
            "points": device_telemetry_history(
                db, device_id, limit, range_name=range_name
            ),
        }
    )


__all__ = [
    "router",
    "device_page",
    "device_live_data",
    "download_device_hardware_report",
]
