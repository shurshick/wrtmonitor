transaction_configs_for_command() {
    case "$1" in
        wifi.set_enabled|wifi.set_ssid|wifi.set_password|wifi.set_channel|wifi.set_country|wifi.set_radio|wifi.add_ssid|wifi.update_ssid|wifi.delete_ssid|wifi.set_mesh) printf 'wireless' ;;
        wifi.set_schedule) printf 'wireless wrtmonitor' ;;
        wifi.set_guest) printf 'wireless network dhcp firewall' ;;
        network.set_wan|network.set_lan) printf 'network' ;;
        network.set_ipv6) printf 'network dhcp' ;;
        network.set_segment|network.delete_segment) printf 'network dhcp firewall' ;;
        network.set_vlan|network.delete_vlan) printf 'network' ;;
        network.set_multiwan) printf 'network mwan3' ;;
        network.set_route|network.delete_route) printf 'network' ;;
        network.set_ddns) printf 'ddns' ;;
        network.set_upnp) printf 'upnpd firewall' ;;
        vpn.wireguard.set_interface|vpn.wireguard.delete_interface) printf 'network' ;;
        vpn.wireguard.set_peer|vpn.wireguard.delete_peer) printf 'network' ;;
        vpn.openvpn.set_client|vpn.openvpn.delete_client|vpn.openvpn.set_enabled) printf 'openvpn' ;;
        vpn.policy.set|vpn.policy.delete) printf 'pbr' ;;
        dhcp.set_lease|dhcp.delete_lease|dhcp.set_pool|dns.set_servers) printf 'dhcp' ;;
        dns.set_dot) printf 'dhcp stubby' ;;
        dns.set_doh) printf 'dhcp https-dns-proxy' ;;
        firewall.set_port_forward|firewall.delete_port_forward|client.set_blocked) printf 'firewall' ;;
        client.set_policy) printf 'firewall wrtmonitor' ;;
        firewall.set_zone|firewall.delete_zone|firewall.set_forwarding|firewall.delete_forwarding|firewall.set_rule|firewall.delete_rule|firewall.set_redirect|firewall.delete_redirect) printf 'firewall' ;;
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
        wifi.*|network.set_*|network.delete_*|dhcp.*|dns.set_*|firewall.*|vpn.*|qos.set_sqm) return 0 ;;
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
