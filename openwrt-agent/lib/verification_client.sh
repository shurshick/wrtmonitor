verify_client_policy_postcondition() {
    payload_file="$1"
    mac="$(json_get_string "$payload_file" '@.mac')"
    [ -n "$mac" ] || return 1
    blocked="$(json_get_bool "$payload_file" '@.blocked')"
    schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
    weekdays="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
    start="$(json_get_string "$payload_file" '@.schedule.start')"
    stop="$(json_get_string "$payload_file" '@.schedule.stop')"
    priority="$(json_get_string "$payload_file" '@.qos.priority')"
    download="$(json_get_number "$payload_file" '@.qos.download_kbps')"
    upload="$(json_get_number "$payload_file" '@.qos.upload_kbps')"
    dns="$(json_get_string "$payload_file" '@.dns.provider')"
    [ -n "$priority" ] || priority=normal
    [ -n "$download" ] || download=0
    [ -n "$upload" ] || upload=0
    [ -n "$dns" ] || dns=none
    suffix="$(client_policy_suffix "$mac")"
    policy_ref="wrtmonitor_policy_$suffix"
    policy_after_ref="${policy_ref}_after"
    policy_days_ref="${policy_ref}_days"
    qos_ref="wrtmonitor_qos_$suffix"
    dns_ref="wrtmonitor_dns_$suffix"
    dot_ref="wrtmonitor_dot_$suffix"
    state_ref="$(client_policy_section "$mac")"

    verify_uci_value "wrtmonitor.$state_ref.mac" "$mac" || return 1
    verify_uci_value "wrtmonitor.$state_ref.blocked" "$( [ "$blocked" = true ] && echo 1 || echo 0 )" || return 1
    verify_uci_value "wrtmonitor.$state_ref.schedule_enabled" "$( [ "$schedule_enabled" = true ] && echo 1 || echo 0 )" || return 1
    verify_uci_value "wrtmonitor.$state_ref.weekdays" "$weekdays" || return 1
    verify_uci_value "wrtmonitor.$state_ref.start" "$start" || return 1
    verify_uci_value "wrtmonitor.$state_ref.stop" "$stop" || return 1
    verify_uci_value "wrtmonitor.$state_ref.priority" "$priority" || return 1
    verify_uci_value "wrtmonitor.$state_ref.download_kbps" "$download" || return 1
    verify_uci_value "wrtmonitor.$state_ref.upload_kbps" "$upload" || return 1
    verify_uci_value "wrtmonitor.$state_ref.dns_provider" "$dns" || return 1

    if [ "$blocked" = true ]; then
        verify_uci_value "firewall.$policy_ref.src_mac" "$mac" \
            && verify_uci_value "firewall.$policy_ref.target" REJECT || return 1
        [ -z "$(uci -q get "firewall.$policy_after_ref" 2>/dev/null || true)" ] || return 1
        [ -z "$(uci -q get "firewall.$policy_days_ref" 2>/dev/null || true)" ] || return 1
    elif [ "$schedule_enabled" = true ]; then
        blocked_days="$(client_policy_complement_weekdays "$weekdays")"
        if client_policy_time_before "$start" "$stop"; then
            if [ "$start" = "00:00" ]; then
                [ -z "$(uci -q get "firewall.$policy_ref" 2>/dev/null || true)" ] || return 1
            else
                verify_uci_value "firewall.$policy_ref.weekdays" "$weekdays" \
                    && verify_uci_value "firewall.$policy_ref.start_time" "00:00" \
                    && verify_uci_value "firewall.$policy_ref.stop_time" "$start" || return 1
            fi
            if [ "$stop" = "23:59" ]; then
                [ -z "$(uci -q get "firewall.$policy_after_ref" 2>/dev/null || true)" ] || return 1
            else
                verify_uci_value "firewall.$policy_after_ref.weekdays" "$weekdays" \
                    && verify_uci_value "firewall.$policy_after_ref.start_time" "$stop" \
                    && verify_uci_value "firewall.$policy_after_ref.stop_time" "23:59" || return 1
            fi
        else
            verify_uci_value "firewall.$policy_ref.weekdays" "$weekdays" \
                && verify_uci_value "firewall.$policy_ref.start_time" "$stop" \
                && verify_uci_value "firewall.$policy_ref.stop_time" "$start" || return 1
            [ -z "$(uci -q get "firewall.$policy_after_ref" 2>/dev/null || true)" ] || return 1
        fi
        if [ -n "$blocked_days" ]; then
            verify_uci_value "firewall.$policy_days_ref.weekdays" "$blocked_days" \
                && verify_uci_value "firewall.$policy_days_ref.target" REJECT || return 1
        else
            [ -z "$(uci -q get "firewall.$policy_days_ref" 2>/dev/null || true)" ] || return 1
        fi
    else
        [ -z "$(uci -q get "firewall.$policy_ref" 2>/dev/null || true)" ] || return 1
        [ -z "$(uci -q get "firewall.$policy_after_ref" 2>/dev/null || true)" ] || return 1
        [ -z "$(uci -q get "firewall.$policy_days_ref" 2>/dev/null || true)" ] || return 1
    fi
    if [ "$priority" = normal ]; then
        [ -z "$(uci -q get "firewall.$qos_ref" 2>/dev/null || true)" ] || return 1
    else
        case "$priority" in low) mark=0x10 ;; high) mark=0x30 ;; realtime) mark=0x40 ;; *) return 1 ;; esac
        verify_uci_value "firewall.$qos_ref.src_mac" "$mac" \
            && verify_uci_value "firewall.$qos_ref.set_mark" "$mark" || return 1
    fi
    if [ "$dns" = none ]; then
        [ -z "$(uci -q get "firewall.$dns_ref" 2>/dev/null || true)" ] \
            && [ -z "$(uci -q get "firewall.$dot_ref" 2>/dev/null || true)" ] || return 1
    else
        case "$dns" in cloudflare-security) expected_dns=1.1.1.2 ;; cloudflare-family) expected_dns=1.1.1.3 ;; *) return 1 ;; esac
        verify_uci_value "firewall.$dns_ref.dest_ip" "$expected_dns" \
            && verify_uci_value "firewall.$dot_ref.dest_port" 853 || return 1
    fi
    device="$(uci -q get "wrtmonitor.$state_ref.shaping_device" 2>/dev/null || true)"
    pref="$(uci -q get "wrtmonitor.$state_ref.shaping_pref" 2>/dev/null || true)"
    if [ "$upload" -gt 0 ]; then client_policy_filter_matches "$device" ingress "$pref" "$mac" "$upload" || return 1; fi
    if [ "$download" -gt 0 ]; then client_policy_filter_matches "$device" egress "$pref" "$mac" "$download" || return 1; fi
}
