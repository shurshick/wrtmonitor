verify_uci_value() {
    key="$1"
    expected="$2"
    actual="$(uci -q get "$key" 2>/dev/null || true)"
    [ "$actual" = "$expected" ]
}

verify_command_postcondition() {
    command_type="$1"
    command_payload="$2"
    payload_file="/tmp/wrtmonitor-verify-payload-$$"
    printf '%s' "$command_payload" >"$payload_file"
    verified=0
    case "$command_type" in
        agent.set_interval)
            expected="$(json_get_number "$payload_file" '@.interval_seconds')"
            verify_uci_value "$CONFIG.interval" "$expected" || verified=1
            ;;
        agent.rotate_token)
            [ -n "$(device_token)" ] || verified=1
            ;;
        system.set_hostname)
            expected="$(json_get_string "$payload_file" '@.hostname')"
            verify_uci_value 'system.@system[0].hostname' "$expected" || verified=1
            ;;
        system.set_timezone)
            expected="$(json_get_string "$payload_file" '@.timezone')"
            verify_uci_value 'system.@system[0].timezone' "$expected" || verified=1
            ;;
        wifi.set_enabled)
            radio="$(json_get_string "$payload_file" '@.radio')"
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            radio="$(resolve_wifi_radio "$radio" || true)"
            expected=1
            [ "$enabled" = true ] && expected=0
            [ -n "$radio" ] && verify_uci_value "wireless.$radio.disabled" "$expected" || verified=1
            ;;
        wifi.set_ssid)
            iface="$(json_get_string "$payload_file" '@.iface')"
            expected="$(json_get_string "$payload_file" '@.ssid')"
            iface="$(resolve_wifi_iface "$iface" "" || true)"
            [ -n "$iface" ] && verify_uci_value "wireless.$iface.ssid" "$expected" || verified=1
            ;;
        wifi.set_channel)
            radio="$(json_get_string "$payload_file" '@.radio')"
            expected="$(json_get_string "$payload_file" '@.channel')"
            radio="$(resolve_wifi_radio "$radio" || true)"
            [ -n "$radio" ] && verify_uci_value "wireless.$radio.channel" "$expected" || verified=1
            ;;
        wifi.set_country)
            radio="$(json_get_string "$payload_file" '@.radio')"
            expected="$(json_get_string "$payload_file" '@.country')"
            radio="$(resolve_wifi_radio "$radio" || true)"
            [ -n "$radio" ] && verify_uci_value "wireless.$radio.country" "$expected" || verified=1
            ;;
        network.set_wan|network.set_lan)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface="$( [ "$command_type" = network.set_lan ] && printf lan || printf wan )"
            protocol="$(json_get_string "$payload_file" '@.protocol')"
            [ -n "$protocol" ] && verify_uci_value "network.$interface.proto" "$protocol" || verified=1
            if [ "$verified" = 0 ] && [ "$protocol" = static ]; then
                expected="$(json_get_string "$payload_file" '@.ip_address')"
                verify_uci_value "network.$interface.ipaddr" "$expected" || verified=1
            fi
            ;;
        dhcp.set_pool)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface=lan
            start="$(json_get_number "$payload_file" '@.start')"
            limit="$(json_get_number "$payload_file" '@.limit')"
            lease="$(json_get_string "$payload_file" '@.leasetime')"
            verify_uci_value "dhcp.$interface.start" "$start" && \
                verify_uci_value "dhcp.$interface.limit" "$limit" && \
                verify_uci_value "dhcp.$interface.leasetime" "$lease" || verified=1
            ;;
    esac
    rm -f "$payload_file"
    [ "$verified" = 0 ]
}
