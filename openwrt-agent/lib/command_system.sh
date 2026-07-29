handle_system_command() {
    case "$command_type" in
        router.reboot)
            result="$(command_success_result "reboot scheduled")"
            (sleep 2; reboot) >/dev/null 2>&1 &
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
        *) return 1 ;;
    esac
    return 0
}
