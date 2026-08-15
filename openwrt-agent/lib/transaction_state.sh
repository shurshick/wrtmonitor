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
