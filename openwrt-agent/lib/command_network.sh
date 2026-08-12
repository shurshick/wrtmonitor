# shellcheck disable=SC2034,SC2154
handle_network_command() {
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
            result="$(command_success_result "network restart scheduled")"
            (sleep 2; /etc/init.d/network restart) >/dev/null 2>&1 &
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
        dhcp.set_lease)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            lease_mac="$(json_get_string /tmp/wrtmonitor-command-payload '@.mac')"
            lease_ip="$(json_get_string /tmp/wrtmonitor-command-payload '@.ip')"
            lease_hostname="$(json_get_string /tmp/wrtmonitor-command-payload '@.hostname')"
            rm -f /tmp/wrtmonitor-command-payload
            backup_file="$(backup_config dhcp "$command_id" "$command_type" || true)"
            lease_name="wrtmonitor_$(printf '%s' "$lease_mac" | tr -d ':')"
            lease_ref="$(resolve_dhcp_host_by_mac "$lease_mac" || true)"
            [ -n "$lease_ref" ] || lease_ref="$lease_name"
            if [ -z "$backup_file" ]; then
                status="failed"
                result="$(command_failed_result "failed to create DHCP config backup")"
            elif uci set "dhcp.$lease_ref=host" \
                && uci set "dhcp.$lease_ref.mac=$lease_mac" \
                && uci set "dhcp.$lease_ref.ip=$lease_ip" \
                && uci set "dhcp.$lease_ref.name=$lease_hostname" \
                && uci commit dhcp \
                && service_action dnsmasq restart 20 >/dev/null 2>&1; then
                result="$(command_success_result "static DHCP lease saved" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$lease_mac")\",\"ip\":\"$(json_escape "$lease_ip")\"")"
            else
                status="failed"
                result="$(command_failed_result "failed to save static DHCP lease")"
            fi
            ;;
        dhcp.delete_lease)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            lease_mac="$(json_get_string /tmp/wrtmonitor-command-payload '@.mac')"
            rm -f /tmp/wrtmonitor-command-payload
            backup_file="$(backup_config dhcp "$command_id" "$command_type" || true)"
            lease_ref="$(resolve_dhcp_host_by_mac "$lease_mac" || true)"
            if [ -z "$backup_file" ]; then
                status="failed"
                result="$(command_failed_result "failed to create DHCP config backup")"
            elif [ -n "$lease_ref" ] && uci -q delete "dhcp.$lease_ref" && uci commit dhcp && service_action dnsmasq restart 20 >/dev/null 2>&1; then
                result="$(command_success_result "static DHCP lease deleted" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$lease_mac")\"")"
            else
                status="failed"
                result="$(command_failed_result "static DHCP lease not found")"
            fi
            ;;
        dhcp.set_pool)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            pool_interface="$(json_get_string "$payload_file" '@.interface')"; pool_start="$(json_get_number "$payload_file" '@.start')"; pool_limit="$(json_get_number "$payload_file" '@.limit')"; pool_leasetime="$(json_get_string "$payload_file" '@.leasetime')"; rm -f "$payload_file"
            [ -n "$pool_interface" ] || pool_interface="lan"
            backup_file="$(backup_config dhcp "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && uci set "dhcp.$pool_interface=dhcp" && uci set "dhcp.$pool_interface.interface=$pool_interface" && uci set "dhcp.$pool_interface.start=$pool_start" && uci set "dhcp.$pool_interface.limit=$pool_limit" && uci set "dhcp.$pool_interface.leasetime=$pool_leasetime" && uci commit dhcp && service_action dnsmasq restart 20 >/dev/null 2>&1; then
                result="$(command_success_result "DHCP pool updated" "\"backup\":\"$(json_escape "$backup_file")\"")"
            else status="failed"; result="$(command_failed_result "failed to update DHCP pool")"; fi
            ;;
        dns.set_servers)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; dns_servers="$(jsonfilter -i "$payload_file" -e '@.servers[*]' 2>/dev/null || true)"; rm -f "$payload_file"
            backup_file="$(backup_config dhcp "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && [ -n "$dns_servers" ]; then
                uci -q delete 'dhcp.@dnsmasq[0].server' || true
                printf '%s\n' "$dns_servers" | while IFS= read -r server; do [ -z "$server" ] || uci add_list "dhcp.@dnsmasq[0].server=$server"; done
                if uci commit dhcp && service_action dnsmasq restart 20 >/dev/null 2>&1; then result="$(command_success_result "DNS servers updated" "\"backup\":\"$(json_escape "$backup_file")\"")"; else status="failed"; result="$(command_failed_result "DNS configuration was saved, but dnsmasq did not restart within 20 seconds")"; fi
            else status="failed"; result="$(command_failed_result "DNS servers or backup are unavailable")"; fi
            ;;
        dns.install_encrypted|dns.install_dot|dns.install_doh)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; dns_mode="$(json_get_string "$payload_file" '@.mode')"; rm -f "$payload_file"
            [ -n "$dns_mode" ] || case "$command_type" in dns.install_dot) dns_mode="dot" ;; dns.install_doh) dns_mode="doh" ;; esac
            case "$dns_mode" in dot) dns_package=stubby ;; doh) dns_package=https-dns-proxy ;; *) dns_package="" ;; esac
            backup_plain_dns
            encrypted_dns_install_ok=0
            if [ -n "$dns_package" ] && package_refresh_indexes >/dev/null 2>&1 && package_apply install "$dns_package" >/dev/null 2>&1 \
                && { [ "$dns_mode" != dot ] || configure_dot cloudflare false; } \
                && { [ "$dns_mode" != doh ] || configure_doh cloudflare false; } \
                && dns_resolution_works; then
                encrypted_dns_install_ok=1
            else
                case "$dns_mode" in
                    dot) configure_dot cloudflare false >/dev/null 2>&1 || true ;;
                    doh) configure_doh cloudflare false >/dev/null 2>&1 || true ;;
                esac
                restore_plain_dns
                service_action dnsmasq restart 20 >/dev/null 2>&1 || true
            fi
            if [ "$encrypted_dns_install_ok" = 1 ]; then
                result="$(command_success_result "encrypted DNS package installed" "\"mode\":\"$(json_escape "$dns_mode")\",\"package\":\"$(json_escape "$dns_package")\"")"
            else status="failed"; result="$(command_failed_result "encrypted DNS package installation did not preserve working name resolution" "post_condition_failed")"; fi
            ;;
        dns.set_encrypted|dns.set_dot|dns.set_doh)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; dns_mode="$(json_get_string "$payload_file" '@.mode')"; dns_provider="$(json_get_string "$payload_file" '@.provider')"; dns_enabled="$(json_get_bool "$payload_file" '@.enabled')"; rm -f "$payload_file"
            [ -n "$dns_mode" ] || case "$command_type" in dns.set_dot) dns_mode="dot" ;; dns.set_doh) dns_mode="doh" ;; esac
            case "$dns_mode" in dot) configure_dns_result=configure_dot ;; doh) configure_dns_result=configure_doh ;; *) configure_dns_result="" ;; esac
            if [ -n "$configure_dns_result" ] && "$configure_dns_result" "$dns_provider" "$dns_enabled"; then
                result="$(command_success_result "encrypted DNS configuration applied" "\"mode\":\"$(json_escape "$dns_mode")\",\"provider\":\"$(json_escape "$dns_provider")\",\"enabled\":$dns_enabled")"
            else status="failed"; result="$(command_failed_result "failed to configure encrypted DNS")"; fi
            ;;
        client.set_blocked)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; client_mac="$(json_get_string "$payload_file" '@.mac')"; client_blocked="$(json_get_bool "$payload_file" '@.blocked')"; rm -f "$payload_file"
            client_ref="wrtmonitor_block_$(printf '%s' "$client_mac" | tr -d ':')"; backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -z "$backup_file" ]; then status="failed"; result="$(command_failed_result "failed to create firewall backup")"
            elif [ "$client_blocked" = "true" ]; then
                if uci set "firewall.$client_ref=rule" && uci set "firewall.$client_ref.name=WrtMonitor block $client_mac" && uci set "firewall.$client_ref.src=lan" && uci set "firewall.$client_ref.dest=wan" && uci set "firewall.$client_ref.src_mac=$client_mac" && uci set "firewall.$client_ref.target=REJECT" && uci commit firewall && service_action firewall reload 20 >/dev/null 2>&1; then result="$(command_success_result "client internet access blocked" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\"")"; else status="failed"; result="$(command_failed_result "failed to block client")"; fi
            else
                uci -q delete "firewall.$client_ref" || true
                if uci commit firewall && service_action firewall reload 20 >/dev/null 2>&1; then result="$(command_success_result "client internet access restored" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\"")"; else status="failed"; result="$(command_failed_result "failed to unblock client")"; fi
            fi
            ;;
        client.set_policy)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            client_mac="$(json_get_string "$payload_file" '@.mac')"
            client_blocked="$(json_get_bool "$payload_file" '@.blocked')"
            schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
            schedule_start="$(json_get_string "$payload_file" '@.schedule.start')"
            schedule_stop="$(json_get_string "$payload_file" '@.schedule.stop')"
            schedule_days="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
            qos_priority="$(json_get_string "$payload_file" '@.qos.priority')"
            download_kbps="$(json_get_number "$payload_file" '@.qos.download_kbps')"
            upload_kbps="$(json_get_number "$payload_file" '@.qos.upload_kbps')"
            dns_provider="$(json_get_string "$payload_file" '@.dns.provider')"
            rm -f "$payload_file"
            [ -n "$qos_priority" ] || qos_priority=normal
            [ -n "$download_kbps" ] || download_kbps=0
            [ -n "$upload_kbps" ] || upload_kbps=0
            [ -n "$dns_provider" ] || dns_provider=none
            client_suffix="$(client_policy_suffix "$client_mac")"
            client_ref="wrtmonitor_policy_$client_suffix"
            qos_ref="wrtmonitor_qos_$client_suffix"
            dns_ref="wrtmonitor_dns_$client_suffix"
            dot_ref="wrtmonitor_dot_$client_suffix"
            shaping_device="$(client_policy_lan_device)"
            shaping_pref="$(client_policy_filter_pref "$client_mac")"
            backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if { [ "$download_kbps" -gt 0 ] || [ "$upload_kbps" -gt 0 ]; } && ! traffic_control_healthy; then
                status="failed"; result="$(command_failed_result "client speed limits require tc-full, kmod-sched-flower and kmod-sched-act-police" "dependency_missing" true)"
            elif [ -z "$backup_file" ]; then
                status="failed"; result="$(command_failed_result "failed to create firewall backup")"
            else
                uci -q delete "firewall.$client_ref" || true
                uci -q delete "firewall.$qos_ref" || true
                uci -q delete "firewall.$dns_ref" || true
                uci -q delete "firewall.$dot_ref" || true
                if [ "$client_blocked" = "true" ] || [ "$schedule_enabled" = "true" ]; then
                    uci set "firewall.$client_ref=rule"
                    uci set "firewall.$client_ref.name=WrtMonitor policy $client_mac"
                    uci set "firewall.$client_ref.src=lan"
                    uci set "firewall.$client_ref.dest=wan"
                    uci set "firewall.$client_ref.src_mac=$client_mac"
                    uci set "firewall.$client_ref.target=REJECT"
                    if [ "$client_blocked" != "true" ] && [ "$schedule_enabled" = "true" ]; then
                        [ -z "$schedule_days" ] || uci set "firewall.$client_ref.weekdays=$schedule_days"
                        [ -z "$schedule_start" ] || uci set "firewall.$client_ref.start_time=$schedule_start"
                        [ -z "$schedule_stop" ] || uci set "firewall.$client_ref.stop_time=$schedule_stop"
                    fi
                fi
                if [ "$qos_priority" != "normal" ]; then
                    case "$qos_priority" in low) policy_mark="0x10" ;; high) policy_mark="0x30" ;; realtime) policy_mark="0x40" ;; *) policy_mark="0x20" ;; esac
                    uci set "firewall.$qos_ref=rule"
                    uci set "firewall.$qos_ref.name=WrtMonitor priority $client_mac"
                    uci set "firewall.$qos_ref.src=lan"
                    uci set "firewall.$qos_ref.src_mac=$client_mac"
                    uci set "firewall.$qos_ref.target=MARK"
                    uci set "firewall.$qos_ref.set_mark=$policy_mark"
                fi
                case "$dns_provider" in
                    cloudflare-security) policy_dns="1.1.1.2" ;;
                    cloudflare-family) policy_dns="1.1.1.3" ;;
                    none|"") policy_dns="" ;;
                    *) status="failed"; result="$(command_failed_result "unsupported client DNS policy")" ;;
                esac
                if [ "$status" = "done" ] && [ -n "$policy_dns" ]; then
                    uci set "firewall.$dns_ref=redirect"
                    uci set "firewall.$dns_ref.name=WrtMonitor DNS policy $client_mac"
                    uci set "firewall.$dns_ref.src=lan"
                    uci set "firewall.$dns_ref.src_mac=$client_mac"
                    uci set "firewall.$dns_ref.proto=tcp udp"
                    uci set "firewall.$dns_ref.src_dport=53"
                    uci set "firewall.$dns_ref.dest_ip=$policy_dns"
                    uci set "firewall.$dns_ref.dest_port=53"
                    uci set "firewall.$dns_ref.target=DNAT"
                    uci set "firewall.$dot_ref=rule"
                    uci set "firewall.$dot_ref.name=WrtMonitor block DoT $client_mac"
                    uci set "firewall.$dot_ref.src=lan"
                    uci set "firewall.$dot_ref.dest=wan"
                    uci set "firewall.$dot_ref.src_mac=$client_mac"
                    uci set "firewall.$dot_ref.proto=tcp udp"
                    uci set "firewall.$dot_ref.dest_port=853"
                    uci set "firewall.$dot_ref.target=REJECT"
                fi
                if [ "$status" = "done" ] \
                    && client_policy_save_state "$client_mac" "$client_blocked" "$schedule_enabled" "$schedule_days" "$schedule_start" "$schedule_stop" "$qos_priority" "$download_kbps" "$upload_kbps" "$dns_provider" "$shaping_device" "$shaping_pref" \
                    && uci commit firewall \
                    && uci commit wrtmonitor \
                    && service_action firewall reload 20 >/dev/null 2>&1 \
                    && client_policy_apply_runtime_limits "$client_mac" "$download_kbps" "$upload_kbps" "$shaping_device" "$shaping_pref"; then
                    observed="$(client_policy_observed_json "$client_mac")"
                    result="$(command_success_result "client policy applied" "\"backup\":\"$(json_escape "$backup_file")\",\"observed\":$observed")"
                else
                    status="failed"; result="$(command_failed_result "client policy could not be applied or verified" "post_condition_failed")"
                fi
            fi
            ;;
        qos.set_sqm)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            sqm_enabled="$(json_get_bool "$payload_file" '@.enabled')"
            sqm_interface="$(json_get_string "$payload_file" '@.interface')"
            sqm_download="$(json_get_number "$payload_file" '@.download_kbps')"
            sqm_upload="$(json_get_number "$payload_file" '@.upload_kbps')"
            sqm_qdisc="$(json_get_string "$payload_file" '@.qdisc')"
            sqm_script="$(json_get_string "$payload_file" '@.script')"
            sqm_profile="$(json_get_string "$payload_file" '@.profile')"
            sqm_qdisc_options="$(json_get_string "$payload_file" '@.qdisc_options')"
            sqm_schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
            sqm_schedule_days="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
            sqm_schedule_start="$(json_get_string "$payload_file" '@.schedule.start')"
            sqm_schedule_stop="$(json_get_string "$payload_file" '@.schedule.stop')"
            rm -f "$payload_file"
            [ -n "$sqm_qdisc" ] || sqm_qdisc="cake"
            [ -n "$sqm_script" ] || sqm_script="piece_of_cake.qos"
            sqm_backup="$(backup_config sqm "$command_id" "$command_type" || true)"
            if [ -z "$sqm_backup" ]; then
                status="failed"; result="$(command_failed_result "failed to create SQM backup")"
            elif uci set sqm.wrtmonitor=queue \
                && uci set "sqm.wrtmonitor.enabled=$( [ "$sqm_enabled" = "true" ] && printf 1 || printf 0 )" \
                && uci set "sqm.wrtmonitor.interface=$sqm_interface" \
                && uci set "sqm.wrtmonitor.download=$sqm_download" \
                && uci set "sqm.wrtmonitor.upload=$sqm_upload" \
                && uci set "sqm.wrtmonitor.qdisc=$sqm_qdisc" \
                && uci set "sqm.wrtmonitor.script=$sqm_script" \
                && uci set "sqm.wrtmonitor.qdisc_advanced=$( [ -n "$sqm_qdisc_options" ] && printf 1 || printf 0 )" \
                && uci set "sqm.wrtmonitor.qdisc_really_really_advanced=$( [ -n "$sqm_qdisc_options" ] && printf 1 || printf 0 )" \
                && uci set "sqm.wrtmonitor.eqdisc_opts=$sqm_qdisc_options" \
                  && uci set "sqm.wrtmonitor.iqdisc_opts=$sqm_qdisc_options" \
                  && uci commit sqm \
                  && service_action sqm restart 20 >/dev/null 2>&1; then
                sqm_crontab="${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root"
                mkdir -p "$(dirname "$sqm_crontab")"
                touch "$sqm_crontab"
                sed -i '/# wrtmonitor-sqm-schedule$/d' "$sqm_crontab"
                if [ "$sqm_schedule_enabled" = true ]; then
                    sqm_cron_days=""
                    for sqm_day in $sqm_schedule_days; do
                        case "$sqm_day" in mon) sqm_number=1 ;; tue) sqm_number=2 ;; wed) sqm_number=3 ;; thu) sqm_number=4 ;; fri) sqm_number=5 ;; sat) sqm_number=6 ;; sun) sqm_number=0 ;; *) continue ;; esac
                        sqm_cron_days="${sqm_cron_days:+$sqm_cron_days,}$sqm_number"
                    done
                    sqm_start_hour="${sqm_schedule_start%:*}"; sqm_start_minute="${sqm_schedule_start#*:}"
                    sqm_stop_hour="${sqm_schedule_stop%:*}"; sqm_stop_minute="${sqm_schedule_stop#*:}"
                    printf '%s %s * * %s /etc/init.d/sqm start # wrtmonitor-sqm-schedule\n' "$sqm_start_minute" "$sqm_start_hour" "$sqm_cron_days" >>"$sqm_crontab"
                    printf '%s %s * * %s /etc/init.d/sqm stop # wrtmonitor-sqm-schedule\n' "$sqm_stop_minute" "$sqm_stop_hour" "$sqm_cron_days" >>"$sqm_crontab"
                fi
                [ ! -x /etc/init.d/cron ] || service_action cron restart 20 >/dev/null 2>&1 || true
                result="$(command_success_result "SQM configuration applied" "\"backup\":\"$(json_escape "$sqm_backup")\",\"profile\":\"$(json_escape "$sqm_profile")\",\"interface\":\"$(json_escape "$sqm_interface")\",\"download_kbps\":$sqm_download,\"upload_kbps\":$sqm_upload")"
            else
                status="failed"; result="$(command_failed_result "failed to apply SQM configuration")"
            fi
            ;;
        *) return 1 ;;
    esac
    return 0
}
