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

encrypted_dns_provider() {
    mode="$1"
    provider="$2"
    case "$mode:$provider" in
        dot:cloudflare) printf '%s|%s|%s' '1.1.1.1 1.0.0.1' 'cloudflare-dns.com' '' ;;
        dot:quad9) printf '%s|%s|%s' '9.9.9.9 149.112.112.112' 'dns.quad9.net' '' ;;
        dot:google) printf '%s|%s|%s' '8.8.8.8 8.8.4.4' 'dns.google' '' ;;
        *) return 1 ;;
    esac
}

backup_plain_dns() {
    if [ -z "$(uci -q get wrtmonitor.main.dns_backup_present 2>/dev/null || true)" ]; then
        uci set wrtmonitor.main.dns_backup_present=1
        current_noresolv="$(uci -q get 'dhcp.@dnsmasq[0].noresolv' 2>/dev/null || printf unset)"
        uci set "wrtmonitor.main.dns_backup_noresolv=$current_noresolv"
        uci -q delete wrtmonitor.main.dns_backup_servers || true
        for server in $(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null || true); do
            uci add_list "wrtmonitor.main.dns_backup_servers=$server"
        done
        uci commit wrtmonitor
    fi
}

restore_plain_dns() {
    [ "$(uci -q get wrtmonitor.main.dns_backup_present 2>/dev/null || true)" = 1 ] || return 0
    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    for server in $(uci -q get wrtmonitor.main.dns_backup_servers 2>/dev/null || true); do
        uci add_list "dhcp.@dnsmasq[0].server=$server"
    done
    old_noresolv="$(uci -q get wrtmonitor.main.dns_backup_noresolv 2>/dev/null || printf unset)"
    if [ "$old_noresolv" = unset ]; then uci -q delete 'dhcp.@dnsmasq[0].noresolv' || true; else uci set "dhcp.@dnsmasq[0].noresolv=$old_noresolv"; fi
    uci -q delete wrtmonitor.main.dns_backup_present || true
    uci -q delete wrtmonitor.main.dns_backup_noresolv || true
    uci -q delete wrtmonitor.main.dns_backup_servers || true
    uci commit wrtmonitor
    uci commit dhcp
}

remove_dnsmasq_server() {
    target="$1"
    for server in $(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null || true); do
        [ "$server" != "$target" ] || uci -q del_list "dhcp.@dnsmasq[0].server=$target" || true
    done
}

configure_dot() {
    provider="$1"
    enabled="$2"
    [ -x /etc/init.d/stubby ] || return 1
    if [ "$enabled" != true ]; then
        /etc/init.d/stubby stop >/dev/null 2>&1 || true
        /etc/init.d/stubby disable >/dev/null 2>&1 || true
        restore_plain_dns
        /etc/init.d/dnsmasq restart >/dev/null 2>&1
        return
    fi
    provider_data="$(encrypted_dns_provider dot "$provider")" || return 1
    addresses="${provider_data%%|*}"
    auth_name="${provider_data#*|}"; auth_name="${auth_name%%|*}"
    while uci -q get 'stubby.@resolver[0]' >/dev/null 2>&1; do uci -q delete 'stubby.@resolver[0]'; done
    uci set stubby.global=stubby
    uci set stubby.global.manual=0
    uci set stubby.global.trigger=wan
    uci -q delete stubby.global.dns_transport || true
    uci add_list stubby.global.dns_transport=GETDNS_TRANSPORT_TLS
    uci set stubby.global.tls_authentication=1
    uci -q delete stubby.global.listen_address || true
    uci add_list stubby.global.listen_address='127.0.0.1@5453'
    for address in $addresses; do
        resolver="$(uci add stubby resolver)"
        uci set "stubby.$resolver.address=$address"
        uci set "stubby.$resolver.tls_auth_name=$auth_name"
        uci set "stubby.$resolver.tls_port=853"
    done
    backup_plain_dns
    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    uci add_list 'dhcp.@dnsmasq[0].server=127.0.0.1#5453'
    uci set 'dhcp.@dnsmasq[0].noresolv=1'
    uci commit stubby && uci commit dhcp
    [ ! -x /etc/init.d/https-dns-proxy ] || { /etc/init.d/https-dns-proxy stop >/dev/null 2>&1 || true; /etc/init.d/https-dns-proxy disable >/dev/null 2>&1 || true; }
    /etc/init.d/stubby enable >/dev/null 2>&1
    /etc/init.d/stubby restart >/dev/null 2>&1
    /etc/init.d/dnsmasq restart >/dev/null 2>&1
}

configure_doh() {
    provider="$1"
    enabled="$2"
    [ -x /etc/init.d/https-dns-proxy ] || return 1
    if [ "$enabled" != true ]; then
        /etc/init.d/https-dns-proxy stop >/dev/null 2>&1 || true
        /etc/init.d/https-dns-proxy disable >/dev/null 2>&1 || true
        restore_plain_dns
        /etc/init.d/dnsmasq restart >/dev/null 2>&1
        return
    fi
    case "$provider" in
        cloudflare) resolver_url='https://cloudflare-dns.com/dns-query'; bootstrap_dns='1.1.1.1,1.0.0.1' ;;
        quad9) resolver_url='https://dns.quad9.net/dns-query'; bootstrap_dns='9.9.9.9,149.112.112.112' ;;
        google) resolver_url='https://dns.google/dns-query'; bootstrap_dns='8.8.8.8,8.8.4.4' ;;
        *) return 1 ;;
    esac
    [ ! -x /etc/init.d/stubby ] || {
        /etc/init.d/stubby stop >/dev/null 2>&1 || true
        /etc/init.d/stubby disable >/dev/null 2>&1 || true
        restore_plain_dns
    }
    backup_plain_dns
    while uci -q get 'https-dns-proxy.@https-dns-proxy[0]' >/dev/null 2>&1; do uci -q delete 'https-dns-proxy.@https-dns-proxy[0]'; done
    section="$(uci add https-dns-proxy https-dns-proxy)"
    uci set "https-dns-proxy.$section.resolver_url=$resolver_url"
    uci set "https-dns-proxy.$section.bootstrap_dns=$bootstrap_dns"
    uci set "https-dns-proxy.$section.listen_port=5053"
    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    uci add_list 'dhcp.@dnsmasq[0].server=127.0.0.1#5053'
    uci set 'dhcp.@dnsmasq[0].noresolv=1'
    uci commit https-dns-proxy && uci commit dhcp
    /etc/init.d/https-dns-proxy enable >/dev/null 2>&1
    /etc/init.d/https-dns-proxy restart >/dev/null 2>&1
    /etc/init.d/dnsmasq restart >/dev/null 2>&1
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
        resolved="$(uci -q show wireless | sed -n "s/^wireless\.\([^.=]*\)=wifi-device$/\1/p" | sed -n "$((count + 1))p")"
        count=$((count + 1))
    done
    if [ "$count" -eq 1 ]; then
        printf '%s' "$resolved"
        return 0
    fi
    printf '%s' ""
    return 1
}

