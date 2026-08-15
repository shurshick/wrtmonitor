verify_command_postcondition() {
    command_type="$1"
    command_payload="$2"
    payload_file="/tmp/wrtmonitor-verify-payload-$$"
    printf '%s' "$command_payload" >"$payload_file"
    mode="$(postcondition_mode_for_command "$command_type" || true)"
    [ -n "$mode" ] || { rm -f "$payload_file"; return 1; }
    case "$mode" in
        result_payload|handler_result|service_or_connectivity_state)
            rm -f "$payload_file"
            return 0
            ;;
        package_state)
            verify_package_postcondition "$command_type" "$payload_file"
            verification_status=$?
            rm -f "$payload_file"
            return "$verification_status"
            ;;
        service_state)
            verify_service_postcondition "$command_type" "$payload_file"
            verification_status=$?
            rm -f "$payload_file"
            return "$verification_status"
            ;;
        module_state)
            verify_module_postcondition "$payload_file"
            verification_status=$?
            rm -f "$payload_file"
            return "$verification_status"
            ;;
    esac
    verified=0
    case "$command_type" in
        client.set_policy)
            verify_client_policy_postcondition "$payload_file" || verified=1
            ;;
        client.set_blocked)
            mac="$(json_get_string "$payload_file" '@.mac')"
            blocked="$(json_get_bool "$payload_file" '@.blocked')"
            ref="wrtmonitor_block_$(printf '%s' "$mac" | tr -d ':')"
            if [ "$blocked" = true ]; then
                verify_uci_value "firewall.$ref.src_mac" "$mac" \
                    && verify_uci_value "firewall.$ref.target" REJECT || verified=1
            else
                [ -z "$(uci -q get "firewall.$ref" 2>/dev/null || true)" ] || verified=1
            fi
            ;;
        dhcp.set_lease)
            mac="$(json_get_string "$payload_file" '@.mac')"
            expected_ip="$(json_get_string "$payload_file" '@.ip')"
            expected_name="$(json_get_string "$payload_file" '@.hostname')"
            lease_ref="$(resolve_dhcp_host_by_mac "$mac" || true)"
            [ -n "$lease_ref" ] \
                && verify_uci_value "dhcp.$lease_ref.mac" "$mac" \
                && verify_uci_value "dhcp.$lease_ref.ip" "$expected_ip" \
                && verify_uci_value "dhcp.$lease_ref.name" "$expected_name" \
                || verified=1
            ;;
        dhcp.delete_lease)
            mac="$(json_get_string "$payload_file" '@.mac')"
            [ -z "$(resolve_dhcp_host_by_mac "$mac" || true)" ] || verified=1
            ;;
        agent.set_interval)
            expected="$(json_get_number "$payload_file" '@.interval_seconds')"
            verify_uci_value "$CONFIG.interval" "$expected" || verified=1
            ;;
        agent.rotate_token)
            [ -n "$(device_token)" ] || verified=1
            ;;
        agent.set_auto_update)
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            expected=0
            [ "$enabled" = true ] && expected=1
            verify_uci_value "$CONFIG.auto_update" "$expected" || verified=1
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
            schedule_ref="$(find_wifi_schedule "$radio" || true)"
            if [ -n "$schedule_ref" ]; then
                expected=0
                [ "$enabled" = true ] && expected=1
                verify_uci_value "wrtmonitor.$schedule_ref.base_enabled" "$expected" || verified=1
            else
                expected=1
                [ "$enabled" = true ] && expected=0
                [ -n "$radio" ] && verify_uci_value "wireless.$radio.disabled" "$expected" || verified=1
            fi
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
        wifi.set_radio)
            radio="$(resolve_wifi_radio "$(json_get_string "$payload_file" '@.radio')" || true)"
            [ -n "$radio" ] || verified=1
            expected_enabled="$(json_get_bool "$payload_file" '@.enabled')"
            schedule_ref="$(find_wifi_schedule "$radio" || true)"
            if [ -n "$expected_enabled" ] && [ -n "$schedule_ref" ]; then
                expected=0; [ "$expected_enabled" = true ] && expected=1
                verify_uci_value "wrtmonitor.$schedule_ref.base_enabled" "$expected" || verified=1
            elif [ -n "$expected_enabled" ]; then
                expected=1; [ "$expected_enabled" = true ] && expected=0
                verify_uci_value "wireless.$radio.disabled" "$expected" || verified=1
            fi
            for field in channel country htmode; do
                expected="$(json_get_string "$payload_file" "@.$field")"
                [ -z "$expected" ] || verify_uci_value "wireless.$radio.$field" "$expected" || verified=1
            done
            expected="$(json_get_number "$payload_file" '@.txpower')"
            [ -z "$expected" ] || verify_uci_value "wireless.$radio.txpower" "$expected" || verified=1
            ;;
        wifi.set_schedule)
            radio="$(resolve_wifi_radio "$(json_get_string "$payload_file" '@.radio')" || true)"
            schedule_ref="$(find_wifi_schedule "$radio" || true)"
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            expected_enabled=0; [ "$enabled" = true ] && expected_enabled=1
            weekdays="$(jsonfilter -i "$payload_file" -e '@.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
            [ -n "$schedule_ref" ] \
                && verify_uci_value "wrtmonitor.$schedule_ref.radio" "$radio" \
                && verify_uci_value "wrtmonitor.$schedule_ref.enabled" "$expected_enabled" \
                && verify_uci_value "wrtmonitor.$schedule_ref.weekdays" "$weekdays" \
                && verify_uci_value "wrtmonitor.$schedule_ref.start" "$(json_get_string "$payload_file" '@.start')" \
                && verify_uci_value "wrtmonitor.$schedule_ref.stop" "$(json_get_string "$payload_file" '@.stop')" \
                || verified=1
            ;;
        network.set_wan)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface=wan
            protocol="$(json_get_string "$payload_file" '@.protocol')"
            [ -n "$protocol" ] && verify_uci_value "network.$interface.proto" "$protocol" || verified=1
            if [ "$verified" = 0 ] && [ "$protocol" = static ]; then
                expected="$(json_get_string "$payload_file" '@.ip_address')"
                verify_uci_value "network.$interface.ipaddr" "$expected" || verified=1
            fi
            ;;
        network.set_lan)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface=lan
            expected="$(json_get_string "$payload_file" '@.ip_address')"
            netmask="$(json_get_string "$payload_file" '@.netmask')"
            actual="$(uci -q get "network.$interface.ipaddr" 2>/dev/null || true)"
            actual_ip="${actual%%/*}"
            actual_prefix=""
            case "$actual" in
                */*) actual_prefix="${actual#*/}" ;;
                *) actual_prefix="$(ipv4_netmask_prefix "$(uci -q get "network.$interface.netmask" 2>/dev/null || true)" 2>/dev/null || true)" ;;
            esac
            expected_prefix="$(ipv4_netmask_prefix "$netmask" 2>/dev/null || true)"
            verify_uci_value "network.$interface.proto" static && \
                [ "$actual_ip" = "$expected" ] && \
                [ -n "$expected_prefix" ] && \
                [ "$actual_prefix" = "$expected_prefix" ] || verified=1
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
        dns.set_servers)
            expected="$(jsonfilter -i "$payload_file" -e '@.servers[*]' 2>/dev/null | sed '/^$/d' | sort)"
            actual="$(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null | tr ' ' '\n' | sed '/^$/d' | sort)"
            [ -n "$expected" ] && [ "$actual" = "$expected" ] || verified=1
            ;;
        network.set_ipv6)
            interface="$(json_get_string "$payload_file" '@.interface')"
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            if [ "$enabled" = true ]; then
                assignment="$(json_get_number "$payload_file" '@.assignment_length')"
                verify_uci_value "network.$interface.ip6assign" "$assignment" || verified=1
            else
                [ -z "$(uci -q get "network.$interface.ip6assign" 2>/dev/null || true)" ] || verified=1
            fi
            ;;
        network.set_vlan)
            section="$(json_get_string "$payload_file" '@.section')"
            device="$(json_get_string "$payload_file" '@.device')"
            vlan_id="$(json_get_number "$payload_file" '@.vlan_id')"
            if [ -z "$section" ]; then
                vlan_key="$(printf '%s' "$device" | tr -c 'A-Za-z0-9_' '_')"
                section="wrtmonitor_vlan_${vlan_key}_$vlan_id"
            fi
            verify_uci_value "network.$section.device" "$device" && \
                verify_uci_value "network.$section.vlan" "$vlan_id" || verified=1
            ;;
        network.set_multiwan)
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            primary="$(json_get_string "$payload_file" '@.primary_interface')"
            secondary="$(json_get_string "$payload_file" '@.secondary_interface')"
            expected_enabled=0
            [ "$enabled" = true ] && expected_enabled=1
            verify_uci_value mwan3.globals.enabled "$expected_enabled" && \
                verify_uci_value mwan3.wrtmonitor_primary.interface "$primary" && \
                verify_uci_value mwan3.wrtmonitor_secondary.interface "$secondary" && \
                verify_uci_value mwan3.wrtmonitor_default.use_policy wrtmonitor_policy || verified=1
            ;;
        *)
            verify_config_integrity_for_command "$command_type" || verified=1
            ;;
    esac
    rm -f "$payload_file"
    [ "$verified" = 0 ]
}
