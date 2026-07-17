list_config_backups() {
    ensure_state_dirs
    find "$CONFIG_BACKUP_DIR" -maxdepth 1 -type f -name '*.bak' | sort
}

backup_wireless_config() {
    command_id="$1"
    command_type="$2"
    ensure_state_dirs
    [ -r /etc/config/wireless ] || return 1
    timestamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo unknown)"
    backup_file="$CONFIG_BACKUP_DIR/wireless-$timestamp-$command_id.bak"
    meta_file="$CONFIG_BACKUP_DIR/wireless-$timestamp-$command_id.meta"
    cp /etc/config/wireless "$backup_file"
    {
        printf 'command_id=%s\n' "$command_id"
        printf 'command_type=%s\n' "$command_type"
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'agent_version=%s\n' "$AGENT_VERSION"
        printf 'config_file=/etc/config/wireless\n'
    } >"$meta_file"
    printf '%s' "$backup_file"
}

backup_config() {
    config_name="$1"
    command_id="$2"
    command_type="$3"
    ensure_state_dirs
    config_file="/etc/config/$config_name"
    [ -r "$config_file" ] || return 1
    timestamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo unknown)"
    backup_file="$CONFIG_BACKUP_DIR/$config_name-$timestamp-$command_id.bak"
    cp "$config_file" "$backup_file"
    {
        printf 'command_id=%s\n' "$command_id"
        printf 'command_type=%s\n' "$command_type"
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'agent_version=%s\n' "$AGENT_VERSION"
        printf 'config_file=%s\n' "$config_file"
    } >"$CONFIG_BACKUP_DIR/$config_name-$timestamp-$command_id.meta"
    printf '%s' "$backup_file"
}

command_success_result() {
    message="$1"
    extra="${2:-}"
    if [ -n "$extra" ]; then
        printf '{"message":"%s",%s}' "$(json_escape "$message")" "$extra"
    else
        printf '{"message":"%s"}' "$(json_escape "$message")"
    fi
}

command_failed_result() {
    message="$1"
    printf '{"error":"%s"}' "$(json_escape "$message")"
}

resolve_wifi_radio() {
    requested="$1"
    if [ -n "$requested" ]; then
        if uci -q get "wireless.$requested" >/dev/null 2>&1; then
            printf '%s' "$requested"
            return 0
        fi
        printf '%s' ""
        return 1
    fi
    count=0
    resolved=""
    while uci -q get "wireless.@wifi-device[$count]" >/dev/null 2>&1; do
        resolved="radio$count"
        count=$((count + 1))
    done
    if [ "$count" -eq 1 ]; then
        printf '%s' "$resolved"
        return 0
    fi
    printf '%s' ""
    return 1
}

resolve_wifi_iface() {
    requested="$1"
    radio_name="$2"
    if [ -n "$requested" ]; then
        if uci -q get "wireless.$requested" >/dev/null 2>&1; then
            printf '%s' "$requested"
            return 0
        fi
        printf '%s' ""
        return 1
    fi
    count=0
    matches=0
    resolved=""
    while uci -q get "wireless.@wifi-iface[$count]" >/dev/null 2>&1; do
        iface_device="$(uci -q get "wireless.@wifi-iface[$count].device" 2>/dev/null || true)"
        if [ "$iface_device" = "$radio_name" ]; then
            resolved="@wifi-iface[$count]"
            matches=$((matches + 1))
        fi
        count=$((count + 1))
    done
    if [ "$matches" -eq 1 ]; then
        printf '%s' "$resolved"
        return 0
    fi
    printf '%s' ""
    return 1
}

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

