transaction_configs_for_command() {
    case "$1" in
        wifi.set_enabled|wifi.set_ssid|wifi.set_password|wifi.set_channel|wifi.set_country|wifi.set_radio|wifi.add_ssid|wifi.update_ssid|wifi.delete_ssid|wifi.set_mesh) printf 'wireless' ;;
        wifi.set_schedule) printf 'wireless wrtmonitor' ;;
        wifi.set_guest) printf 'wireless network dhcp firewall' ;;
        network.set_wan|network.set_lan) printf 'network' ;;
        network.set_ipv6) printf 'network dhcp' ;;
        network.set_multiwan) printf 'network mwan3' ;;
        network.set_route|network.delete_route) printf 'network' ;;
        network.set_ddns) printf 'ddns' ;;
        network.set_upnp) printf 'upnpd firewall' ;;
        vpn.wireguard.set_interface) printf 'network' ;;
        vpn.wireguard.set_peer|vpn.wireguard.delete_peer) printf 'network' ;;
        vpn.openvpn.set_client|vpn.openvpn.delete_client) printf 'openvpn' ;;
        vpn.policy.set|vpn.policy.delete) printf 'pbr' ;;
        dhcp.set_lease|dhcp.delete_lease|dhcp.set_pool|dns.set_servers) printf 'dhcp' ;;
        dns.set_dot) printf 'dhcp stubby' ;;
        dns.set_doh) printf 'dhcp https-dns-proxy' ;;
        firewall.set_port_forward|firewall.delete_port_forward|client.set_blocked|client.set_policy) printf 'firewall' ;;
        firewall.set_zone|firewall.delete_zone|firewall.set_forwarding|firewall.delete_forwarding|firewall.set_rule|firewall.delete_rule) printf 'firewall' ;;
        qos.set_sqm) printf 'sqm' ;;
        system.set_hostname|system.set_timezone|system.set_ntp) printf 'system' ;;
        *) return 1 ;;
    esac
}

transaction_config_file() {
    printf '%s/etc/config/%s' "${WRTMONITOR_SYSTEM_ROOT:-}" "$1"
}

transaction_service() {
    printf '%s/etc/init.d/%s' "${WRTMONITOR_SYSTEM_ROOT:-}" "$1"
}

transaction_is_connectivity_sensitive() {
    case "$1" in
        wifi.*|network.set_*|dhcp.*|dns.set_*|firewall.*|client.set_blocked|client.set_policy|qos.set_sqm) return 0 ;;
        *) return 1 ;;
    esac
}

transaction_valid_id() {
    case "$1" in
        ""|*[!A-Za-z0-9-]*) return 1 ;;
        *) return 0 ;;
    esac
}

transaction_dir() {
    transaction_valid_id "$1" || return 1
    printf '%s/%s' "$CONFIG_TRANSACTION_DIR" "$1"
}

transaction_timeout_from_payload() {
    payload_file="/tmp/wrtmonitor-transaction-payload-$$"
    printf '%s' "$1" >"$payload_file"
    timeout="$(json_get_number "$payload_file" '@._transaction.rollback_timeout_seconds')"
    rm -f "$payload_file"
    case "$timeout" in ""|*[!0-9]*) timeout=90 ;; esac
    if [ "$timeout" -lt 30 ]; then timeout=30; fi
    if [ "$timeout" -gt 180 ]; then timeout=180; fi
    printf '%s' "$timeout"
}

transaction_begin() {
    command_id="$1"
    command_type="$2"
    rollback_timeout="$3"
    configs="$(transaction_configs_for_command "$command_type")" || return 2
    ensure_state_dirs
    directory="$(transaction_dir "$command_id")" || return 2
    if [ -r "$directory/meta" ]; then return 0; fi
    available_kb="$(df -k "$STATUS_DIR" 2>/dev/null | awk 'NR == 2 { print $4 }')"
    case "$available_kb" in ""|*[!0-9]*) available_kb=0 ;; esac
    [ "$available_kb" -ge 64 ] || return 3
    mkdir -p "$directory"
    for config_name in $configs; do
        config_file="$(transaction_config_file "$config_name")"
        [ -r "$config_file" ] || return 4
        uci -q show "$config_name" >/dev/null 2>&1 || return 5
        cp "$config_file" "$directory/$config_name.bak" || return 6
    done
    {
        printf 'command_id=%s\n' "$command_id"
        printf 'command_type=%s\n' "$command_type"
        printf 'configs=%s\n' "$configs"
        printf 'rollback_timeout=%s\n' "$rollback_timeout"
        printf 'started_epoch=%s\n' "$(date +%s 2>/dev/null || echo 0)"
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'state=prepared\n'
    } >"$directory/meta"
}

