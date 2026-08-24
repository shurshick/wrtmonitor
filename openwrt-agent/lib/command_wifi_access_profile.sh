# shellcheck disable=SC2034,SC2154
handle_wifi_access_profile_command() {
    payload_file="/tmp/wrtmonitor-command-payload"
    printf '%s' "$command_payload" >"$payload_file"
    profile_iface="$(json_get_string "$payload_file" '@.iface')"
    profile_enabled="$(json_get_bool "$payload_file" '@.enabled')"
    profile_id="$(json_get_string "$payload_file" '@.profile_id')"
    profile_name="$(json_get_string "$payload_file" '@.profile_name')"
    profile_blocked="$(json_get_bool "$payload_file" '@.blocked')"
    profile_schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
    profile_weekdays="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
    profile_start="$(json_get_string "$payload_file" '@.schedule.start')"
    profile_stop="$(json_get_string "$payload_file" '@.schedule.stop')"
    profile_download="$(json_get_number "$payload_file" '@.qos.download_kbps')"
    profile_upload="$(json_get_number "$payload_file" '@.qos.upload_kbps')"
    rm -f "$payload_file"
    [ -n "$profile_download" ] || profile_download=0
    [ -n "$profile_upload" ] || profile_upload=0

    if ! uci -q get "wireless.$profile_iface" >/dev/null 2>&1 \
        || [ "$(uci -q get "wireless.$profile_iface.mode" 2>/dev/null || true)" != ap ]; then
        status="failed"
        result="$(command_failed_result "wifi access point interface not found")"
    elif [ "$profile_enabled" != true ]; then
        if wifi_access_profile_clear "$profile_iface"; then
            result="$(command_success_result "Wi-Fi access profile removed" "\"iface\":\"$(json_escape "$profile_iface")\"")"
        else
            status="failed"
            result="$(command_failed_result "failed to remove Wi-Fi access profile")"
        fi
    else
        profile_section="$(wifi_access_profile_section "$profile_iface")"
        if uci -q get "wrtmonitor.$profile_section" >/dev/null 2>&1; then
            profile_base_enabled="$(uci -q get "wrtmonitor.$profile_section.base_enabled" 2>/dev/null || echo 1)"
        else
            profile_base_enabled=1
            [ "$(uci -q get "wireless.$profile_iface.disabled" 2>/dev/null || echo 0)" = 1 ] && profile_base_enabled=0
        fi
        uci set "wrtmonitor.$profile_section=wifi_access_profile"
        uci set "wrtmonitor.$profile_section.iface=$profile_iface"
        uci set "wrtmonitor.$profile_section.profile_id=$profile_id"
        uci set "wrtmonitor.$profile_section.profile_name=$profile_name"
        uci set "wrtmonitor.$profile_section.base_enabled=$profile_base_enabled"
        uci set "wrtmonitor.$profile_section.blocked=$( [ "$profile_blocked" = true ] && echo 1 || echo 0 )"
        uci set "wrtmonitor.$profile_section.schedule_enabled=$( [ "$profile_schedule_enabled" = true ] && echo 1 || echo 0 )"
        uci set "wrtmonitor.$profile_section.weekdays=$profile_weekdays"
        uci set "wrtmonitor.$profile_section.start=$profile_start"
        uci set "wrtmonitor.$profile_section.stop=$profile_stop"
        uci set "wrtmonitor.$profile_section.download_kbps=$profile_download"
        uci set "wrtmonitor.$profile_section.upload_kbps=$profile_upload"
        uci set "wrtmonitor.$profile_section.shaping_pref=$(wifi_access_profile_pref "$profile_section")"
        if uci commit wrtmonitor && apply_wifi_access_profile "$profile_section"; then
            result="$(command_success_result "Wi-Fi access profile applied" "\"iface\":\"$(json_escape "$profile_iface")\",\"profile_id\":\"$(json_escape "$profile_id")\"")"
        else
            status="failed"
            result="$(command_failed_result "failed to apply Wi-Fi access profile")"
        fi
    fi
}
