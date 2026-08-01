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
    code="${2:-}"
    retryable="${3:-false}"
    if [ -z "$code" ]; then
        case "$message" in
            *"not found"*|*"unavailable"*|*"not installed"*) code="resource_unavailable" ;;
            *"invalid"*|*"required"*|*"must "*|*"unsafe"*) code="invalid_request" ;;
            *"timeout"*|*"temporarily"*|*"download failed"*) code="temporary_failure"; retryable=true ;;
            *"backup"*|*"rollback"*) code="safety_check_failed" ;;
            *"permission"*|*"not allowed"*|*"blocked"*) code="operation_blocked" ;;
            *"post-condition"*) code="post_condition_failed" ;;
            *) code="command_failed" ;;
        esac
    fi
    printf '{"error":"%s","error_detail":{"code":"%s","message":"%s","retryable":%s}}' \
        "$(json_escape "$message")" \
        "$(json_escape "$code")" \
        "$(json_escape "$message")" \
        "$retryable"
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
        service_action stubby stop 20 >/dev/null 2>&1 || true
        service_action stubby disable 20 >/dev/null 2>&1 || true
        restore_plain_dns
        service_action dnsmasq restart 20 >/dev/null 2>&1
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
    [ ! -x /etc/init.d/https-dns-proxy ] || { service_action https-dns-proxy stop 20 >/dev/null 2>&1 || true; service_action https-dns-proxy disable 20 >/dev/null 2>&1 || true; }
    /etc/init.d/stubby enable >/dev/null 2>&1
    service_action stubby restart 20 >/dev/null 2>&1
    service_action dnsmasq restart 20 >/dev/null 2>&1
}

configure_doh() {
    provider="$1"
    enabled="$2"
    [ -x /etc/init.d/https-dns-proxy ] || return 1
    if [ "$enabled" != true ]; then
        service_action https-dns-proxy stop 20 >/dev/null 2>&1 || true
        service_action https-dns-proxy disable 20 >/dev/null 2>&1 || true
        restore_plain_dns
        service_action dnsmasq restart 20 >/dev/null 2>&1
        return
    fi
    case "$provider" in
        cloudflare) resolver_url='https://cloudflare-dns.com/dns-query'; bootstrap_dns='1.1.1.1,1.0.0.1' ;;
        quad9) resolver_url='https://dns.quad9.net/dns-query'; bootstrap_dns='9.9.9.9,149.112.112.112' ;;
        google) resolver_url='https://dns.google/dns-query'; bootstrap_dns='8.8.8.8,8.8.4.4' ;;
        *) return 1 ;;
    esac
    [ ! -x /etc/init.d/stubby ] || {
        service_action stubby stop 20 >/dev/null 2>&1 || true
        service_action stubby disable 20 >/dev/null 2>&1 || true
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
    service_action https-dns-proxy restart 20 >/dev/null 2>&1
    service_action dnsmasq restart 20 >/dev/null 2>&1
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
