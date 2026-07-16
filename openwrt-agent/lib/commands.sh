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