execute_command() {
    command_id="$1"
    command_type="$2"
    command_payload="${3:-{}}"
    status="done"
    result="{}"
    disconnect_after=0
    transaction_active=0
    if transaction_configs_for_command "$command_type" >/dev/null 2>&1; then
        transaction_timeout="$(transaction_timeout_from_payload "$command_payload")"
        if transaction_begin "$command_id" "$command_type" "$transaction_timeout"; then
            transaction_active=1
        else
            result="$(transaction_failure_result "$command_id" "configuration preflight or backup failed" "not_applied")"
            api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"failed\",\"result\":$result}" >/dev/null || true
            return 1
        fi
    fi
    case "$command_type" in
        router.reboot)
            result="$(command_success_result "reboot scheduled")"
            (sleep 2; reboot) >/dev/null 2>&1 &
            ;;
        wifi.status)
            result="$(wifi_status_json)"
            ;;
        wifi.set_enabled)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            enabled="$(json_get_bool /tmp/wrtmonitor-command-payload '@.enabled')"
            radio="$(json_get_string /tmp/wrtmonitor-command-payload '@.radio')"
            rm -f /tmp/wrtmonitor-command-payload
            resolved_radio="$(resolve_wifi_radio "$radio" || true)"
            if [ -z "$resolved_radio" ]; then
                status="failed"
                result="$(command_failed_result "wifi radio is ambiguous or not found")"
            else
                backup_file="$(backup_wireless_config "$command_id" "$command_type" || true)"
                if [ -z "$backup_file" ]; then
                    status="failed"
                    result="$(command_failed_result "failed to create wireless config backup")"
                else
                    if [ "$enabled" = "false" ]; then
                        uci set "wireless.$resolved_radio.disabled=1" >/dev/null 2>&1 || status="failed"
                    else
                        uci set "wireless.$resolved_radio.disabled=0" >/dev/null 2>&1 || status="failed"
                    fi
                    uci commit wireless >/dev/null 2>&1 || status="failed"
                    wifi reload >/dev/null 2>&1 || status="failed"
                    if [ "$status" = "done" ]; then
                        result="$(command_success_result "Wi-Fi state updated" "\"backup\":\"$(json_escape "$backup_file")\",\"radio\":\"$(json_escape "$resolved_radio")\"")"
                    else
                        result="$(command_failed_result "failed to update Wi-Fi state")"
                    fi
                fi
            fi
            ;;
        wifi.set_ssid)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            ssid="$(json_get_string /tmp/wrtmonitor-command-payload '@.ssid')"
            iface="$(json_get_string /tmp/wrtmonitor-command-payload '@.iface')"
            rm -f /tmp/wrtmonitor-command-payload
            if [ -n "$ssid" ]; then
                resolved_iface="$(resolve_wifi_iface "$iface" "$(resolve_wifi_radio "" || true)" || true)"
                if [ -z "$resolved_iface" ]; then
                    status="failed"
                    result="$(command_failed_result "wifi iface is ambiguous or not found")"
                else
                    backup_file="$(backup_wireless_config "$command_id" "$command_type" || true)"
                    if [ -z "$backup_file" ]; then
                        status="failed"
                        result="$(command_failed_result "failed to create wireless config backup")"
                    else
                        uci set "wireless.$resolved_iface.ssid=$ssid" >/dev/null 2>&1 || status="failed"
                        uci commit wireless >/dev/null 2>&1 || status="failed"
                        wifi reload >/dev/null 2>&1 || status="failed"
                        if [ "$status" = "done" ]; then
                            result="$(command_success_result "Wi-Fi SSID updated" "\"backup\":\"$(json_escape "$backup_file")\",\"iface\":\"$(json_escape "$resolved_iface")\"")"
                        else
                            result="$(command_failed_result "failed to update Wi-Fi SSID")"
                        fi
                    fi
                fi
            else
                status="failed"
                result="$(command_failed_result "ssid is required")"
            fi
            ;;
        wifi.set_password)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            wifi_key="$(json_get_string /tmp/wrtmonitor-command-payload '@.key')"
            iface="$(json_get_string /tmp/wrtmonitor-command-payload '@.iface')"
            rm -f /tmp/wrtmonitor-command-payload
            if [ "${#wifi_key}" -ge 8 ]; then
                resolved_iface="$(resolve_wifi_iface "$iface" "$(resolve_wifi_radio "" || true)" || true)"
                if [ -z "$resolved_iface" ]; then
                    status="failed"
                    result="$(command_failed_result "wifi iface is ambiguous or not found")"
                else
                    backup_file="$(backup_wireless_config "$command_id" "$command_type" || true)"
                    if [ -z "$backup_file" ]; then
                        status="failed"
                        result="$(command_failed_result "failed to create wireless config backup")"
                    else
                        uci set "wireless.$resolved_iface.key=$wifi_key" >/dev/null 2>&1 || status="failed"
                        uci commit wireless >/dev/null 2>&1 || status="failed"
                        wifi reload >/dev/null 2>&1 || status="failed"
                        if [ "$status" = "done" ]; then
                            result="$(command_success_result "Wi-Fi password updated" "\"backup\":\"$(json_escape "$backup_file")\",\"iface\":\"$(json_escape "$resolved_iface")\"")"
                        else
                            result="$(command_failed_result "failed to update Wi-Fi password")"
                        fi
                    fi
                fi
            else
                status="failed"
                result="$(command_failed_result "password must contain at least 8 characters")"
            fi
            ;;
        wifi.set_channel)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            radio="$(json_get_string /tmp/wrtmonitor-command-payload '@.radio')"
            channel="$(json_get_string /tmp/wrtmonitor-command-payload '@.channel')"
            rm -f /tmp/wrtmonitor-command-payload
            resolved_radio="$(resolve_wifi_radio "$radio" || true)"
            backup_file="$(backup_wireless_config "$command_id" "$command_type" || true)"
            if [ -z "$resolved_radio" ] || [ -z "$backup_file" ]; then
                status="failed"
                result="$(command_failed_result "wifi radio or backup is unavailable")"
            elif uci set "wireless.$resolved_radio.channel=$channel" && uci commit wireless && wifi reload; then
                result="$(command_success_result "Wi-Fi channel updated" "\"backup\":\"$(json_escape "$backup_file")\",\"radio\":\"$(json_escape "$resolved_radio")\",\"channel\":\"$(json_escape "$channel")\"")"
            else
                status="failed"
                result="$(command_failed_result "failed to update Wi-Fi channel")"
            fi
            ;;
        wifi.set_country)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            radio="$(json_get_string /tmp/wrtmonitor-command-payload '@.radio')"
            country="$(json_get_string /tmp/wrtmonitor-command-payload '@.country')"
            rm -f /tmp/wrtmonitor-command-payload
            resolved_radio="$(resolve_wifi_radio "$radio" || true)"
            backup_file="$(backup_wireless_config "$command_id" "$command_type" || true)"
            if [ -z "$resolved_radio" ] || [ -z "$backup_file" ]; then
                status="failed"
                result="$(command_failed_result "wifi radio or backup is unavailable")"
            elif uci set "wireless.$resolved_radio.country=$country" && uci commit wireless && wifi reload; then
                result="$(command_success_result "Wi-Fi country updated" "\"backup\":\"$(json_escape "$backup_file")\",\"radio\":\"$(json_escape "$resolved_radio")\",\"country\":\"$(json_escape "$country")\"")"
            else
                status="failed"
                result="$(command_failed_result "failed to update Wi-Fi country")"
            fi
            ;;
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
            backup_file="$(backup_config network "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && uci set "network.$lan_interface=interface" && uci set "network.$lan_interface.proto=static" && uci set "network.$lan_interface.ipaddr=$lan_ip" && uci set "network.$lan_interface.netmask=$lan_netmask" && uci commit network; then
                result="$(command_success_result "LAN configuration saved; connection address may change" "\"backup\":\"$(json_escape "$backup_file")\",\"interface\":\"$(json_escape "$lan_interface")\",\"ip_address\":\"$(json_escape "$lan_ip")\"")"
                (sleep 3; /etc/init.d/network restart) >/dev/null 2>&1 &
            else status="failed"; result="$(command_failed_result "failed to configure LAN")"; fi
            ;;
        system.set_hostname)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            hostname_value="$(json_get_string /tmp/wrtmonitor-command-payload '@.hostname')"
            rm -f /tmp/wrtmonitor-command-payload
            backup_file="$(backup_config system "$command_id" "$command_type" || true)"
            if [ -z "$hostname_value" ] || [ -z "$backup_file" ]; then
                status="failed"
                result="$(command_failed_result "hostname or backup is unavailable")"
            elif uci set "system.@system[0].hostname=$hostname_value" && uci commit system; then
                hostname "$hostname_value" >/dev/null 2>&1 || true
                result="$(command_success_result "hostname updated" "\"backup\":\"$(json_escape "$backup_file")\",\"hostname\":\"$(json_escape "$hostname_value")\"")"
            else
                status="failed"
                result="$(command_failed_result "failed to update hostname")"
            fi
            ;;
        system.restart_service)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            service="$(json_get_string /tmp/wrtmonitor-command-payload '@.service')"
            rm -f /tmp/wrtmonitor-command-payload
            case "$service" in
                network)
                    result="$(command_success_result "service restart scheduled" "\"service\":\"network\"")"
                    (sleep 2; /etc/init.d/network restart) >/dev/null 2>&1 &
                    ;;
                dnsmasq|firewall|odhcpd)
                    if [ -x "/etc/init.d/$service" ] && "/etc/init.d/$service" restart >/dev/null 2>&1; then
                        result="$(command_success_result "service restarted" "\"service\":\"$(json_escape "$service")\"")"
                    else
                        status="failed"
                        result="$(command_failed_result "failed to restart service")"
                    fi
                    ;;
                *)
                    status="failed"
                    result="$(command_failed_result "service is not allowed")"
                    ;;
            esac
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
                && /etc/init.d/dnsmasq restart >/dev/null 2>&1; then
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
            elif [ -n "$lease_ref" ] && uci -q delete "dhcp.$lease_ref" && uci commit dhcp && /etc/init.d/dnsmasq restart >/dev/null 2>&1; then
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
            if [ -n "$backup_file" ] && uci set "dhcp.$pool_interface=dhcp" && uci set "dhcp.$pool_interface.interface=$pool_interface" && uci set "dhcp.$pool_interface.start=$pool_start" && uci set "dhcp.$pool_interface.limit=$pool_limit" && uci set "dhcp.$pool_interface.leasetime=$pool_leasetime" && uci commit dhcp && /etc/init.d/dnsmasq restart >/dev/null 2>&1; then
                result="$(command_success_result "DHCP pool updated" "\"backup\":\"$(json_escape "$backup_file")\"")"
            else status="failed"; result="$(command_failed_result "failed to update DHCP pool")"; fi
            ;;
        dns.set_servers)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; dns_servers="$(jsonfilter -i "$payload_file" -e '@.servers[*]' 2>/dev/null || true)"; rm -f "$payload_file"
            backup_file="$(backup_config dhcp "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && [ -n "$dns_servers" ]; then
                uci -q delete 'dhcp.@dnsmasq[0].server' || true
                printf '%s\n' "$dns_servers" | while IFS= read -r server; do [ -z "$server" ] || uci add_list "dhcp.@dnsmasq[0].server=$server"; done
                if uci commit dhcp && /etc/init.d/dnsmasq restart >/dev/null 2>&1; then result="$(command_success_result "DNS servers updated" "\"backup\":\"$(json_escape "$backup_file")\"")"; else status="failed"; result="$(command_failed_result "failed to update DNS servers")"; fi
            else status="failed"; result="$(command_failed_result "DNS servers or backup are unavailable")"; fi
            ;;
        firewall.set_port_forward)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            forward_name="$(json_get_string "$payload_file" '@.name')"; forward_proto="$(json_get_string "$payload_file" '@.protocol')"; external_port="$(json_get_number "$payload_file" '@.external_port')"; internal_ip="$(json_get_string "$payload_file" '@.internal_ip')"; internal_port="$(json_get_number "$payload_file" '@.internal_port')"; rm -f "$payload_file"
            forward_ref="wrtmonitor_redirect_$forward_name"; [ "$forward_proto" != "tcpudp" ] || forward_proto="tcp udp"
            backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && uci set "firewall.$forward_ref=redirect" && uci set "firewall.$forward_ref.name=WrtMonitor-$forward_name" && uci set "firewall.$forward_ref.src=wan" && uci set "firewall.$forward_ref.dest=lan" && uci set "firewall.$forward_ref.proto=$forward_proto" && uci set "firewall.$forward_ref.src_dport=$external_port" && uci set "firewall.$forward_ref.dest_ip=$internal_ip" && uci set "firewall.$forward_ref.dest_port=$internal_port" && uci set "firewall.$forward_ref.target=DNAT" && uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then
                result="$(command_success_result "port forwarding rule saved" "\"backup\":\"$(json_escape "$backup_file")\",\"name\":\"$(json_escape "$forward_name")\"")"
            else status="failed"; result="$(command_failed_result "failed to save port forwarding rule")"; fi
            ;;
        firewall.delete_port_forward)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; forward_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; forward_ref="wrtmonitor_redirect_$forward_name"
            backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && uci -q delete "firewall.$forward_ref" && uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "port forwarding rule deleted" "\"backup\":\"$(json_escape "$backup_file")\"")"; else status="failed"; result="$(command_failed_result "port forwarding rule not found")"; fi
            ;;
        client.set_blocked)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; client_mac="$(json_get_string "$payload_file" '@.mac')"; client_blocked="$(json_get_bool "$payload_file" '@.blocked')"; rm -f "$payload_file"
            client_ref="wrtmonitor_block_$(printf '%s' "$client_mac" | tr -d ':')"; backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -z "$backup_file" ]; then status="failed"; result="$(command_failed_result "failed to create firewall backup")"
            elif [ "$client_blocked" = "true" ]; then
                if uci set "firewall.$client_ref=rule" && uci set "firewall.$client_ref.name=WrtMonitor block $client_mac" && uci set "firewall.$client_ref.src=lan" && uci set "firewall.$client_ref.dest=wan" && uci set "firewall.$client_ref.src_mac=$client_mac" && uci set "firewall.$client_ref.target=REJECT" && uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "client internet access blocked" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\"")"; else status="failed"; result="$(command_failed_result "failed to block client")"; fi
            else
                uci -q delete "firewall.$client_ref" || true
                if uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "client internet access restored" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\"")"; else status="failed"; result="$(command_failed_result "failed to unblock client")"; fi
            fi
            ;;
        wifi.set_guest)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; guest_enabled="$(json_get_bool "$payload_file" '@.enabled')"; guest_ssid="$(json_get_string "$payload_file" '@.ssid')"; guest_password="$(json_get_string "$payload_file" '@.password')"; guest_radio="$(json_get_string "$payload_file" '@.radio')"; rm -f "$payload_file"
            [ -n "$guest_radio" ] || guest_radio="$(resolve_wifi_radio "" || true)"; [ -n "$guest_radio" ] || guest_radio="radio0"
            wireless_backup="$(backup_config wireless "$command_id" "$command_type" || true)"; network_backup="$(backup_config network "$command_id" "$command_type" || true)"; dhcp_backup="$(backup_config dhcp "$command_id" "$command_type" || true)"; firewall_backup="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -z "$wireless_backup" ] || [ -z "$network_backup" ] || [ -z "$dhcp_backup" ] || [ -z "$firewall_backup" ]; then status="failed"; result="$(command_failed_result "failed to create guest network backups")"
            else
                uci set network.wrtmonitor_guest=interface; uci set network.wrtmonitor_guest.proto=static; uci set network.wrtmonitor_guest.ipaddr=192.168.3.1; uci set network.wrtmonitor_guest.netmask=255.255.255.0
                uci set dhcp.wrtmonitor_guest=dhcp; uci set dhcp.wrtmonitor_guest.interface=wrtmonitor_guest; uci set dhcp.wrtmonitor_guest.start=100; uci set dhcp.wrtmonitor_guest.limit=150; uci set dhcp.wrtmonitor_guest.leasetime=12h
                uci set firewall.wrtmonitor_guest=zone; uci set firewall.wrtmonitor_guest.name=wrtmonitor_guest; uci add_list firewall.wrtmonitor_guest.network=wrtmonitor_guest; uci set firewall.wrtmonitor_guest.input=REJECT; uci set firewall.wrtmonitor_guest.output=ACCEPT; uci set firewall.wrtmonitor_guest.forward=REJECT
                uci set firewall.wrtmonitor_guest_forward=forwarding; uci set firewall.wrtmonitor_guest_forward.src=wrtmonitor_guest; uci set firewall.wrtmonitor_guest_forward.dest=wan
                uci set wireless.wrtmonitor_guest=wifi-iface; uci set wireless.wrtmonitor_guest.device="$guest_radio"; uci set wireless.wrtmonitor_guest.network=wrtmonitor_guest; uci set wireless.wrtmonitor_guest.mode=ap; uci set wireless.wrtmonitor_guest.isolate=1
                if [ "$guest_enabled" = "true" ]; then uci set wireless.wrtmonitor_guest.disabled=0; uci set wireless.wrtmonitor_guest.ssid="$guest_ssid"; uci set wireless.wrtmonitor_guest.encryption=psk2; uci set wireless.wrtmonitor_guest.key="$guest_password"; else uci set wireless.wrtmonitor_guest.disabled=1; fi
                if uci commit network && uci commit dhcp && uci commit firewall && uci commit wireless; then result="$(command_success_result "guest Wi-Fi configuration saved")"; (sleep 2; /etc/init.d/network restart; /etc/init.d/dnsmasq restart; /etc/init.d/firewall reload; wifi reload) >/dev/null 2>&1 & else status="failed"; result="$(command_failed_result "failed to configure guest Wi-Fi")"; fi
            fi
            ;;
        system.set_timezone)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; zonename="$(json_get_string "$payload_file" '@.zonename')"; timezone="$(json_get_string "$payload_file" '@.timezone')"; rm -f "$payload_file"; backup_file="$(backup_config system "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ] && uci set "system.@system[0].zonename=$zonename" && uci set "system.@system[0].timezone=$timezone" && uci commit system; then result="$(command_success_result "timezone updated" "\"backup\":\"$(json_escape "$backup_file")\"")"; else status="failed"; result="$(command_failed_result "failed to update timezone")"; fi
            ;;
        system.set_ntp)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; ntp_enabled="$(json_get_bool "$payload_file" '@.enabled')"; ntp_servers="$(jsonfilter -i "$payload_file" -e '@.servers[*]' 2>/dev/null || true)"; rm -f "$payload_file"; backup_file="$(backup_config system "$command_id" "$command_type" || true)"
            if [ -n "$backup_file" ]; then
                uci set system.ntp=timeserver
                if [ "$ntp_enabled" = "true" ]; then
                    uci set system.ntp.enabled=1
                else
                    uci set system.ntp.enabled=0
                fi
                uci -q delete system.ntp.server || true
                printf '%s\n' "$ntp_servers" | while IFS= read -r server; do [ -z "$server" ] || uci add_list "system.ntp.server=$server"; done
                if uci commit system && /etc/init.d/sysntpd restart >/dev/null 2>&1; then result="$(command_success_result "NTP settings updated" "\"backup\":\"$(json_escape "$backup_file")\"")"; else status="failed"; result="$(command_failed_result "failed to update NTP settings")"; fi
            else status="failed"; result="$(command_failed_result "failed to create system backup")"; fi
            ;;
        diagnostics.run)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            checks="$(jsonfilter -i /tmp/wrtmonitor-command-payload -e '@.checks[*]' 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
            rm -f /tmp/wrtmonitor-command-payload
            if [ -n "$checks" ]; then
                result="$(diagnostics_checks_json "$checks")"
            else
                result="$(diagnostics_json)"
            fi
            ;;
        agent.disconnect)
            result="$(command_success_result "agent disabled")"
            disconnect_after=1
            ;;
        agent.update)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            force="$(json_get_bool /tmp/wrtmonitor-command-payload '@.force')"
            allow_downgrade="$(json_get_bool /tmp/wrtmonitor-command-payload '@.allow_downgrade')"
            rm -f /tmp/wrtmonitor-command-payload
            [ "$force" = "true" ] || force="false"
            [ "$allow_downgrade" = "true" ] || allow_downgrade="false"
            if check_for_update "command" "$( [ "$force" = "true" ] && printf 1 || printf 0 )" "$( [ "$allow_downgrade" = "true" ] && printf 1 || printf 0 )"; then
                result="$(agent_status_json)"
            else
                status="failed"
                load_status
                result="{\"error\":\"$(json_escape "${LAST_UPDATE_ERROR:-update failed}")\"}"
            fi
            ;;
        agent.rollback)
            if perform_rollback "command" "rollback requested"; then
                result="$(agent_status_json)"
            else
                status="failed"
                load_status
                result="{\"error\":\"$(json_escape "${LAST_UPDATE_ERROR:-rollback unavailable}")\"}"
            fi
            ;;
        agent.set_auto_update)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            enabled="$(json_get_bool /tmp/wrtmonitor-command-payload '@.enabled')"
            rm -f /tmp/wrtmonitor-command-payload
            if [ "$enabled" = "false" ]; then
                set_auto_update_config 0
            else
                set_auto_update_config 1
            fi
            result="$(agent_status_json)"
            ;;
        agent.set_interval)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            interval_seconds="$(json_get_number /tmp/wrtmonitor-command-payload '@.interval_seconds')"
            rm -f /tmp/wrtmonitor-command-payload
            case "$interval_seconds" in
                ""|*[!0-9]*)
                    status="failed"
                    result="$(command_failed_result "interval_seconds must be numeric")"
                    ;;
                *)
                    if [ "$interval_seconds" -lt 5 ]; then
                        status="failed"
                        result="$(command_failed_result "interval_seconds must be at least 5")"
                    else
                        uci set "$CONFIG.interval=$interval_seconds"
                        uci commit wrtmonitor
                        result="$(agent_status_json)"
                    fi
                    ;;
            esac
            ;;
        *)
            status="failed"
            result='{"error":"unsupported command"}'
            ;;
    esac
    if [ "$transaction_active" = "1" ]; then
        if [ "$status" = "done" ] && transaction_is_connectivity_sensitive "$command_type"; then
            result="{\"message\":\"configuration applied; connectivity verification is running\",\"transaction\":{\"id\":\"$(json_escape "$command_id")\",\"state\":\"verifying\",\"rollback_timeout_seconds\":$transaction_timeout}}"
            api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"running\",\"result\":$result}" >/dev/null || true
            transaction_schedule_verification "$command_id"
            return 0
        fi
        if [ "$status" = "done" ]; then
            transaction_set_state "$command_id" "confirmed"
            result="$(transaction_success_result "$command_id")"
        elif transaction_restore "$command_id"; then
            result="$(transaction_failure_result "$command_id" "configuration command failed; backup restored" "rolled_back")"
        else
            result="$(transaction_failure_result "$command_id" "configuration command failed and rollback failed" "rollback_failed")"
        fi
    fi
    api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"$status\",\"result\":$result}" >/dev/null || true
    if [ "$disconnect_after" = "1" ] && [ "$status" = "done" ]; then
        uci set "$CONFIG.enabled=0"
        uci commit wrtmonitor
        log_notice "agent disconnected by server command"
        exit 0
    fi
    if [ "$PENDING_AGENT_EXEC" = "1" ] && [ "$status" = "done" ]; then
        handoff_to_updated_agent
    fi
}
