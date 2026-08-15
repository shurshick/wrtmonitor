# shellcheck disable=SC2034,SC2154
handle_network_topology_command() {
    case "$command_type" in
        network.set_segment)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"
            segment_name="$(json_get_string "$payload_file" '@.name')"; segment_proto="$(json_get_string "$payload_file" '@.protocol')"; segment_device="$(json_get_string "$payload_file" '@.device')"; segment_bridge_ref="$(json_get_string "$payload_file" '@.bridge_section')"; segment_ip="$(json_get_string "$payload_file" '@.ip_address')"; segment_netmask="$(json_get_string "$payload_file" '@.netmask')"; segment_enabled="$(json_get_bool "$payload_file" '@.enabled')"; segment_bridge="$(json_get_bool "$payload_file" '@.bridge')"; segment_stp="$(json_get_bool "$payload_file" '@.stp')"; segment_igmp="$(json_get_bool "$payload_file" '@.igmp_snooping')"; segment_dhcp="$(json_get_bool "$payload_file" '@.dhcp_enabled')"; segment_dhcp_start="$(json_get_number "$payload_file" '@.dhcp_start')"; segment_dhcp_limit="$(json_get_number "$payload_file" '@.dhcp_limit')"; segment_dhcp_lease="$(json_get_string "$payload_file" '@.dhcp_leasetime')"; segment_policy="$(json_get_string "$payload_file" '@.policy')"; segment_ports="$(jsonfilter -i "$payload_file" -e '@.ports[*]' 2>/dev/null || true)"; rm -f "$payload_file"
            case "$segment_name:$segment_proto:$segment_policy" in
                *[!A-Za-z0-9_:-]*|:*|*:|*::*) status=failed; result="$(command_failed_result "invalid segment configuration")" ;;
                *)
                    [ -n "$segment_bridge_ref" ] || segment_bridge_ref="wrtmonitor_bridge_$segment_name"; [ -n "$segment_device" ] || segment_device="br-$segment_name"
                    if [ "$segment_bridge" = true ]; then
                        uci set "network.$segment_bridge_ref=device"; uci set "network.$segment_bridge_ref.name=$segment_device"; uci set "network.$segment_bridge_ref.type=bridge"; uci set "network.$segment_bridge_ref.stp=$( [ "$segment_stp" = true ] && printf 1 || printf 0 )"; uci set "network.$segment_bridge_ref.igmp_snooping=$( [ "$segment_igmp" = true ] && printf 1 || printf 0 )"; uci -q delete "network.$segment_bridge_ref.ports" || true
                        printf '%s\n' "$segment_ports" | while IFS= read -r port; do case "$port" in ''|*[!A-Za-z0-9_.@-]*) exit 1 ;; esac; uci add_list "network.$segment_bridge_ref.ports=$port"; done || status=failed
                    else
                        case "$segment_bridge_ref" in wrtmonitor_bridge_*) uci -q delete "network.$segment_bridge_ref" || true ;; esac
                    fi
                    uci set "network.$segment_name=interface"; uci set "network.$segment_name.proto=$segment_proto"; uci set "network.$segment_name.disabled=$( [ "$segment_enabled" = true ] && printf 0 || printf 1 )"; uci -q delete "network.$segment_name.ipaddr" || true; uci -q delete "network.$segment_name.netmask" || true; uci -q delete "network.$segment_name.device" || true
                    [ -z "$segment_device" ] || uci set "network.$segment_name.device=$segment_device"
                    if [ "$segment_proto" = static ]; then uci set "network.$segment_name.ipaddr=$segment_ip"; uci set "network.$segment_name.netmask=$segment_netmask"; fi
                    uci set "dhcp.$segment_name=dhcp"; uci set "dhcp.$segment_name.interface=$segment_name"
                    if [ "$segment_dhcp" = true ]; then uci set "dhcp.$segment_name.ignore=0"; uci set "dhcp.$segment_name.start=$segment_dhcp_start"; uci set "dhcp.$segment_name.limit=$segment_dhcp_limit"; uci set "dhcp.$segment_name.leasetime=$segment_dhcp_lease"; else uci set "dhcp.$segment_name.ignore=1"; fi
                    case "$segment_name" in
                        lan|wan|wan6|loopback) ;;
                        *)
                            segment_zone="wrtmonitor_zone_$segment_name"; segment_forward="wrtmonitor_forward_$segment_name"; segment_dns_rule="wrtmonitor_dns_$segment_name"; segment_dhcp_rule="wrtmonitor_dhcp_$segment_name"
                            uci set "firewall.$segment_zone=zone"; uci set "firewall.$segment_zone.name=$segment_name"; uci -q delete "firewall.$segment_zone.network" || true; uci add_list "firewall.$segment_zone.network=$segment_name"; uci set "firewall.$segment_zone.output=ACCEPT"; uci set "firewall.$segment_zone.forward=REJECT"; uci set "firewall.$segment_zone.input=$( [ "$segment_policy" = trusted ] && printf ACCEPT || printf REJECT )"
                            uci set "firewall.$segment_dns_rule=rule"; uci set "firewall.$segment_dns_rule.name=WrtMonitor DNS $segment_name"; uci set "firewall.$segment_dns_rule.src=$segment_name"; uci set "firewall.$segment_dns_rule.dest_port=53"; uci set "firewall.$segment_dns_rule.proto=tcp udp"; uci set "firewall.$segment_dns_rule.target=ACCEPT"
                            uci set "firewall.$segment_dhcp_rule=rule"; uci set "firewall.$segment_dhcp_rule.name=WrtMonitor DHCP $segment_name"; uci set "firewall.$segment_dhcp_rule.src=$segment_name"; uci set "firewall.$segment_dhcp_rule.dest_port=67-68"; uci set "firewall.$segment_dhcp_rule.proto=udp"; uci set "firewall.$segment_dhcp_rule.family=ipv4"; uci set "firewall.$segment_dhcp_rule.target=ACCEPT"
                            if [ "$segment_policy" = isolated ]; then uci -q delete "firewall.$segment_forward" || true; else uci set "firewall.$segment_forward=forwarding"; uci set "firewall.$segment_forward.src=$segment_name"; uci set "firewall.$segment_forward.dest=wan"; fi
                            ;;
                    esac
                    if [ "$status" = "done" ] && uci commit network && uci commit dhcp && uci commit firewall && service_action network reload 30 >/dev/null 2>&1 && service_action dnsmasq restart 20 >/dev/null 2>&1 && service_action firewall reload 20 >/dev/null 2>&1; then result="$(command_success_result "network segment updated" "\"segment\":\"$(json_escape "$segment_name")\"")"; else status=failed; result="$(command_failed_result "failed to update network segment")"; fi
                    ;;
            esac
            ;;
        network.delete_segment)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; segment_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"
            case "$segment_name" in ''|lan|wan|wan6|loopback|*[!A-Za-z0-9_-]*) status=failed; result="$(command_failed_result "core or invalid segment cannot be deleted")" ;; *) uci -q delete "network.$segment_name" || true; uci -q delete "network.wrtmonitor_bridge_$segment_name" || true; uci -q delete "dhcp.$segment_name" || true; uci -q delete "firewall.wrtmonitor_zone_$segment_name" || true; uci -q delete "firewall.wrtmonitor_forward_$segment_name" || true; uci -q delete "firewall.wrtmonitor_dns_$segment_name" || true; uci -q delete "firewall.wrtmonitor_dhcp_$segment_name" || true; if uci commit network && uci commit dhcp && uci commit firewall && service_action network reload 30 >/dev/null 2>&1 && service_action dnsmasq restart 20 >/dev/null 2>&1 && service_action firewall reload 20 >/dev/null 2>&1; then result="$(command_success_result "network segment deleted")"; else status=failed; result="$(command_failed_result "failed to delete network segment")"; fi ;; esac
            ;;
        network.set_vlan)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; vlan_section="$(json_get_string "$payload_file" '@.section')"; vlan_device="$(json_get_string "$payload_file" '@.device')"; vlan_id="$(json_get_number "$payload_file" '@.vlan_id')"; vlan_ports="$(jsonfilter -i "$payload_file" -e '@.ports[*]' 2>/dev/null || true)"; rm -f "$payload_file"
            if [ -z "$vlan_section" ]; then vlan_key="$(printf '%s' "$vlan_device" | tr -c 'A-Za-z0-9_' '_')"; vlan_section="wrtmonitor_vlan_${vlan_key}_$vlan_id"; fi
            case "$vlan_section" in ''|*[!A-Za-z0-9_.@\[\]-]*) status=failed ;; esac
            case "$vlan_device" in ''|*[!A-Za-z0-9_.@:-]*) status=failed ;; esac
            case "$vlan_id" in ''|*[!0-9]*|0) status=failed ;; esac
            if [ "$status" = failed ]; then
                result="$(command_failed_result "invalid VLAN configuration")"
            else
                uci set "network.$vlan_section=bridge-vlan"; uci set "network.$vlan_section.device=$vlan_device"; uci set "network.$vlan_section.vlan=$vlan_id"; uci -q delete "network.$vlan_section.ports" || true
                printf '%s\n' "$vlan_ports" | while IFS= read -r port; do case "$port" in ''|*[!A-Za-z0-9_.@:\*-]*) exit 1 ;; esac; uci add_list "network.$vlan_section.ports=$port"; done || status=failed
                for device_ref in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=device$/\1/p'); do [ "$(uci -q get "network.$device_ref.name" 2>/dev/null || true)" != "$vlan_device" ] || uci set "network.$device_ref.vlan_filtering=1"; done
                if [ "$status" = "done" ] && uci commit network && service_action network reload 30 >/dev/null 2>&1; then result="$(command_success_result "bridge VLAN updated" "\"section\":\"$(json_escape "$vlan_section")\",\"vlan_id\":$vlan_id")"; else status=failed; result="$(command_failed_result "failed to update bridge VLAN")"; fi
            fi
            ;;
        network.delete_vlan)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; vlan_section="$(json_get_string "$payload_file" '@.section')"; rm -f "$payload_file"
            case "$vlan_section" in ''|*[!A-Za-z0-9_.@\[\]-]*) status=failed; result="$(command_failed_result "invalid VLAN section")" ;; *) if uci -q delete "network.$vlan_section" && uci commit network && service_action network reload 30 >/dev/null 2>&1; then result="$(command_success_result "bridge VLAN deleted")"; else status=failed; result="$(command_failed_result "VLAN section not found")"; fi ;; esac
            ;;
        network.set_multiwan)
            payload_file=/tmp/wrtmonitor-command-payload
            printf '%s' "$command_payload" >"$payload_file"
            multi_enabled="$(json_get_bool "$payload_file" '@.enabled')"
            primary="$(json_get_string "$payload_file" '@.primary_interface')"
            secondary="$(json_get_string "$payload_file" '@.secondary_interface')"
            primary_metric="$(json_get_number "$payload_file" '@.primary_metric')"
            secondary_metric="$(json_get_number "$payload_file" '@.secondary_metric')"
            track_ips="$(jsonfilter -i "$payload_file" -e '@.track_ips[*]' 2>/dev/null || true)"
            check_interval="$(json_get_number "$payload_file" '@.check_interval')"
            failure_interval="$(json_get_number "$payload_file" '@.failure_interval')"
            recovery_interval="$(json_get_number "$payload_file" '@.recovery_interval')"
            rm -f "$payload_file"
            backup_file="$(backup_config mwan3 "$command_id" "$command_type" || true)"
            if [ -z "$backup_file" ]; then
                status=failed
                result="$(command_failed_result "failed to create mwan3 backup")"
            else
            for monitored_interface in "$primary" "$secondary"; do
                uci set "mwan3.$monitored_interface=interface"
                uci set "mwan3.$monitored_interface.enabled=1"
                uci set "mwan3.$monitored_interface.family=ipv4"
                uci set "mwan3.$monitored_interface.reliability=1"
                uci set "mwan3.$monitored_interface.count=1"
                uci set "mwan3.$monitored_interface.timeout=2"
                uci set "mwan3.$monitored_interface.interval=$check_interval"
                uci set "mwan3.$monitored_interface.failure_interval=$check_interval"
                uci set "mwan3.$monitored_interface.recovery_interval=$check_interval"
                uci set "mwan3.$monitored_interface.down=$failure_interval"
                uci set "mwan3.$monitored_interface.up=$recovery_interval"
                uci -q delete "mwan3.$monitored_interface.track_ip" || true
                printf '%s\n' "$track_ips" | while IFS= read -r track_ip; do
                    [ -z "$track_ip" ] || uci add_list "mwan3.$monitored_interface.track_ip=$track_ip"
                done
            done
            uci set mwan3.wrtmonitor_primary=member; uci set "mwan3.wrtmonitor_primary.interface=$primary"; uci set "mwan3.wrtmonitor_primary.metric=$primary_metric"; uci set mwan3.wrtmonitor_primary.weight=1
            uci set mwan3.wrtmonitor_secondary=member; uci set "mwan3.wrtmonitor_secondary.interface=$secondary"; uci set "mwan3.wrtmonitor_secondary.metric=$secondary_metric"; uci set mwan3.wrtmonitor_secondary.weight=1
            uci set mwan3.wrtmonitor_policy=policy; uci -q delete mwan3.wrtmonitor_policy.use_member || true; uci add_list mwan3.wrtmonitor_policy.use_member=wrtmonitor_primary; uci add_list mwan3.wrtmonitor_policy.use_member=wrtmonitor_secondary; uci set "mwan3.globals.enabled=$( [ "$multi_enabled" = true ] && echo 1 || echo 0 )"
            uci set mwan3.wrtmonitor_default=rule
            uci set mwan3.wrtmonitor_default.dest_ip=0.0.0.0/0
            uci set mwan3.wrtmonitor_default.use_policy=wrtmonitor_policy
            if uci commit mwan3 && service_action mwan3 restart 20 >/dev/null 2>&1; then
                result="$(command_success_result "multi-WAN policy updated" "\"backup\":\"$(json_escape "$backup_file")\"")"
            else
                status=failed
                result="$(command_failed_result "failed to update multi-WAN")"
            fi
            fi
            ;;
        network.set_route)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; route_section="$(json_get_string "$payload_file" '@.section')"; route_name="$(json_get_string "$payload_file" '@.name')"; route_iface="$(json_get_string "$payload_file" '@.interface')"; route_target="$(json_get_string "$payload_file" '@.target')"; route_gateway="$(json_get_string "$payload_file" '@.gateway')"; route_metric="$(json_get_number "$payload_file" '@.metric')"; rm -f "$payload_file"; route_ref="${route_section:-wrtmonitor_route_$route_name}"; case "$route_target" in *:*) route_type=route6 ;; *) route_type=route ;; esac
            uci set "network.$route_ref=$route_type"; uci set "network.$route_ref.wrtmonitor_name=$route_name"; uci set "network.$route_ref.interface=$route_iface"; uci set "network.$route_ref.target=$route_target"; uci -q delete "network.$route_ref.gateway" || true; [ -z "$route_gateway" ] || uci set "network.$route_ref.gateway=$route_gateway"; uci set "network.$route_ref.metric=$route_metric"
            if uci commit network && service_action network reload 30 >/dev/null 2>&1; then result="$(command_success_result "static route updated")"; else status=failed; result="$(command_failed_result "failed to update route")"; fi
            ;;
        network.delete_route)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; route_section="$(json_get_string "$payload_file" '@.section')"; route_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; route_ref="${route_section:-wrtmonitor_route_$route_name}"
            if uci -q delete "network.$route_ref" && uci commit network && service_action network reload 30 >/dev/null 2>&1; then result="$(command_success_result "static route deleted")"; else status=failed; result="$(command_failed_result "route not found")"; fi
            ;;
        network.set_ddns)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; ddns_name="$(json_get_string "$payload_file" '@.name')"; ddns_enabled="$(json_get_bool "$payload_file" '@.enabled')"; provider="$(json_get_string "$payload_file" '@.provider')"; domain="$(json_get_string "$payload_file" '@.domain')"; ddns_user="$(json_get_string "$payload_file" '@.username')"; ddns_password="$(json_get_string "$payload_file" '@.password')"; ddns_iface="$(json_get_string "$payload_file" '@.interface')"; rm -f "$payload_file"; ddns_ref="wrtmonitor_$ddns_name"
            uci set "ddns.$ddns_ref=service"; uci set "ddns.$ddns_ref.enabled=$( [ "$ddns_enabled" = true ] && echo 1 || echo 0 )"; uci set "ddns.$ddns_ref.service_name=$provider"; uci set "ddns.$ddns_ref.domain=$domain"; uci set "ddns.$ddns_ref.username=$ddns_user"; uci set "ddns.$ddns_ref.password=$ddns_password"; uci set "ddns.$ddns_ref.interface=$ddns_iface"; uci set "ddns.$ddns_ref.ip_source=network"; uci set "ddns.$ddns_ref.ip_network=$ddns_iface"
            if uci commit ddns && service_action ddns restart 20 >/dev/null 2>&1; then result="$(command_success_result "DDNS service updated")"; else status=failed; result="$(command_failed_result "failed to update DDNS")"; fi
            ;;
        network.set_upnp)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; upnp_enabled="$(json_get_bool "$payload_file" '@.enabled')"; secure_mode="$(json_get_bool "$payload_file" '@.secure_mode')"; rm -f "$payload_file"; uci set "upnpd.config.enabled=$( [ "$upnp_enabled" = true ] && echo 1 || echo 0 )"; uci set "upnpd.config.secure_mode=$( [ "$secure_mode" = true ] && echo 1 || echo 0 )"
            if uci commit upnpd && service_action miniupnpd restart 20 >/dev/null 2>&1; then result="$(command_success_result "UPnP configuration updated")"; else status=failed; result="$(command_failed_result "failed to update UPnP")"; fi
            ;;
        *) return 1 ;;
    esac
    return 0
}
