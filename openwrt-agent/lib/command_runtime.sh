resolve_dhcp_host_by_mac() {
    requested_mac="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    host_index=0
    while uci -q get "dhcp.@host[$host_index]" >/dev/null 2>&1; do
        current_mac="$(uci -q get "dhcp.@host[$host_index].mac" 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)"
        if [ "$current_mac" = "$requested_mac" ]; then
            printf '@host[%s]' "$host_index"
            return 0
        fi
        host_index=$((host_index + 1))
    done
    return 1
}

set_auto_update_config() {
    enabled_value="$1"
    if [ "$enabled_value" = "1" ]; then
        uci set "$CONFIG.auto_update=1"
    else
        uci set "$CONFIG.auto_update=0"
    fi
    uci commit wrtmonitor
    load_status
    write_status "$LAST_UPDATE_STATUS" "$LAST_UPDATE_ERROR" "$AVAILABLE_VERSION" "$LAST_UPDATE_CHECK" "$LAST_SUCCESSFUL_UPDATE"
}

openvpn_render_configs() {
    openvpn_dir="${WRTMONITOR_SYSTEM_ROOT:-}/etc/openvpn"
    mkdir -p "$openvpn_dir"
    for openvpn_ref in $(uci -q show openvpn 2>/dev/null | sed -n 's/^openvpn\.\([^.=]*\)=openvpn$/\1/p'); do
        config_b64="$(uci -q get "openvpn.$openvpn_ref.wrtmonitor_config_b64" 2>/dev/null || true)"
        [ -n "$config_b64" ] || continue
        config_path="$openvpn_dir/wrtmonitor-$openvpn_ref.conf"
        printf '%s' "$config_b64" | base64 -d >"$config_path" || return 1
        chmod 0600 "$config_path"
        uci set "openvpn.$openvpn_ref.config=/etc/openvpn/wrtmonitor-$openvpn_ref.conf"
    done
    uci commit openvpn
}
