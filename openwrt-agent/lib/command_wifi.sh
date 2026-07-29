handle_wifi_command() {
    case "$command_type" in
        wifi.status)
            result="$(wifi_status_json)"
            ;;
        wifi.set_radio)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            radio="$(json_get_string "$payload_file" '@.radio')"; channel="$(json_get_string "$payload_file" '@.channel')"; country="$(json_get_string "$payload_file" '@.country')"; htmode="$(json_get_string "$payload_file" '@.htmode')"; txpower="$(json_get_number "$payload_file" '@.txpower')"; rm -f "$payload_file"
            resolved_radio="$(resolve_wifi_radio "$radio" || true)"
            if [ -z "$resolved_radio" ]; then status="failed"; result="$(command_failed_result "wifi radio not found")"
            else
                [ -z "$channel" ] || uci set "wireless.$resolved_radio.channel=$channel" || status="failed"
                [ -z "$country" ] || uci set "wireless.$resolved_radio.country=$country" || status="failed"
                [ -z "$htmode" ] || uci set "wireless.$resolved_radio.htmode=$htmode" || status="failed"
                [ -z "$txpower" ] || uci set "wireless.$resolved_radio.txpower=$txpower" || status="failed"
                if [ "$status" = "done" ] && uci commit wireless && wifi reload >/dev/null 2>&1; then result="$(command_success_result "Wi-Fi radio updated" "\"radio\":\"$(json_escape "$resolved_radio")\"")"; else status="failed"; result="$(command_failed_result "failed to update Wi-Fi radio")"; fi
            fi
            ;;
        wifi.add_ssid)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            radio="$(json_get_string "$payload_file" '@.radio')"; ssid="$(json_get_string "$payload_file" '@.ssid')"; network="$(json_get_string "$payload_file" '@.network')"; encryption="$(json_get_string "$payload_file" '@.encryption')"; wifi_key="$(json_get_string "$payload_file" '@.key')"; hidden="$(json_get_bool "$payload_file" '@.hidden')"; isolate="$(json_get_bool "$payload_file" '@.isolate')"; rm -f "$payload_file"
            resolved_radio="$(resolve_wifi_radio "$radio" || true)"; new_iface="$(uci add wireless wifi-iface 2>/dev/null || true)"
            if [ -z "$resolved_radio" ] || [ -z "$new_iface" ]; then status="failed"; result="$(command_failed_result "wifi radio is unavailable")"
            elif uci set "wireless.$new_iface.device=$resolved_radio" && uci set "wireless.$new_iface.mode=ap" && uci set "wireless.$new_iface.network=$network" && uci set "wireless.$new_iface.ssid=$ssid" && uci set "wireless.$new_iface.encryption=$encryption" && uci set "wireless.$new_iface.hidden=$( [ "$hidden" = true ] && printf 1 || printf 0 )" && uci set "wireless.$new_iface.isolate=$( [ "$isolate" = true ] && printf 1 || printf 0 )" && { [ "$encryption" = none ] || uci set "wireless.$new_iface.key=$wifi_key"; } && uci commit wireless && wifi reload >/dev/null 2>&1; then result="$(command_success_result "Wi-Fi network added" "\"iface\":\"$(json_escape "$new_iface")\"")"; else status="failed"; result="$(command_failed_result "failed to add Wi-Fi network")"; fi
            ;;
        wifi.update_ssid)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            iface="$(json_get_string "$payload_file" '@.iface')"; ssid="$(json_get_string "$payload_file" '@.ssid')"; network="$(json_get_string "$payload_file" '@.network')"; encryption="$(json_get_string "$payload_file" '@.encryption')"; wifi_key="$(json_get_string "$payload_file" '@.key')"; enabled="$(json_get_bool "$payload_file" '@.enabled')"; hidden="$(json_get_bool "$payload_file" '@.hidden')"; isolate="$(json_get_bool "$payload_file" '@.isolate')"; ieee80211r="$(json_get_bool "$payload_file" '@.ieee80211r')"; ieee80211k="$(json_get_bool "$payload_file" '@.ieee80211k')"; bss_transition="$(json_get_bool "$payload_file" '@.bss_transition')"; mobility_domain="$(json_get_string "$payload_file" '@.mobility_domain')"; rm -f "$payload_file"
            resolved_iface="$(resolve_wifi_iface "$iface" "" || true)"
            if [ -z "$resolved_iface" ]; then status="failed"; result="$(command_failed_result "wifi interface not found")"
            elif uci set "wireless.$resolved_iface.ssid=$ssid" && uci set "wireless.$resolved_iface.network=$network" && uci set "wireless.$resolved_iface.encryption=$encryption" && uci set "wireless.$resolved_iface.disabled=$( [ "$enabled" = true ] && printf 0 || printf 1 )" && uci set "wireless.$resolved_iface.hidden=$( [ "$hidden" = true ] && printf 1 || printf 0 )" && uci set "wireless.$resolved_iface.isolate=$( [ "$isolate" = true ] && printf 1 || printf 0 )" && uci set "wireless.$resolved_iface.ieee80211r=$( [ "$ieee80211r" = true ] && printf 1 || printf 0 )" && uci set "wireless.$resolved_iface.ieee80211k=$( [ "$ieee80211k" = true ] && printf 1 || printf 0 )" && uci set "wireless.$resolved_iface.bss_transition=$( [ "$bss_transition" = true ] && printf 1 || printf 0 )"; then
                if [ "$encryption" = none ]; then uci -q delete "wireless.$resolved_iface.key" || true; elif [ -n "$wifi_key" ]; then uci set "wireless.$resolved_iface.key=$wifi_key"; fi
                if [ "$ieee80211r" = true ]; then uci set "wireless.$resolved_iface.mobility_domain=$mobility_domain"; else uci -q delete "wireless.$resolved_iface.mobility_domain" || true; fi
                if uci commit wireless && wifi reload >/dev/null 2>&1; then result="$(command_success_result "Wi-Fi network updated" "\"iface\":\"$(json_escape "$resolved_iface")\"")"; else status="failed"; result="$(command_failed_result "failed to reload Wi-Fi")"; fi
            else status="failed"; result="$(command_failed_result "failed to update Wi-Fi network")"; fi
            ;;
        wifi.delete_ssid)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; iface="$(json_get_string "$payload_file" '@.iface')"; rm -f "$payload_file"; resolved_iface="$(resolve_wifi_iface "$iface" "" || true)"
            if [ -n "$resolved_iface" ] && uci delete "wireless.$resolved_iface" && uci commit wireless && wifi reload >/dev/null 2>&1; then result="$(command_success_result "Wi-Fi network deleted")"; else status="failed"; result="$(command_failed_result "failed to delete Wi-Fi network")"; fi
            ;;
        wifi.set_schedule)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; radio="$(json_get_string "$payload_file" '@.radio')"; enabled="$(json_get_bool "$payload_file" '@.enabled')"; weekdays="$(jsonfilter -i "$payload_file" -e '@.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"; schedule_start="$(json_get_string "$payload_file" '@.start')"; schedule_stop="$(json_get_string "$payload_file" '@.stop')"; rm -f "$payload_file"; resolved_radio="$(resolve_wifi_radio "$radio" || true)"; schedule_ref="$(find_wifi_schedule "$resolved_radio" || uci add wrtmonitor wifi_schedule)"
            if [ -n "$resolved_radio" ] && [ -n "$schedule_ref" ] && uci set "wrtmonitor.$schedule_ref.radio=$resolved_radio" && uci set "wrtmonitor.$schedule_ref.enabled=$( [ "$enabled" = true ] && printf 1 || printf 0 )" && uci set "wrtmonitor.$schedule_ref.weekdays=$weekdays" && uci set "wrtmonitor.$schedule_ref.start=$schedule_start" && uci set "wrtmonitor.$schedule_ref.stop=$schedule_stop" && uci commit wrtmonitor && apply_wifi_schedules; then result="$(command_success_result "Wi-Fi schedule updated")"; else status="failed"; result="$(command_failed_result "failed to update Wi-Fi schedule")"; fi
            ;;
        wifi.set_mesh)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; radio="$(json_get_string "$payload_file" '@.radio')"; enabled="$(json_get_bool "$payload_file" '@.enabled')"; mesh_id="$(json_get_string "$payload_file" '@.mesh_id')"; network="$(json_get_string "$payload_file" '@.network')"; encryption="$(json_get_string "$payload_file" '@.encryption')"; wifi_key="$(json_get_string "$payload_file" '@.key')"; rm -f "$payload_file"; resolved_radio="$(resolve_wifi_radio "$radio" || true)"; mesh_iface="$(find_mesh_iface "$resolved_radio" || true)"
            if [ "$enabled" = true ] && [ -n "$resolved_radio" ]; then
                [ -n "$mesh_iface" ] || mesh_iface="$(uci add wireless wifi-iface)"
                if uci set "wireless.$mesh_iface.device=$resolved_radio" && uci set "wireless.$mesh_iface.mode=mesh" && uci set "wireless.$mesh_iface.mesh_id=$mesh_id" && uci set "wireless.$mesh_iface.network=$network" && uci set "wireless.$mesh_iface.encryption=$encryption" && { [ "$encryption" = none ] || uci set "wireless.$mesh_iface.key=$wifi_key"; } && uci commit wireless && wifi reload >/dev/null 2>&1; then result="$(command_success_result "Wi-Fi mesh enabled")"; else status="failed"; result="$(command_failed_result "failed to enable Wi-Fi mesh")"; fi
            elif [ "$enabled" = false ] && [ -n "$mesh_iface" ] && uci delete "wireless.$mesh_iface" && uci commit wireless && wifi reload >/dev/null 2>&1; then result="$(command_success_result "Wi-Fi mesh disabled")"
            else status="failed"; result="$(command_failed_result "mesh interface or radio not found")"; fi
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
        wifi.set_guest)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; guest_enabled="$(json_get_bool "$payload_file" '@.enabled')"; guest_ssid="$(json_get_string "$payload_file" '@.ssid')"; guest_password="$(json_get_string "$payload_file" '@.password')"; guest_radio="$(json_get_string "$payload_file" '@.radio')"; rm -f "$payload_file"
            [ -n "$guest_radio" ] || guest_radio="$(resolve_wifi_radio "" || true)"; [ -n "$guest_radio" ] || guest_radio="radio0"
            guest_ip="$(uci -q get network.wrtmonitor_guest.ipaddr 2>/dev/null || true)"
            if [ -z "$guest_ip" ]; then
                guest_octet=2
                while [ "$guest_octet" -le 254 ]; do
                    guest_subnet="192.168.$guest_octet.0/24"
                    if ! ip -4 route show 2>/dev/null | grep -Fq "$guest_subnet" \
                        && ! uci -q show network 2>/dev/null | grep -Fq "192.168.$guest_octet."; then
                        guest_ip="192.168.$guest_octet.1"
                        break
                    fi
                    guest_octet=$((guest_octet + 1))
                done
            fi
            wireless_backup="$(backup_config wireless "$command_id" "$command_type" || true)"; network_backup="$(backup_config network "$command_id" "$command_type" || true)"; dhcp_backup="$(backup_config dhcp "$command_id" "$command_type" || true)"; firewall_backup="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -z "$guest_ip" ]; then status="failed"; result="$(command_failed_result "no unused guest subnet is available")"
            elif [ -z "$wireless_backup" ] || [ -z "$network_backup" ] || [ -z "$dhcp_backup" ] || [ -z "$firewall_backup" ]; then status="failed"; result="$(command_failed_result "failed to create guest network backups")"
            else
                uci set network.wrtmonitor_guest=interface; uci set network.wrtmonitor_guest.proto=static; uci set "network.wrtmonitor_guest.ipaddr=$guest_ip"; uci set network.wrtmonitor_guest.netmask=255.255.255.0
                uci set dhcp.wrtmonitor_guest=dhcp; uci set dhcp.wrtmonitor_guest.interface=wrtmonitor_guest; uci set dhcp.wrtmonitor_guest.start=100; uci set dhcp.wrtmonitor_guest.limit=150; uci set dhcp.wrtmonitor_guest.leasetime=12h
                uci set firewall.wrtmonitor_guest=zone; uci set firewall.wrtmonitor_guest.name=wrtmonitor_guest; uci add_list firewall.wrtmonitor_guest.network=wrtmonitor_guest; uci set firewall.wrtmonitor_guest.input=REJECT; uci set firewall.wrtmonitor_guest.output=ACCEPT; uci set firewall.wrtmonitor_guest.forward=REJECT
                uci set firewall.wrtmonitor_guest_forward=forwarding; uci set firewall.wrtmonitor_guest_forward.src=wrtmonitor_guest; uci set firewall.wrtmonitor_guest_forward.dest=wan
                uci set wireless.wrtmonitor_guest=wifi-iface; uci set wireless.wrtmonitor_guest.device="$guest_radio"; uci set wireless.wrtmonitor_guest.network=wrtmonitor_guest; uci set wireless.wrtmonitor_guest.mode=ap; uci set wireless.wrtmonitor_guest.isolate=1
                if [ "$guest_enabled" = "true" ]; then uci set wireless.wrtmonitor_guest.disabled=0; uci set wireless.wrtmonitor_guest.ssid="$guest_ssid"; uci set wireless.wrtmonitor_guest.encryption=psk2; uci set wireless.wrtmonitor_guest.key="$guest_password"; else uci set wireless.wrtmonitor_guest.disabled=1; fi
                if uci commit network && uci commit dhcp && uci commit firewall && uci commit wireless; then result="$(command_success_result "guest Wi-Fi configuration saved" "\"gateway\":\"$(json_escape "$guest_ip")\"")"; (sleep 2; /etc/init.d/network restart; /etc/init.d/dnsmasq restart; /etc/init.d/firewall reload; wifi reload) >/dev/null 2>&1 & else status="failed"; result="$(command_failed_result "failed to configure guest Wi-Fi")"; fi
            fi
            ;;
        *) return 1 ;;
    esac
    return 0
}
