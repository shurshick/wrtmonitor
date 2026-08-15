# shellcheck disable=SC2034,SC2154
handle_network_services_command() {
    case "$command_type" in
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
        *) return 1 ;;
    esac
    return 0
}
