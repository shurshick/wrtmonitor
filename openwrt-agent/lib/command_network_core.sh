# shellcheck disable=SC2034,SC2154
handle_network_core_command() {
    case "$command_type" in
        network.interfaces)
            result="$(network_summary_json)"
            ;;
        network.interface_restart)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            interface="$(json_get_string /tmp/wrtmonitor-command-payload '@.interface')"
            rm -f /tmp/wrtmonitor-command-payload
            case "$interface" in
                ""|*[!A-Za-z0-9_.-]*)
                    status="failed"
                    result="$(command_failed_result "invalid interface")"
                    ;;
                *)
                    if ifdown "$interface" >/dev/null 2>&1 && ifup "$interface" >/dev/null 2>&1; then
                        result="$(command_success_result "network interface restarted" "\"interface\":\"$(json_escape "$interface")\"")"
                    else
                        status="failed"
                        result="$(command_failed_result "failed to restart network interface")"
                    fi
                    ;;
            esac
            ;;
        network.restart)
            if /etc/init.d/network reload >/dev/null 2>&1; then
                result="$(command_success_result "network configuration reloaded")"
            else
                status="failed"
                result="$(command_failed_result "failed to reload network configuration")"
            fi
            ;;
        network.set_wan)
            payload_file="/tmp/wrtmonitor-command-payload"
            printf '%s' "$command_payload" >"$payload_file"
            wan_interface="$(json_get_string "$payload_file" '@.interface')"
            wan_protocol="$(json_get_string "$payload_file" '@.protocol')"
            wan_ip="$(json_get_string "$payload_file" '@.ip_address')"
            wan_netmask="$(json_get_string "$payload_file" '@.netmask')"
            wan_gateway="$(json_get_string "$payload_file" '@.gateway')"
            wan_username="$(json_get_string "$payload_file" '@.username')"
            wan_password="$(json_get_string "$payload_file" '@.password')"
            wan_mtu="$(json_get_number "$payload_file" '@.mtu')"
            wan_dns="$(jsonfilter -i "$payload_file" -e '@.dns[*]' 2>/dev/null || true)"
            rm -f "$payload_file"
            backup_file="$(backup_config network "$command_id" "$command_type" || true)"
            [ -n "$wan_interface" ] || wan_interface="wan"
            if [ -z "$backup_file" ]; then
                status="failed"; result="$(command_failed_result "failed to create network backup")"
            else
                uci set "network.$wan_interface=interface" && uci set "network.$wan_interface.proto=$wan_protocol" || status="failed"
                for option in ipaddr netmask gateway username password mtu dns peerdns; do uci -q delete "network.$wan_interface.$option" || true; done
                case "$wan_protocol" in
                    static)
                        uci set "network.$wan_interface.ipaddr=$wan_ip" && uci set "network.$wan_interface.netmask=$wan_netmask" || status="failed"
                        [ -z "$wan_gateway" ] || uci set "network.$wan_interface.gateway=$wan_gateway" || status="failed"
                        ;;
                    pppoe)
                        uci set "network.$wan_interface.username=$wan_username" && uci set "network.$wan_interface.password=$wan_password" || status="failed"
                        ;;
                    dhcp) ;;
                    *) status="failed" ;;
                esac
                [ -z "$wan_mtu" ] || uci set "network.$wan_interface.mtu=$wan_mtu" || status="failed"
                if [ -n "$wan_dns" ]; then
                    uci set "network.$wan_interface.peerdns=0" || status="failed"
                    printf '%s\n' "$wan_dns" | while IFS= read -r server; do [ -z "$server" ] || uci add_list "network.$wan_interface.dns=$server"; done
                fi
                uci commit network || status="failed"
                if [ "$status" = "done" ]; then
                    result="$(command_success_result "WAN configuration saved" "\"backup\":\"$(json_escape "$backup_file")\",\"interface\":\"$(json_escape "$wan_interface")\",\"protocol\":\"$(json_escape "$wan_protocol")\"")"
                    (sleep 2; ifdown "$wan_interface"; ifup "$wan_interface") >/dev/null 2>&1 &
                else result="$(command_failed_result "failed to configure WAN")"; fi
            fi
            ;;
        network.set_lan)
            payload_file="/tmp/wrtmonitor-command-payload"
            printf '%s' "$command_payload" >"$payload_file"
            lan_interface="$(json_get_string "$payload_file" '@.interface')"
            lan_ip="$(json_get_string "$payload_file" '@.ip_address')"
            lan_netmask="$(json_get_string "$payload_file" '@.netmask')"
            rm -f "$payload_file"
            [ -n "$lan_interface" ] || lan_interface="lan"
            lan_current_proto="$(uci -q get "network.$lan_interface.proto" 2>/dev/null || true)"
            lan_current_value="$(uci -q get "network.$lan_interface.ipaddr" 2>/dev/null || true)"
            lan_current_ip="${lan_current_value%%/*}"
            lan_current_prefix=""
            case "$lan_current_value" in
                */*) lan_current_prefix="${lan_current_value#*/}" ;;
                *) lan_current_prefix="$(ipv4_netmask_prefix "$(uci -q get "network.$lan_interface.netmask" 2>/dev/null || true)" 2>/dev/null || true)" ;;
            esac
            lan_expected_prefix="$(ipv4_netmask_prefix "$lan_netmask" 2>/dev/null || true)"
            if [ "$lan_current_proto" = static ] && [ "$lan_current_ip" = "$lan_ip" ] && [ -n "$lan_expected_prefix" ] && [ "$lan_current_prefix" = "$lan_expected_prefix" ]; then
                transaction_noop=1
                result="$(command_success_result "LAN configuration already matches" "\"interface\":\"$(json_escape "$lan_interface")\",\"ip_address\":\"$(json_escape "$lan_ip")\",\"changed\":false")"
            else
                backup_file="$(backup_config network "$command_id" "$command_type" || true)"
                if [ -n "$backup_file" ] && uci set "network.$lan_interface=interface" && uci set "network.$lan_interface.proto=static"; then
                    case "$lan_current_value" in
                        */*)
                            if uci set "network.$lan_interface.ipaddr=$lan_ip/$lan_expected_prefix"; then
                                uci -q delete "network.$lan_interface.netmask" || true
                            else
                                status=failed
                            fi
                            ;;
                        *)
                            if ! uci set "network.$lan_interface.ipaddr=$lan_ip" || ! uci set "network.$lan_interface.netmask=$lan_netmask"; then
                                status=failed
                            fi
                            ;;
                    esac
                    if [ "$status" = "done" ] && uci commit network; then
                        result="$(command_success_result "LAN configuration saved; connection address may change" "\"backup\":\"$(json_escape "$backup_file")\",\"interface\":\"$(json_escape "$lan_interface")\",\"ip_address\":\"$(json_escape "$lan_ip")\",\"changed\":true")"
                        (sleep 2; network_interface_cycle "$lan_interface") >/dev/null 2>&1 &
                    else status="failed"; result="$(command_failed_result "failed to commit LAN configuration")"; fi
                else status="failed"; result="$(command_failed_result "failed to configure LAN")"; fi
            fi
            ;;
        network.set_ipv6)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; ipv6_iface="$(json_get_string "$payload_file" '@.interface')"; ipv6_enabled="$(json_get_bool "$payload_file" '@.enabled')"; assignment="$(json_get_number "$payload_file" '@.assignment_length')"; ra_mode="$(json_get_string "$payload_file" '@.ra')"; dhcpv6_mode="$(json_get_string "$payload_file" '@.dhcpv6')"; ndp_mode="$(json_get_string "$payload_file" '@.ndp')"; rm -f "$payload_file"
            if [ "$ipv6_enabled" = true ]; then uci set "network.$ipv6_iface.ip6assign=$assignment"; uci set "dhcp.$ipv6_iface.ra=$ra_mode"; uci set "dhcp.$ipv6_iface.dhcpv6=$dhcpv6_mode"; uci set "dhcp.$ipv6_iface.ndp=$ndp_mode"; else uci -q delete "network.$ipv6_iface.ip6assign" || true; uci set "dhcp.$ipv6_iface.ra=disabled"; uci set "dhcp.$ipv6_iface.dhcpv6=disabled"; uci set "dhcp.$ipv6_iface.ndp=disabled"; fi
            if uci commit network && uci commit dhcp && service_action network reload 30 >/dev/null 2>&1 && service_action odhcpd restart 20 >/dev/null 2>&1; then result="$(command_success_result "IPv6 configuration updated")"; else status=failed; result="$(command_failed_result "failed to update IPv6")"; fi
            ;;
        *) return 1 ;;
    esac
    return 0
}
