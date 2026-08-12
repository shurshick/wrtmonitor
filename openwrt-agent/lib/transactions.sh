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

transaction_store_payload() {
    directory="$(transaction_dir "$1")" || return 1
    printf '%s' "$2" >"$directory/payload.json"
    chmod 600 "$directory/payload.json" 2>/dev/null || true
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
    command_type="$(transaction_meta_value "$command_id" command_type)"
    if [ "$command_type" = client.set_policy ] && [ -r "$directory/payload.json" ]; then
        policy_mac="$(json_get_string "$directory/payload.json" '@.mac')"
        if [ -n "$policy_mac" ]; then
            current_section="$(client_policy_section "$policy_mac")"
            current_device="$(uci -q get "wrtmonitor.$current_section.shaping_device" 2>/dev/null || client_policy_lan_device)"
            current_pref="$(uci -q get "wrtmonitor.$current_section.shaping_pref" 2>/dev/null || client_policy_filter_pref "$policy_mac")"
            client_policy_delete_filter "$current_device" ingress "$current_pref"
            client_policy_delete_filter "$current_device" egress "$current_pref"
        fi
    fi
    restore_status=0
    for config_name in $configs; do
        backup_file="$directory/$config_name.bak"
        [ -r "$backup_file" ] && cp "$backup_file" "$(transaction_config_file "$config_name")" || restore_status=1
    done
    if printf '%s' "$configs" | grep -qw wireless; then wifi reload >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw network; then
        payload_file="$directory/payload.json"
        case "$command_type" in
            network.set_lan|network.set_wan)
                interface=""
                [ ! -r "$payload_file" ] || interface="$(json_get_string "$payload_file" '@.interface')"
                if [ -z "$interface" ]; then
                    [ "$command_type" = network.set_lan ] && interface=lan || interface=wan
                fi
                if command -v ifdown >/dev/null 2>&1 && command -v ifup >/dev/null 2>&1; then
                    network_interface_cycle "$interface" || restore_status=1
                else
                    service_action network reload 30 >/dev/null 2>&1 || restore_status=1
                fi
                if [ "$command_type" = network.set_lan ]; then
                    restored_ipv4="$(uci -q get "network.$interface.ipaddr" 2>/dev/null || true)"
                    restored_ipv4="${restored_ipv4%%/*}"
                    network_interface_has_ipv4 "$interface" "$restored_ipv4" || restore_status=1
                fi
                ;;
            *) service_action network reload 30 >/dev/null 2>&1 || restore_status=1 ;;
        esac
    fi
    if printf '%s' "$configs" | grep -qw dhcp; then service_action dnsmasq restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw stubby; then service_action stubby restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw https-dns-proxy; then service_action https-dns-proxy restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw firewall; then service_action firewall restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw wrtmonitor; then restore_client_policy_runtime || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw sqm; then service_action sqm restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw mwan3; then service_action mwan3 restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw ddns; then service_action ddns restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw upnpd; then service_action miniupnpd restart 20 >/dev/null 2>&1 || restore_status=1; fi
    if printf '%s' "$configs" | grep -qw openvpn; then
        command -v openvpn_render_configs >/dev/null 2>&1 && openvpn_render_configs
        service_action openvpn restart 20 >/dev/null 2>&1 || restore_status=1
    fi
    if printf '%s' "$configs" | grep -qw pbr; then service_restart_if_enabled pbr config.enabled pbr >/dev/null 2>&1 || restore_status=1; fi
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

transaction_restart_verification_window() {
    directory="$(transaction_dir "$1")" || return 1
    recovery_count="$(transaction_meta_value "$1" recovery_count)"
    case "$recovery_count" in ""|*[!0-9]*) recovery_count=0 ;; esac
    [ "$recovery_count" -lt 1 ] || return 1
    recovery_count=$((recovery_count + 1))
    sed -i "/^started_epoch=/d;/^recovery_count=/d" "$directory/meta"
    {
        printf 'started_epoch=%s\n' "$(date +%s 2>/dev/null || echo 0)"
        printf 'recovery_count=%s\n' "$recovery_count"
    } >>"$directory/meta"
}