find_wifi_schedule() {
    requested_radio="$1"
    schedule_index=0
    while uci -q get "wrtmonitor.@wifi_schedule[$schedule_index]" >/dev/null 2>&1; do
        [ "$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].radio" 2>/dev/null || true)" != "$requested_radio" ] || {
            printf '@wifi_schedule[%s]' "$schedule_index"
            return 0
        }
        schedule_index=$((schedule_index + 1))
    done
    return 1
}

wifi_time_minutes() {
    value="$1"
    hour="${value%:*}"
    minute="${value#*:}"
    hour="${hour#0}"; minute="${minute#0}"
    [ -n "$hour" ] || hour=0
    [ -n "$minute" ] || minute=0
    printf '%s' $((hour * 60 + minute))
}

wifi_day_name() {
    case "$1" in 1) printf mon ;; 2) printf tue ;; 3) printf wed ;; 4) printf thu ;; 5) printf fri ;; 6) printf sat ;; *) printf sun ;; esac
}

wifi_schedule_has_day() {
    case " $1 " in *" $2 "*) return 0 ;; *) return 1 ;; esac
}

wifi_schedule_active_now() {
    days="$1"; start="$2"; stop="$3"
    day_number="$(date +%u 2>/dev/null || echo 1)"
    now_minutes="$(wifi_time_minutes "$(date +%H:%M 2>/dev/null || echo 00:00)")"
    start_minutes="$(wifi_time_minutes "$start")"
    stop_minutes="$(wifi_time_minutes "$stop")"
    today="$(wifi_day_name "$day_number")"
    previous_number=$((day_number - 1)); [ "$previous_number" -gt 0 ] || previous_number=7
    previous="$(wifi_day_name "$previous_number")"
    if [ "$start_minutes" -lt "$stop_minutes" ]; then
        wifi_schedule_has_day "$days" "$today" && [ "$now_minutes" -ge "$start_minutes" ] && [ "$now_minutes" -lt "$stop_minutes" ]
    else
        { wifi_schedule_has_day "$days" "$today" && [ "$now_minutes" -ge "$start_minutes" ]; } \
            || { wifi_schedule_has_day "$days" "$previous" && [ "$now_minutes" -lt "$stop_minutes" ]; }
    fi
}

apply_wifi_schedules() {
    schedule_index=0
    changed=0
    while uci -q get "wrtmonitor.@wifi_schedule[$schedule_index]" >/dev/null 2>&1; do
        schedule_ref="@wifi_schedule[$schedule_index]"
        schedule_enabled="$(uci -q get "wrtmonitor.$schedule_ref.enabled" 2>/dev/null || echo 0)"
        schedule_radio="$(uci -q get "wrtmonitor.$schedule_ref.radio" 2>/dev/null || true)"
        schedule_days="$(uci -q get "wrtmonitor.$schedule_ref.weekdays" 2>/dev/null || true)"
        schedule_start="$(uci -q get "wrtmonitor.$schedule_ref.start" 2>/dev/null || true)"
        schedule_stop="$(uci -q get "wrtmonitor.$schedule_ref.stop" 2>/dev/null || true)"
        if [ "$schedule_enabled" = "1" ] && [ -n "$schedule_radio" ] && [ -n "$schedule_start" ] && [ -n "$schedule_stop" ]; then
            desired_disabled=1
            wifi_schedule_active_now "$schedule_days" "$schedule_start" "$schedule_stop" && desired_disabled=0
            current_disabled="$(uci -q get "wireless.$schedule_radio.disabled" 2>/dev/null || echo 0)"
            if [ "$current_disabled" != "$desired_disabled" ]; then
                uci set "wireless.$schedule_radio.disabled=$desired_disabled"
                changed=1
            fi
        fi
        schedule_index=$((schedule_index + 1))
    done
    if [ "$changed" = "1" ]; then
        uci commit wireless && wifi reload >/dev/null 2>&1
    fi
}