transaction_meta_value() {
    directory="$(transaction_dir "$1")" || return 1
    key="$2"
    sed -n "s/^$key=//p" "$directory/meta" 2>/dev/null | head -n 1
}

transaction_set_state() {
    directory="$(transaction_dir "$1")" || return 1
    sed -i "s/^state=.*/state=$2/" "$directory/meta"
}

transaction_restore() {
    command_id="$1"
    directory="$(transaction_dir "$command_id")" || return 1
    configs="$(transaction_meta_value "$command_id" configs)"
    [ -n "$configs" ] || return 1
    restore_status=0
    for config_name in $configs; do
        backup_file="$directory/$config_name.bak"
        [ -r "$backup_file" ] && cp "$backup_file" "$(transaction_config_file "$config_name")" || restore_status=1
    done
    if printf '%s' "$configs" | grep -qw wireless; then wifi reload >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw network; then "$(transaction_service network)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw dhcp; then "$(transaction_service dnsmasq)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw stubby; then "$(transaction_service stubby)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw https-dns-proxy; then "$(transaction_service https-dns-proxy)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw firewall; then "$(transaction_service firewall)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw sqm; then "$(transaction_service sqm)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw mwan3; then "$(transaction_service mwan3)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw ddns; then "$(transaction_service ddns)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw upnpd; then "$(transaction_service miniupnpd)" restart >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw openvpn; then
        command -v openvpn_render_configs >/dev/null 2>&1 && openvpn_render_configs
        "$(transaction_service openvpn)" restart >/dev/null 2>&1 || restore_status=1
    fi
    if printf '%s' "$configs" | grep -qw pbr; then "$(transaction_service pbr)" restart >/dev/null 2>&1 || restore_status=1; fi
    transaction_set_state "$command_id" "rolled_back"
    return "$restore_status"
}

transaction_success_result() {
    configs="$(transaction_meta_value "$1" configs)"
    printf '{"message":"configuration applied and verified","transaction":{"id":"%s","state":"confirmed","configs":"%s","rollback":false}}' \
        "$(json_escape "$1")" "$(json_escape "$configs")"
}

transaction_failure_result() {
    printf '{"error":"%s","transaction":{"id":"%s","state":"%s","rollback":true}}' \
        "$(json_escape "$2")" "$(json_escape "$1")" "$(json_escape "$3")"
}

transaction_schedule_verification() {
    transaction_set_state "$1" "verifying"
    (sleep 10; "$SCRIPT_PATH" verify-transaction "$1") >/dev/null 2>&1 &
}

verify_transaction() {
    command_id="$1"
    directory="$(transaction_dir "$command_id")" || return 1
    [ -r "$directory/meta" ] || return 1
    rollback_timeout="$(transaction_meta_value "$command_id" rollback_timeout)"
    started_epoch="$(transaction_meta_value "$command_id" started_epoch)"
    case "$rollback_timeout" in ""|*[!0-9]*) rollback_timeout=90 ;; esac
    case "$started_epoch" in ""|*[!0-9]*) started_epoch="$(date +%s 2>/dev/null || echo 0)" ;; esac
    while true; do
        if curl -fsS --connect-timeout 5 --max-time 10 "$(server_url)/health" >/dev/null 2>&1; then
            transaction_set_state "$command_id" "confirmed"
            result="$(transaction_success_result "$command_id")"
            api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"success\",\"result\":$result}" >/dev/null || true
            return 0
        fi
        now_epoch="$(date +%s 2>/dev/null || echo 0)"
        [ "$now_epoch" -lt $((started_epoch + rollback_timeout)) ] || break
        sleep 5
    done
    if transaction_restore "$command_id"; then rollback_state="rolled_back"; else rollback_state="rollback_failed"; fi
    sleep 8
    result="$(transaction_failure_result "$command_id" "connectivity verification timed out" "$rollback_state")"
    api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"failed\",\"result\":$result}" >/dev/null || true
    return 1
}
