telemetry() {
    agent_enabled || return 0
    [ -n "$(device_id)" ] || register_device
    body="$(telemetry_payload)"
    api POST /api/v1/agent/telemetry "$body" >/dev/null
}

telemetry_payload() {
    [ -n "$(device_id)" ] || register_device
    uptime_value="$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 0)"
    load_values="$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo '0 0 0')"
    load_value="$(printf '%s' "$load_values" | cut -d' ' -f1)"
    load_5m="$(printf '%s' "$load_values" | cut -d' ' -f2)"
    load_15m="$(printf '%s' "$load_values" | cut -d' ' -f3)"
    case "$uptime_value" in
        ""|*[!0-9]*) uptime_value="0" ;;
    esac
    load_value="$(json_escape "$load_value")"
    printf '{"device_id":"%s","telemetry":{"schema_version":2,"system":{"uptime":%s,"load":"%s","load_5m":"%s","load_15m":"%s","hostname":"%s","kernel":"%s","local_time":"%s","time":%s,"memory":%s,"processes":%s,"conntrack":%s,"services":%s,"ubus":%s},"cpu":%s,"storage":%s,"thermal":%s,"traffic":%s,"board":%s,"network":%s,"network_devices":%s,"wifi":%s,"clients":%s,"dhcp":%s,"perimeter":%s,"vpn":%s,"modules":%s,"maintenance":%s,"agent":%s}}' \
        "$(device_id)" \
        "$uptime_value" \
        "$load_value" \
        "$(json_escape "$load_5m")" \
        "$(json_escape "$load_15m")" \
        "$(json_escape "$(uci -q get system.@system[0].hostname 2>/dev/null || hostname)")" \
        "$(json_escape "$(uname -r 2>/dev/null || true)")" \
        "$(json_escape "$(iso_now)")" \
        "$(system_time_json)" \
        "$(memory_json)" \
        "$(processes_json)" \
        "$(conntrack_json)" \
        "$(services_json)" \
        "$(ubus_json system info)" \
        "$(cpu_json)" \
        "$(storage_json)" \
        "$(thermal_json)" \
        "$(traffic_json)" \
        "$(ubus_json system board)" \
        "$(network_summary_json)" \
        "$(network_devices_json)" \
        "$(wifi_status_json)" \
        "$(clients_json)" \
        "$(dhcp_json)" \
        "$(perimeter_json)" \
        "$(vpn_json)" \
        "$(modules_json)" \
        "$(maintenance_json)" \
        "$(agent_status_json)"
}