find_mesh_iface() {
    requested_radio="$1"
    iface_index=0
    while uci -q get "wireless.@wifi-iface[$iface_index]" >/dev/null 2>&1; do
        iface_ref="@wifi-iface[$iface_index]"
        if [ "$(uci -q get "wireless.$iface_ref.device" 2>/dev/null || true)" = "$requested_radio" ] \
            && [ "$(uci -q get "wireless.$iface_ref.mode" 2>/dev/null || true)" = "mesh" ]; then
            printf '%s' "$iface_ref"
            return 0
        fi
        iface_index=$((iface_index + 1))
    done
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

openvpn_render_configs() {
    openvpn_dir="${WRTMONITOR_SYSTEM_ROOT:-}/etc/openvpn"
    mkdir -p "$openvpn_dir"
    for openvpn_ref in $(uci -q show openvpn 2>/dev/null | sed -n 's/^openvpn\.\([^.=]*\)=openvpn$/\1/p'); do
        config_b64="$(uci -q get "openvpn.$openvpn_ref.wrtmonitor_config_b64" 2>/dev/null || true)"
        [ -n "$config_b64" ] || continue
        config_path="$openvpn_dir/wrtmonitor-$openvpn_ref.conf"
        printf '%s' "$config_b64" | base64 -d >"$config_path" || return 1
        chmod 0600 "$config_path"
        uci set "openvpn.$openvpn_ref.config=/etc/openvpn/wrtmonitor-$openvpn_ref.conf"
    done
    uci commit openvpn
}

execute_command() {
    command_id="$1"
    command_type="$2"
    command_payload="${3:-{}}"
    status="done"
    result="{}"
    disconnect_after=0
    transaction_active=0
    recovery_mode="$(uci -q get "$CONFIG.recovery_mode" 2>/dev/null || echo 0)"
    if [ "$recovery_mode" = 1 ]; then
        case "$command_type" in
            wifi.status|network.interfaces|diagnostics.run|maintenance.packages.refresh|maintenance.backup.create|maintenance.logs.read|maintenance.diagnostics.bundle|maintenance.recovery.disable|agent.status) ;;
            *)
                result="$(command_failed_result "recovery mode blocks configuration changes")"
                api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"failed\",\"result\":$result}" >/dev/null || true
                return 1
                ;;
        esac
    fi
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
        network.set_ipv6)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; ipv6_iface="$(json_get_string "$payload_file" '@.interface')"; ipv6_enabled="$(json_get_bool "$payload_file" '@.enabled')"; assignment="$(json_get_number "$payload_file" '@.assignment_length')"; ra_mode="$(json_get_string "$payload_file" '@.ra')"; dhcpv6_mode="$(json_get_string "$payload_file" '@.dhcpv6')"; ndp_mode="$(json_get_string "$payload_file" '@.ndp')"; rm -f "$payload_file"
            if [ "$ipv6_enabled" = true ]; then uci set "network.$ipv6_iface.ip6assign=$assignment"; uci set "dhcp.$ipv6_iface.ra=$ra_mode"; uci set "dhcp.$ipv6_iface.dhcpv6=$dhcpv6_mode"; uci set "dhcp.$ipv6_iface.ndp=$ndp_mode"; else uci -q delete "network.$ipv6_iface.ip6assign" || true; uci set "dhcp.$ipv6_iface.ra=disabled"; uci set "dhcp.$ipv6_iface.dhcpv6=disabled"; uci set "dhcp.$ipv6_iface.ndp=disabled"; fi
            if uci commit network && uci commit dhcp && /etc/init.d/network reload >/dev/null 2>&1 && /etc/init.d/odhcpd restart >/dev/null 2>&1; then result="$(command_success_result "IPv6 configuration updated")"; else status=failed; result="$(command_failed_result "failed to update IPv6")"; fi
            ;;
        network.set_multiwan)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; multi_enabled="$(json_get_bool "$payload_file" '@.enabled')"; primary="$(json_get_string "$payload_file" '@.primary_interface')"; secondary="$(json_get_string "$payload_file" '@.secondary_interface')"; primary_metric="$(json_get_number "$payload_file" '@.primary_metric')"; secondary_metric="$(json_get_number "$payload_file" '@.secondary_metric')"; rm -f "$payload_file"
            uci set mwan3.wrtmonitor_primary=member; uci set "mwan3.wrtmonitor_primary.interface=$primary"; uci set "mwan3.wrtmonitor_primary.metric=$primary_metric"; uci set mwan3.wrtmonitor_primary.weight=1
            uci set mwan3.wrtmonitor_secondary=member; uci set "mwan3.wrtmonitor_secondary.interface=$secondary"; uci set "mwan3.wrtmonitor_secondary.metric=$secondary_metric"; uci set mwan3.wrtmonitor_secondary.weight=1
            uci set mwan3.wrtmonitor_policy=policy; uci -q delete mwan3.wrtmonitor_policy.use_member || true; uci add_list mwan3.wrtmonitor_policy.use_member=wrtmonitor_primary; uci add_list mwan3.wrtmonitor_policy.use_member=wrtmonitor_secondary; uci set "mwan3.globals.enabled=$( [ "$multi_enabled" = true ] && echo 1 || echo 0 )"
            if uci commit mwan3 && /etc/init.d/mwan3 restart >/dev/null 2>&1; then result="$(command_success_result "multi-WAN policy updated")"; else status=failed; result="$(command_failed_result "failed to update multi-WAN")"; fi
            ;;
        network.set_route)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; route_name="$(json_get_string "$payload_file" '@.name')"; route_iface="$(json_get_string "$payload_file" '@.interface')"; route_target="$(json_get_string "$payload_file" '@.target')"; route_gateway="$(json_get_string "$payload_file" '@.gateway')"; route_metric="$(json_get_number "$payload_file" '@.metric')"; rm -f "$payload_file"; route_ref="wrtmonitor_route_$route_name"; case "$route_target" in *:*) route_type=route6 ;; *) route_type=route ;; esac
            uci set "network.$route_ref=$route_type"; uci set "network.$route_ref.wrtmonitor_name=$route_name"; uci set "network.$route_ref.interface=$route_iface"; uci set "network.$route_ref.target=$route_target"; uci -q delete "network.$route_ref.gateway" || true; [ -z "$route_gateway" ] || uci set "network.$route_ref.gateway=$route_gateway"; uci set "network.$route_ref.metric=$route_metric"
            if uci commit network && /etc/init.d/network reload >/dev/null 2>&1; then result="$(command_success_result "static route updated")"; else status=failed; result="$(command_failed_result "failed to update route")"; fi
            ;;
        network.delete_route)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; route_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"
            if uci -q delete "network.wrtmonitor_route_$route_name" && uci commit network && /etc/init.d/network reload >/dev/null 2>&1; then result="$(command_success_result "static route deleted")"; else status=failed; result="$(command_failed_result "route not found")"; fi
            ;;
        network.set_ddns)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; ddns_name="$(json_get_string "$payload_file" '@.name')"; ddns_enabled="$(json_get_bool "$payload_file" '@.enabled')"; provider="$(json_get_string "$payload_file" '@.provider')"; domain="$(json_get_string "$payload_file" '@.domain')"; ddns_user="$(json_get_string "$payload_file" '@.username')"; ddns_password="$(json_get_string "$payload_file" '@.password')"; ddns_iface="$(json_get_string "$payload_file" '@.interface')"; rm -f "$payload_file"; ddns_ref="wrtmonitor_$ddns_name"
            uci set "ddns.$ddns_ref=service"; uci set "ddns.$ddns_ref.enabled=$( [ "$ddns_enabled" = true ] && echo 1 || echo 0 )"; uci set "ddns.$ddns_ref.service_name=$provider"; uci set "ddns.$ddns_ref.domain=$domain"; uci set "ddns.$ddns_ref.username=$ddns_user"; uci set "ddns.$ddns_ref.password=$ddns_password"; uci set "ddns.$ddns_ref.interface=$ddns_iface"; uci set "ddns.$ddns_ref.ip_source=network"; uci set "ddns.$ddns_ref.ip_network=$ddns_iface"
            if uci commit ddns && /etc/init.d/ddns restart >/dev/null 2>&1; then result="$(command_success_result "DDNS service updated")"; else status=failed; result="$(command_failed_result "failed to update DDNS")"; fi
            ;;
        network.set_upnp)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; upnp_enabled="$(json_get_bool "$payload_file" '@.enabled')"; secure_mode="$(json_get_bool "$payload_file" '@.secure_mode')"; rm -f "$payload_file"; uci set "upnpd.config.enabled=$( [ "$upnp_enabled" = true ] && echo 1 || echo 0 )"; uci set "upnpd.config.secure_mode=$( [ "$secure_mode" = true ] && echo 1 || echo 0 )"
            if uci commit upnpd && /etc/init.d/miniupnpd restart >/dev/null 2>&1; then result="$(command_success_result "UPnP configuration updated")"; else status=failed; result="$(command_failed_result "failed to update UPnP")"; fi
            ;;
        vpn.wireguard.set_interface)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; wg_name="$(json_get_string "$payload_file" '@.name')"; wg_enabled="$(json_get_bool "$payload_file" '@.enabled')"; wg_mode="$(json_get_string "$payload_file" '@.mode')"; wg_addresses="$(jsonfilter -i "$payload_file" -e '@.addresses[*]' 2>/dev/null || true)"; wg_port="$(json_get_number "$payload_file" '@.listen_port')"; wg_private="$(json_get_string "$payload_file" '@.private_key')"; wg_mtu="$(json_get_number "$payload_file" '@.mtu')"; rm -f "$payload_file"
            if [ -z "$wg_private" ]; then wg_private="$(wg genkey 2>/dev/null || true)"; fi
            uci set "network.$wg_name=interface"; uci set "network.$wg_name.proto=wireguard"; uci set "network.$wg_name.private_key=$wg_private"; uci set "network.$wg_name.listen_port=$wg_port"; uci set "network.$wg_name.mtu=$wg_mtu"; uci set "network.$wg_name.wrtmonitor_mode=$wg_mode"; uci set "network.$wg_name.disabled=$( [ "$wg_enabled" = true ] && printf 0 || printf 1 )"; uci -q delete "network.$wg_name.addresses" || true
            for wg_address in $wg_addresses; do uci add_list "network.$wg_name.addresses=$wg_address"; done
            if [ -n "$wg_private" ] && uci commit network; then result="$(command_success_result "WireGuard interface updated" "\"interface\":\"$(json_escape "$wg_name")\"")"; (sleep 2; ifdown "$wg_name" >/dev/null 2>&1 || true; if [ "$wg_enabled" = true ]; then ifup "$wg_name" >/dev/null 2>&1 || true; fi) & else status=failed; result="$(command_failed_result "failed to update WireGuard interface")"; fi
            ;;
        vpn.wireguard.set_peer)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; wg_iface="$(json_get_string "$payload_file" '@.interface')"; peer_name="$(json_get_string "$payload_file" '@.name')"; peer_public="$(json_get_string "$payload_file" '@.public_key')"; peer_psk="$(json_get_string "$payload_file" '@.preshared_key')"; peer_allowed="$(jsonfilter -i "$payload_file" -e '@.allowed_ips[*]' 2>/dev/null || true)"; peer_endpoint="$(json_get_string "$payload_file" '@.endpoint')"; peer_keepalive="$(json_get_number "$payload_file" '@.persistent_keepalive')"; peer_route="$(json_get_bool "$payload_file" '@.route_allowed_ips')"; rm -f "$payload_file"; peer_ref="wrtmonitor_wgpeer_${wg_iface}_${peer_name}"
            uci set "network.$peer_ref=wireguard_$wg_iface"; uci set "network.$peer_ref.wrtmonitor_name=$peer_name"; uci set "network.$peer_ref.public_key=$peer_public"; uci set "network.$peer_ref.route_allowed_ips=$( [ "$peer_route" = true ] && printf 1 || printf 0 )"; uci set "network.$peer_ref.persistent_keepalive=$peer_keepalive"; uci -q delete "network.$peer_ref.preshared_key" || true; [ -z "$peer_psk" ] || uci set "network.$peer_ref.preshared_key=$peer_psk"; uci -q delete "network.$peer_ref.allowed_ips" || true; for allowed in $peer_allowed; do uci add_list "network.$peer_ref.allowed_ips=$allowed"; done; uci -q delete "network.$peer_ref.endpoint_host" || true; uci -q delete "network.$peer_ref.endpoint_port" || true
            if [ -n "$peer_endpoint" ]; then peer_port="${peer_endpoint##*:}"; peer_host="${peer_endpoint%:*}"; peer_host="$(printf '%s' "$peer_host" | sed 's/^\[//; s/\]$//')"; uci set "network.$peer_ref.endpoint_host=$peer_host"; uci set "network.$peer_ref.endpoint_port=$peer_port"; fi
            if uci commit network && ifup "$wg_iface" >/dev/null 2>&1; then result="$(command_success_result "WireGuard peer updated")"; else status=failed; result="$(command_failed_result "failed to update WireGuard peer")"; fi
            ;;
        vpn.wireguard.delete_peer)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; wg_iface="$(json_get_string "$payload_file" '@.interface')"; peer_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; if uci -q delete "network.wrtmonitor_wgpeer_${wg_iface}_${peer_name}" && uci commit network; then ifup "$wg_iface" >/dev/null 2>&1 || true; result="$(command_success_result "WireGuard peer deleted")"; else status=failed; result="$(command_failed_result "WireGuard peer not found")"; fi
            ;;
        vpn.wireguard.export_peer)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; wg_iface="$(json_get_string "$payload_file" '@.interface')"; peer_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; peer_ref="wrtmonitor_wgpeer_${wg_iface}_${peer_name}"; server_private="$(uci -q get "network.$wg_iface.private_key" 2>/dev/null || true)"; server_public="$(printf '%s' "$server_private" | wg pubkey 2>/dev/null || true)"; peer_allowed="$(uci -q get "network.$peer_ref.allowed_ips" 2>/dev/null || true)"; server_port="$(uci -q get "network.$wg_iface.listen_port" 2>/dev/null || echo 51820)"; if [ -n "$server_public" ] && [ -n "$peer_allowed" ]; then export_config="[Interface]\nPrivateKey = <PRIVATE_KEY>\nAddress = $peer_allowed\n\n[Peer]\nPublicKey = $server_public\nAllowedIPs = 0.0.0.0/0, ::/0\nEndpoint = <SERVER_HOST>:$server_port\nPersistentKeepalive = 25"; result="$(command_success_result "WireGuard peer profile exported" "\"config\":\"$(json_escape "$export_config")\"")"; else status=failed; result="$(command_failed_result "WireGuard peer or interface not found")"; fi
            ;;
        vpn.openvpn.set_client)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; ovpn_name="$(json_get_string "$payload_file" '@.name')"; ovpn_enabled="$(json_get_bool "$payload_file" '@.enabled')"; ovpn_config="$(json_get_string "$payload_file" '@.config')"; rm -f "$payload_file"; ovpn_ref="wrtmonitor_$ovpn_name"; ovpn_b64="$(printf '%s\n' "$ovpn_config" | base64 | tr -d '\n')"; uci set "openvpn.$ovpn_ref=openvpn"; uci set "openvpn.$ovpn_ref.enabled=$( [ "$ovpn_enabled" = true ] && printf 1 || printf 0 )"; uci set "openvpn.$ovpn_ref.wrtmonitor_name=$ovpn_name"; uci set "openvpn.$ovpn_ref.wrtmonitor_config_b64=$ovpn_b64"
            if openvpn_render_configs && /etc/init.d/openvpn restart >/dev/null 2>&1; then result="$(command_success_result "OpenVPN client imported")"; else status=failed; result="$(command_failed_result "failed to import OpenVPN client")"; fi
            ;;
        vpn.openvpn.delete_client)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; ovpn_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; ovpn_ref="wrtmonitor_$ovpn_name"; if uci -q delete "openvpn.$ovpn_ref" && uci commit openvpn; then rm -f "${WRTMONITOR_SYSTEM_ROOT:-}/etc/openvpn/wrtmonitor-$ovpn_ref.conf"; /etc/init.d/openvpn restart >/dev/null 2>&1 || true; result="$(command_success_result "OpenVPN client deleted")"; else status=failed; result="$(command_failed_result "OpenVPN client not found")"; fi
            ;;
        vpn.policy.set)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; policy_name="$(json_get_string "$payload_file" '@.name')"; policy_enabled="$(json_get_bool "$payload_file" '@.enabled')"; policy_iface="$(json_get_string "$payload_file" '@.interface')"; policy_source="$(json_get_string "$payload_file" '@.source')"; policy_destination="$(json_get_string "$payload_file" '@.destination')"; policy_protocol="$(json_get_string "$payload_file" '@.protocol')"; rm -f "$payload_file"; policy_ref="wrtmonitor_$policy_name"; uci set "pbr.$policy_ref=policy"; uci set "pbr.$policy_ref.name=WrtMonitor-$policy_name"; uci set "pbr.$policy_ref.enabled=$( [ "$policy_enabled" = true ] && printf 1 || printf 0 )"; uci set "pbr.$policy_ref.interface=$policy_iface"; uci -q delete "pbr.$policy_ref.src_addr" || true; uci -q delete "pbr.$policy_ref.dest_addr" || true; [ -z "$policy_source" ] || uci set "pbr.$policy_ref.src_addr=$policy_source"; [ -z "$policy_destination" ] || uci set "pbr.$policy_ref.dest_addr=$policy_destination"; uci set "pbr.$policy_ref.proto=$policy_protocol"
            if uci commit pbr && /etc/init.d/pbr restart >/dev/null 2>&1; then result="$(command_success_result "VPN policy updated")"; else status=failed; result="$(command_failed_result "failed to update VPN policy")"; fi
            ;;
        vpn.policy.delete)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; policy_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; if uci -q delete "pbr.wrtmonitor_$policy_name" && uci commit pbr; then /etc/init.d/pbr restart >/dev/null 2>&1 || true; result="$(command_success_result "VPN policy deleted")"; else status=failed; result="$(command_failed_result "VPN policy not found")"; fi
            ;;
        firewall.set_zone)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; zone_section="$(json_get_string "$payload_file" '@.section')"; zone_name="$(json_get_string "$payload_file" '@.name')"; zone_networks="$(jsonfilter -i "$payload_file" -e '@.networks[*]' 2>/dev/null)"; zone_input="$(json_get_string "$payload_file" '@.input')"; zone_output="$(json_get_string "$payload_file" '@.output')"; zone_forward="$(json_get_string "$payload_file" '@.forward')"; masquerade="$(json_get_bool "$payload_file" '@.masquerade')"; rm -f "$payload_file"; zone_ref="${zone_section:-wrtmonitor_zone_$zone_name}"; uci set "firewall.$zone_ref=zone"; uci set "firewall.$zone_ref.name=$zone_name"; uci set "firewall.$zone_ref.input=$zone_input"; uci set "firewall.$zone_ref.output=$zone_output"; uci set "firewall.$zone_ref.forward=$zone_forward"; uci set "firewall.$zone_ref.masq=$( [ "$masquerade" = true ] && echo 1 || echo 0 )"; uci -q delete "firewall.$zone_ref.network" || true; for item in $zone_networks; do uci add_list "firewall.$zone_ref.network=$item"; done
            if uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "firewall zone updated")"; else status=failed; result="$(command_failed_result "failed to update firewall zone")"; fi
            ;;
        firewall.delete_zone)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; zone_section="$(json_get_string "$payload_file" '@.section')"; zone_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; zone_ref="${zone_section:-wrtmonitor_zone_$zone_name}"
            if [ "$zone_name" = lan ] || [ "$zone_name" = wan ]; then status=failed; result="$(command_failed_result "core firewall zone cannot be deleted")"
            elif uci -q delete "firewall.$zone_ref" && uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "firewall zone deleted")"; else status=failed; result="$(command_failed_result "firewall zone not found")"; fi
            ;;
        firewall.set_forwarding)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; forward_section="$(json_get_string "$payload_file" '@.section')"; forward_src="$(json_get_string "$payload_file" '@.src')"; forward_dest="$(json_get_string "$payload_file" '@.dest')"; forward_enabled="$(json_get_bool "$payload_file" '@.enabled')"; rm -f "$payload_file"; forward_ref="${forward_section:-wrtmonitor_forward_${forward_src}_${forward_dest}}"
            if [ "$forward_enabled" = true ]; then uci set "firewall.$forward_ref=forwarding"; uci set "firewall.$forward_ref.src=$forward_src"; uci set "firewall.$forward_ref.dest=$forward_dest"; else uci -q delete "firewall.$forward_ref" || true; fi
            if uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "firewall forwarding updated")"; else status=failed; result="$(command_failed_result "failed to update forwarding")"; fi
            ;;
        firewall.delete_forwarding)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; forward_section="$(json_get_string "$payload_file" '@.section')"; forward_src="$(json_get_string "$payload_file" '@.src')"; forward_dest="$(json_get_string "$payload_file" '@.dest')"; rm -f "$payload_file"; forward_ref="${forward_section:-wrtmonitor_forward_${forward_src}_${forward_dest}}"
            if uci -q delete "firewall.$forward_ref" && uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "firewall forwarding deleted")"; else status=failed; result="$(command_failed_result "firewall forwarding not found")"; fi
            ;;
        firewall.set_rule)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; rule_section="$(json_get_string "$payload_file" '@.section')"; rule_name="$(json_get_string "$payload_file" '@.name')"; rule_src="$(json_get_string "$payload_file" '@.src')"; rule_dest="$(json_get_string "$payload_file" '@.dest')"; rule_proto="$(json_get_string "$payload_file" '@.protocol')"; rule_src_ip="$(json_get_string "$payload_file" '@.src_ip')"; rule_dest_ip="$(json_get_string "$payload_file" '@.dest_ip')"; rule_src_port="$(json_get_string "$payload_file" '@.src_port')"; rule_dest_port="$(json_get_string "$payload_file" '@.dest_port')"; rule_target="$(json_get_string "$payload_file" '@.target')"; rm -f "$payload_file"; rule_ref="${rule_section:-wrtmonitor_rule_$rule_name}"; [ "$rule_proto" != tcpudp ] || rule_proto='tcp udp'; uci set "firewall.$rule_ref=rule"; uci set "firewall.$rule_ref.name=$rule_name"; for option in src dest src_ip dest_ip src_port dest_port; do uci -q delete "firewall.$rule_ref.$option" || true; done; [ "$rule_src" = '*' ] || uci set "firewall.$rule_ref.src=$rule_src"; [ "$rule_dest" = '*' ] || uci set "firewall.$rule_ref.dest=$rule_dest"; uci set "firewall.$rule_ref.proto=$rule_proto"; uci set "firewall.$rule_ref.target=$rule_target"; [ -z "$rule_src_ip" ] || uci set "firewall.$rule_ref.src_ip=$rule_src_ip"; [ -z "$rule_dest_ip" ] || uci set "firewall.$rule_ref.dest_ip=$rule_dest_ip"; [ -z "$rule_src_port" ] || uci set "firewall.$rule_ref.src_port=$rule_src_port"; [ -z "$rule_dest_port" ] || uci set "firewall.$rule_ref.dest_port=$rule_dest_port"
            if uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "firewall rule updated")"; else status=failed; result="$(command_failed_result "failed to update firewall rule")"; fi
            ;;
        firewall.delete_rule)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; rule_section="$(json_get_string "$payload_file" '@.section')"; rule_name="$(json_get_string "$payload_file" '@.name')"; rm -f "$payload_file"; rule_ref="${rule_section:-wrtmonitor_rule_$rule_name}"; if uci -q delete "firewall.$rule_ref" && uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then result="$(command_success_result "firewall rule deleted")"; else status=failed; result="$(command_failed_result "rule not found")"; fi
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
        dns.install_encrypted|dns.install_dot|dns.install_doh)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; dns_mode="$(json_get_string "$payload_file" '@.mode')"; rm -f "$payload_file"
            [ -n "$dns_mode" ] || case "$command_type" in dns.install_dot) dns_mode="dot" ;; dns.install_doh) dns_mode="doh" ;; esac
            case "$dns_mode" in dot) dns_package=stubby ;; doh) dns_package=https-dns-proxy ;; *) dns_package="" ;; esac
            if [ -n "$dns_package" ] && package_refresh_indexes >/dev/null 2>&1 && package_apply install "$dns_package" >/dev/null 2>&1; then
                result="$(command_success_result "encrypted DNS package installed" "\"mode\":\"$(json_escape "$dns_mode")\",\"package\":\"$(json_escape "$dns_package")\"")"
            else status="failed"; result="$(command_failed_result "failed to install encrypted DNS package")"; fi
            ;;
        dns.set_encrypted|dns.set_dot|dns.set_doh)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; dns_mode="$(json_get_string "$payload_file" '@.mode')"; dns_provider="$(json_get_string "$payload_file" '@.provider')"; dns_enabled="$(json_get_bool "$payload_file" '@.enabled')"; rm -f "$payload_file"
            [ -n "$dns_mode" ] || case "$command_type" in dns.set_dot) dns_mode="dot" ;; dns.set_doh) dns_mode="doh" ;; esac
            case "$dns_mode" in dot) configure_dns_result=configure_dot ;; doh) configure_dns_result=configure_doh ;; *) configure_dns_result="" ;; esac
            if [ -n "$configure_dns_result" ] && "$configure_dns_result" "$dns_provider" "$dns_enabled"; then
                result="$(command_success_result "encrypted DNS configuration applied" "\"mode\":\"$(json_escape "$dns_mode")\",\"provider\":\"$(json_escape "$dns_provider")\",\"enabled\":$dns_enabled")"
            else status="failed"; result="$(command_failed_result "failed to configure encrypted DNS")"; fi
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
            rm -f "$payload_file"
            client_suffix="$(printf '%s' "$client_mac" | tr -d ':')"
            client_ref="wrtmonitor_policy_$client_suffix"
            qos_ref="wrtmonitor_qos_$client_suffix"
            backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -z "$backup_file" ]; then
                status="failed"; result="$(command_failed_result "failed to create firewall backup")"
            else
                uci -q delete "firewall.$client_ref" || true
                uci -q delete "firewall.$qos_ref" || true
                if [ "$client_blocked" = "true" ] || [ "$schedule_enabled" = "true" ]; then
                    uci set "firewall.$client_ref=rule"
                    uci set "firewall.$client_ref.name=WrtMonitor policy $client_mac"
                    uci set "firewall.$client_ref.src=lan"
                    uci set "firewall.$client_ref.dest=wan"
                    uci set "firewall.$client_ref.src_mac=$client_mac"
                    uci set "firewall.$client_ref.target=REJECT"
                    if [ "$schedule_enabled" = "true" ]; then
                        [ -z "$schedule_days" ] || uci set "firewall.$client_ref.weekdays=$schedule_days"
                        [ -z "$schedule_start" ] || uci set "firewall.$client_ref.start_time=$schedule_start"
                        [ -z "$schedule_stop" ] || uci set "firewall.$client_ref.stop_time=$schedule_stop"
                    fi
                fi
                if [ -n "$qos_priority" ] && [ "$qos_priority" != "normal" ]; then
                    case "$qos_priority" in low) policy_mark="0x10" ;; high) policy_mark="0x30" ;; realtime) policy_mark="0x40" ;; *) policy_mark="0x20" ;; esac
                    uci set "firewall.$qos_ref=rule"
                    uci set "firewall.$qos_ref.name=WrtMonitor priority $client_mac"
                    uci set "firewall.$qos_ref.src=lan"
                    uci set "firewall.$qos_ref.src_mac=$client_mac"
                    uci set "firewall.$qos_ref.target=MARK"
                    uci set "firewall.$qos_ref.set_mark=$policy_mark"
                fi
                if uci commit firewall && /etc/init.d/firewall reload >/dev/null 2>&1; then
                    result="$(command_success_result "client policy applied" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\",\"qos_priority\":\"$(json_escape "$qos_priority")\",\"download_kbps\":${download_kbps:-0},\"upload_kbps\":${upload_kbps:-0}")"
                else
                    status="failed"; result="$(command_failed_result "failed to apply client policy")"
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
                && uci commit sqm \
                && /etc/init.d/sqm restart >/dev/null 2>&1; then
                result="$(command_success_result "SQM configuration applied" "\"backup\":\"$(json_escape "$sqm_backup")\",\"interface\":\"$(json_escape "$sqm_interface")\",\"download_kbps\":$sqm_download,\"upload_kbps\":$sqm_upload")"
            else
                status="failed"; result="$(command_failed_result "failed to apply SQM configuration")"
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
        maintenance.packages.refresh)
            package_manager_value="$(package_manager_name 2>/dev/null || true)"
            if [ -n "$package_manager_value" ] && package_refresh_indexes >/dev/null 2>&1; then
                upgrades="$(package_list_upgradeable | head -n 50 | tr '\n' ';')"
                result="$(command_success_result "package lists refreshed" "\"manager\":\"$package_manager_value\",\"upgradable\":\"$(json_escape "$upgrades")\"")"
            else status=failed; result="$(command_failed_result "apk/opkg package index update failed")"; fi
            ;;
        maintenance.package.install|maintenance.package.remove)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; package="$(json_get_string "$payload_file" '@.package')"; rm -f "$payload_file"
            package_action=install; [ "$command_type" = maintenance.package.remove ] && package_action=remove
            case "$package_action:$package" in
                remove:base-files|remove:busybox|remove:dnsmasq|remove:dropbear|remove:firewall4|remove:kernel|remove:libc|remove:netifd|remove:procd|remove:ubus|remove:uci|remove:wrtmonitor|remove:wrtmonitor-agent)
                    status=failed; result="$(command_failed_result "system package removal is not allowed")"
                    ;;
                *)
                    if package_output="$(package_apply "$package_action" "$package" 2>&1)"; then
                        if [ "$package_action" = install ] && [ "$package" = nlbwmon ]; then
                            if ! ensure_nlbwmon_runtime >/dev/null 2>&1; then
                                status="failed"
                                result="$(command_failed_result "nlbwmon installed, but runtime initialization failed")"
                            fi
                        fi
                        if [ "$status" != failed ]; then
                            result="$(command_success_result "package operation completed" "\"package\":\"$(json_escape "$package")\",\"manager\":\"$(package_manager_name)\",\"output\":\"$(json_escape "$package_output")\"")"
                        fi
                    else status=failed; result="$(command_failed_result "$package_output")"; fi
                    ;;
            esac
            ;;
        maintenance.backup.create)
            backup_path="/tmp/wrtmonitor-backup-$command_id.tar.gz"
            if sysupgrade -b "$backup_path" >/dev/null 2>&1 && [ -s "$backup_path" ]; then backup_b64="$(base64 <"$backup_path" | tr -d '\n')"; result="$(command_success_result "configuration backup created" "\"filename\":\"wrtmonitor-openwrt-backup.tar.gz\",\"archive_base64\":\"$backup_b64\"")"; rm -f "$backup_path"; else status=failed; result="$(command_failed_result "failed to create configuration backup")"; fi
            ;;
        maintenance.backup.restore)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; restore_b64="$(json_get_string "$payload_file" '@.archive_base64')"; rm -f "$payload_file"; restore_path="/tmp/wrtmonitor-restore-$command_id.tar.gz"
            if ! printf '%s' "$restore_b64" | base64 -d >"$restore_path" 2>/dev/null; then status=failed; result="$(command_failed_result "backup decoding failed")"
            elif ! tar -tzf "$restore_path" 2>/dev/null | awk 'BEGIN{ok=1} /^\//{ok=0} /(^|\/)\.\.($|\/)/{ok=0} !/^etc\//{ok=0} END{exit !ok}'; then status=failed; result="$(command_failed_result "backup contains unsafe paths")"
            elif sysupgrade -r "$restore_path" >/dev/null 2>&1; then result="$(command_success_result "configuration backup restored; reboot recommended")"; else status=failed; result="$(command_failed_result "configuration restore failed")"; fi
            rm -f "$restore_path"
            ;;
        maintenance.sysupgrade.check)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; firmware_url="$(json_get_string "$payload_file" '@.url')"; firmware_sha="$(json_get_string "$payload_file" '@.sha256')"; expected_model="$(json_get_string "$payload_file" '@.expected_model')"; preserve_config="$(json_get_bool "$payload_file" '@.preserve_config')"; rm -f "$payload_file"; firmware_path=/tmp/wrtmonitor-sysupgrade.bin
            local_model="$(cat /tmp/sysinfo/model 2>/dev/null || true)"
            if [ -n "$expected_model" ] && [ "$expected_model" != "$local_model" ]; then status=failed; result="$(command_failed_result "firmware model does not match router")"
            elif ! curl -fsS --connect-timeout 15 --max-time 600 -o "$firmware_path" "$firmware_url"; then status=failed; result="$(command_failed_result "firmware download failed")"
            elif [ "$(sha256sum "$firmware_path" | awk '{print $1}')" != "$firmware_sha" ]; then status=failed; result="$(command_failed_result "firmware checksum mismatch")"
            elif firmware_size="$(wc -c <"$firmware_path" | tr -d ' ')" && tmp_free_bytes="$(df -k /tmp | awk 'NR == 2 {print $4 * 1024}')" && [ "$tmp_free_bytes" -lt 8388608 ]; then status=failed; result="$(command_failed_result "not enough free space to safely validate firmware")"
            elif ! sysupgrade -T "$firmware_path" >/tmp/wrtmonitor-sysupgrade-check.log 2>&1; then status=failed; result="$(command_failed_result "$(cat /tmp/wrtmonitor-sysupgrade-check.log 2>/dev/null || echo firmware validation failed)")"
            else uci set "$CONFIG.staged_firmware_sha256=$firmware_sha"; uci set "$CONFIG.staged_firmware_preserve=$( [ "$preserve_config" = true ] && printf 1 || printf 0 )"; uci commit wrtmonitor; firmware_size="$(wc -c <"$firmware_path" | tr -d ' ')"; result="$(command_success_result "firmware staged and validated" "\"sha256\":\"$firmware_sha\",\"size_bytes\":$firmware_size,\"model\":\"$(json_escape "$local_model")\"")"; fi
            rm -f /tmp/wrtmonitor-sysupgrade-check.log
            ;;
        maintenance.sysupgrade.apply)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; firmware_sha="$(json_get_string "$payload_file" '@.sha256')"; preserve_config="$(json_get_bool "$payload_file" '@.preserve_config')"; rm -f "$payload_file"; firmware_path=/tmp/wrtmonitor-sysupgrade.bin; staged_sha="$(uci -q get "$CONFIG.staged_firmware_sha256" 2>/dev/null || true)"
            if [ ! -s "$firmware_path" ] || [ "$staged_sha" != "$firmware_sha" ] || [ "$(sha256sum "$firmware_path" | awk '{print $1}')" != "$firmware_sha" ]; then status=failed; result="$(command_failed_result "validated firmware is not staged")"
            else result="$(command_success_result "sysupgrade scheduled")"; if [ "$preserve_config" = true ]; then (sleep 2; sysupgrade "$firmware_path") >/dev/null 2>&1 & else (sleep 2; sysupgrade -n "$firmware_path") >/dev/null 2>&1 & fi; fi
            ;;
        maintenance.logs.read)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; log_lines="$(json_get_number "$payload_file" '@.lines')"; rm -f "$payload_file"; logs="$(logread 2>/dev/null | tail -n "$log_lines")"; result="$(command_success_result "system log collected" "\"logs\":\"$(json_escape "$logs")\"")"
            ;;
        maintenance.process.signal)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; process_pid="$(json_get_number "$payload_file" '@.pid')"; process_signal="$(json_get_string "$payload_file" '@.signal')"; rm -f "$payload_file"; if kill -"$process_signal" "$process_pid" 2>/dev/null; then result="$(command_success_result "signal sent to process")"; else status=failed; result="$(command_failed_result "failed to signal process")"; fi
            ;;
        maintenance.cron.set)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; cron_content="$(json_get_string "$payload_file" '@.content')"; rm -f "$payload_file"; cron_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root"; cp "$cron_path" "$cron_path.wrtmonitor.bak" 2>/dev/null || true; if printf '%s' "$cron_content" >"$cron_path" && /etc/init.d/cron restart >/dev/null 2>&1; then result="$(command_success_result "cron updated")"; else status=failed; result="$(command_failed_result "failed to update cron")"; fi
            ;;
        maintenance.diagnostics.bundle)
            bundle_dir="/tmp/wrtmonitor-diagnostics-$command_id"; bundle_path="$bundle_dir.tar.gz"; mkdir -p "$bundle_dir"; ubus call system board >"$bundle_dir/board.json" 2>&1 || true; ubus call system info >"$bundle_dir/system.json" 2>&1 || true; ubus call network.interface dump >"$bundle_dir/network.json" 2>&1 || true; logread 2>/dev/null | tail -n 500 >"$bundle_dir/logread.txt"; ps w >"$bundle_dir/processes.txt" 2>&1 || true; df -h >"$bundle_dir/storage.txt" 2>&1 || true; package_list_installed >"$bundle_dir/packages.txt" 2>&1 || true; capabilities_json >"$bundle_dir/capabilities.json"; if tar -czf "$bundle_path" -C "$bundle_dir" .; then bundle_b64="$(base64 <"$bundle_path" | tr -d '\n')"; result="$(command_success_result "diagnostic bundle created" "\"filename\":\"wrtmonitor-diagnostics.tar.gz\",\"bundle_base64\":\"$bundle_b64\"")"; else status=failed; result="$(command_failed_result "failed to create diagnostic bundle")"; fi; rm -rf "$bundle_dir" "$bundle_path"
            ;;
        maintenance.recovery.enable)
            recovery_path=/tmp/wrtmonitor-recovery.tar.gz; if sysupgrade -b "$recovery_path" >/dev/null 2>&1; then uci set "$CONFIG.recovery_mode=1"; uci commit wrtmonitor; result="$(command_success_result "recovery mode enabled")"; else status=failed; result="$(command_failed_result "failed to create recovery backup")"; fi
            ;;
        maintenance.recovery.disable)
            uci set "$CONFIG.recovery_mode=0"; uci commit wrtmonitor; result="$(command_success_result "recovery mode disabled")"
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