transaction_runtime_ready() {
    command_id="$1"
    command_type="$(transaction_meta_value "$command_id" command_type)"
    [ "$command_type" = network.set_lan ] || return 0
    directory="$(transaction_dir "$command_id")" || return 1
    payload_file="$directory/payload.json"
    [ -r "$payload_file" ] || return 1
    interface="$(json_get_string "$payload_file" '@.interface')"
    [ -n "$interface" ] || interface=lan
    expected_ipv4="$(json_get_string "$payload_file" '@.ip_address')"
    network_interface_has_ipv4 "$interface" "$expected_ipv4"
}

transaction_has_newer_confirmed_overlap() {
    current_id="$1"
    current_configs="$2"
    current_started="$3"
    for other_directory in "$CONFIG_TRANSACTION_DIR"/*; do
        [ -r "$other_directory/meta" ] || continue
        other_id="${other_directory##*/}"
        [ "$other_id" != "$current_id" ] || continue
        [ "$(transaction_meta_value "$other_id" state)" = "confirmed" ] || continue
        other_started="$(transaction_meta_value "$other_id" started_epoch)"
        case "$other_started" in ""|*[!0-9]*) continue ;; esac
        [ "$other_started" -gt "$current_started" ] || continue
        other_configs="$(transaction_meta_value "$other_id" configs)"
        for config_name in $current_configs; do
            if printf '%s\n' "$other_configs" | grep -qw "$config_name"; then
                return 0
            fi
        done
    done
    return 1
}

transaction_recover_pending() {
    ensure_state_dirs
    now_epoch="$(date +%s 2>/dev/null || echo 0)"
    for directory in "$CONFIG_TRANSACTION_DIR"/*; do
        [ -r "$directory/meta" ] || continue
        command_id="${directory##*/}"
        transaction_valid_id "$command_id" || continue
        state="$(transaction_meta_value "$command_id" state)"
        case "$state" in prepared|verifying) ;; *) continue ;; esac
        rollback_timeout="$(transaction_meta_value "$command_id" rollback_timeout)"
        started_epoch="$(transaction_meta_value "$command_id" started_epoch)"
        case "$rollback_timeout" in ""|*[!0-9]*) rollback_timeout=90 ;; esac
        case "$started_epoch" in ""|*[!0-9]*) started_epoch=0 ;; esac
        configs="$(transaction_meta_value "$command_id" configs)"
        if transaction_has_newer_confirmed_overlap "$command_id" "$configs" "$started_epoch"; then
            transaction_set_state "$command_id" "superseded"
            result="$(transaction_failure_result "$command_id" "unfinished transaction superseded by a newer confirmed change" "not_applied")"
            report_command_result "$command_id" failed "$result" >/dev/null 2>&1 || true
            log_notice "abandoned superseded transaction $command_id"
            continue
        fi
        if [ "$started_epoch" -gt 0 ] && [ "$now_epoch" -lt $((started_epoch + rollback_timeout)) ]; then
            transaction_schedule_verification "$command_id"
            continue
        fi
        if transaction_restart_verification_window "$command_id"; then
            transaction_schedule_verification "$command_id"
            log_notice "resumed unfinished transaction $command_id after agent restart"
            continue
        fi
        if transaction_restore "$command_id"; then
            rollback_state="rolled_back"
        else
            rollback_state="rollback_failed"
        fi
        result="$(transaction_failure_result "$command_id" "agent restarted before transaction confirmation" "$rollback_state")"
        report_command_result "$command_id" failed "$result" >/dev/null 2>&1 || true
        log_notice "recovered unfinished transaction $command_id: $rollback_state"
    done
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
        if curl -fsS --connect-timeout 5 --max-time 10 "$(server_url)/health" >/dev/null 2>&1 && transaction_runtime_ready "$command_id"; then
            transaction_set_state "$command_id" "confirmed"
            result="$(transaction_success_result "$command_id")"
            report_command_result "$command_id" success "$result" >/dev/null || true
            return 0
        fi
        now_epoch="$(date +%s 2>/dev/null || echo 0)"
        [ "$now_epoch" -lt $((started_epoch + rollback_timeout)) ] || break
        sleep 5
    done
    if transaction_restore "$command_id"; then rollback_state="rolled_back"; else rollback_state="rollback_failed"; fi
    sleep 8
    result="$(transaction_failure_result "$command_id" "connectivity verification timed out" "$rollback_state")"
    report_command_result "$command_id" failed "$result" >/dev/null || true
    return 1
}
