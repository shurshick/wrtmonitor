wifi_access_profile_section() {
    printf 'wifi_access_%s' "$(printf '%s' "$1" | sed 's/[^A-Za-z0-9_]/_/g' | cut -c1-48)"
}

wifi_access_profile_pref() {
    checksum="$(printf '%s' "$1" | sha256sum | cut -d' ' -f1 | tr 'abcdef' '123456' | cut -c1-8)"
    printf '%s' $((40000 + checksum % 9999))
}

wifi_access_profile_direction_pref() {
    base_pref="$1"
    direction="$2"
    if [ "$direction" = egress ]; then
        printf '%s' $((base_pref + 1))
    else
        printf '%s' "$base_pref"
    fi
}
wifi_access_profile_delete_filter() {
    device="$1"
    direction="$2"
    pref="$3"
    [ -n "$device" ] || return 0
    command -v tc >/dev/null 2>&1 || return 0
    tc filter del dev "$device" "$direction" pref "$pref" >/dev/null 2>&1 || true
}

wifi_access_profile_filter_matches() {
    device="$1"
    direction="$2"
    pref="$3"
    expected_kbps="$4"
    case "$expected_kbps" in ""|*[!0-9]*) return 1 ;; esac
    details="$(tc -d filter show dev "$device" "$direction" 2>/dev/null)" || return 1
    rate="$(printf '%s\n' "$details" | awk -v expected_pref="$pref" '
        $0 ~ ("pref " expected_pref " ") { selected = 1 }
        $0 ~ /filter protocol .* pref [0-9]+ / && $0 !~ ("pref " expected_pref " ") { selected = 0 }
        selected && /police/ {
            for (i = 1; i <= NF; i++) if ($i == "rate") { print $(i + 1); exit }
        }
    ')"
    case "$rate" in
        *Kbit) actual_kbps="${rate%Kbit}" ;;
        *Mbit) actual_kbps=$(( ${rate%Mbit} * 1000 )) ;;
        *Gbit) actual_kbps=$(( ${rate%Gbit} * 1000000 )) ;;
        *) return 1 ;;
    esac
    [ "$actual_kbps" -eq "$expected_kbps" ]
}

wifi_access_profile_filter_absent() {
    device="$1"
    direction="$2"
    pref="$3"
    [ -n "$device" ] || return 0
    ! tc filter show dev "$device" "$direction" 2>/dev/null \
        | grep -Eq "(^|[[:space:]])pref[[:space:]]+$pref([[:space:]]|$)"
}

wifi_access_profile_runtime_ifname() {
    iface="$1"
    radio="$(uci -q get "wireless.$iface.device" 2>/dev/null || true)"
    [ -n "$radio" ] || return 1
    runtime_file="/tmp/wrtmonitor-wifi-profile-runtime-$$"
    wifi status "$radio" >"$runtime_file" 2>/dev/null || true
    runtime_index=0
    fallback_ifname=""
    while [ "$runtime_index" -lt 32 ]; do
        runtime_section="$(jsonfilter -i "$runtime_file" -e "@.$radio.interfaces[$runtime_index].section" 2>/dev/null || true)"
        runtime_name="$(jsonfilter -i "$runtime_file" -e "@.$radio.interfaces[$runtime_index].ifname" 2>/dev/null || true)"
        [ -n "$runtime_section$runtime_name" ] || break
        [ -n "$fallback_ifname" ] || fallback_ifname="$runtime_name"
        if [ "$runtime_section" = "$iface" ]; then
            rm -f "$runtime_file"
            printf '%s' "$runtime_name"
            return 0
        fi
        runtime_index=$((runtime_index + 1))
    done
    rm -f "$runtime_file"

    target_ssid="$(uci -q get "wireless.$iface.ssid" 2>/dev/null || true)"
    if [ -n "$target_ssid" ] && command -v ubus >/dev/null 2>&1 && command -v iwinfo >/dev/null 2>&1; then
        for hostapd_object in $(ubus list 'hostapd.*' 2>/dev/null || true); do
            candidate_ifname="${hostapd_object#hostapd.}"
            candidate_ssid="$(iwinfo "$candidate_ifname" info 2>/dev/null | sed -n 's/.*ESSID: "\(.*\)".*/\1/p' | head -n 1)"
            if [ "$candidate_ssid" = "$target_ssid" ]; then
                printf '%s' "$candidate_ifname"
                return 0
            fi
        done
    fi
    [ -n "$fallback_ifname" ] && printf '%s' "$fallback_ifname"
}

wifi_access_profile_active_now() {
    section="$1"
    blocked="$(uci -q get "wrtmonitor.$section.blocked" 2>/dev/null || echo 0)"
    [ "$blocked" != 1 ] || return 1
    schedule_enabled="$(uci -q get "wrtmonitor.$section.schedule_enabled" 2>/dev/null || echo 0)"
    [ "$schedule_enabled" = 1 ] || return 0
    weekdays="$(uci -q get "wrtmonitor.$section.weekdays" 2>/dev/null || true)"
    start="$(uci -q get "wrtmonitor.$section.start" 2>/dev/null || true)"
    stop="$(uci -q get "wrtmonitor.$section.stop" 2>/dev/null || true)"
    [ -n "$start" ] && [ -n "$stop" ] && wifi_schedule_active_now "$weekdays" "$start" "$stop"
}

wifi_access_profile_apply_limits() {
    section="$1"
    ifname="$2"
    download="$(uci -q get "wrtmonitor.$section.download_kbps" 2>/dev/null || echo 0)"
    upload="$(uci -q get "wrtmonitor.$section.upload_kbps" 2>/dev/null || echo 0)"
    pref="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || wifi_access_profile_pref "$section")"
    upload_pref="$(wifi_access_profile_direction_pref "$pref" ingress)"
    download_pref="$(wifi_access_profile_direction_pref "$pref" egress)"
    previous_ifname="$(uci -q get "wrtmonitor.$section.runtime_ifname" 2>/dev/null || true)"
    if [ -n "$previous_ifname" ] && [ "$previous_ifname" != "$ifname" ]; then
        wifi_access_profile_delete_filter "$previous_ifname" ingress "$upload_pref"
        wifi_access_profile_delete_filter "$previous_ifname" egress "$download_pref"
    fi
    [ -n "$ifname" ] || return 0
    command -v tc >/dev/null 2>&1 || return 2
    ip link show dev "$ifname" >/dev/null 2>&1 || return 3
    if [ "$download" -le 0 ] 2>/dev/null && [ "$upload" -le 0 ] 2>/dev/null; then
        wifi_access_profile_delete_filter "$ifname" ingress "$upload_pref"
        wifi_access_profile_delete_filter "$ifname" egress "$download_pref"
        return 0
    fi
    tc qdisc show dev "$ifname" 2>/dev/null | grep -qw clsact \
        || tc qdisc add dev "$ifname" clsact >/dev/null 2>&1 \
        || return 4
    if [ "$upload" -gt 0 ]; then
        if ! wifi_access_profile_filter_matches "$ifname" ingress "$upload_pref" "$upload"; then
            wifi_access_profile_delete_filter "$ifname" ingress "$upload_pref"
            tc filter add dev "$ifname" ingress protocol all pref "$upload_pref" \
                u32 match u32 0 0 action police rate "${upload}kbit" burst 64k conform-exceed drop \
                >/dev/null 2>&1 || return 5
        fi
    else
        wifi_access_profile_delete_filter "$ifname" ingress "$upload_pref"
    fi
    if [ "$download" -gt 0 ]; then
        if ! wifi_access_profile_filter_matches "$ifname" egress "$download_pref" "$download"; then
            wifi_access_profile_delete_filter "$ifname" egress "$download_pref"
            tc filter add dev "$ifname" egress protocol all pref "$download_pref" \
                u32 match u32 0 0 action police rate "${download}kbit" burst 64k conform-exceed drop \
                >/dev/null 2>&1 || return 6
        fi
    else
        wifi_access_profile_delete_filter "$ifname" egress "$download_pref"
    fi
}

apply_wifi_access_profile() {
    section="$1"
    iface="$(uci -q get "wrtmonitor.$section.iface" 2>/dev/null || true)"
    [ -n "$iface" ] && uci -q get "wireless.$iface" >/dev/null 2>&1 || return 1
    base_enabled="$(uci -q get "wrtmonitor.$section.base_enabled" 2>/dev/null || echo 1)"
    desired_disabled=1
    if [ "$base_enabled" = 1 ] && wifi_access_profile_active_now "$section"; then
        desired_disabled=0
    fi
    current_disabled="$(uci -q get "wireless.$iface.disabled" 2>/dev/null || echo 0)"
    if [ "$current_disabled" != "$desired_disabled" ]; then
        uci set "wireless.$iface.disabled=$desired_disabled" || return 1
        uci commit wireless || return 1
        wifi reload >/dev/null 2>&1 || return 1
    fi
    ifname=""
    if [ "$desired_disabled" = 0 ]; then
        wait_count=0
        while [ "$wait_count" -lt 8 ]; do
            ifname="$(wifi_access_profile_runtime_ifname "$iface" || true)"
            [ -n "$ifname" ] && break
            wait_count=$((wait_count + 1))
            sleep 1
        done
    fi
    wifi_access_profile_apply_limits "$section" "$ifname" || return 1
    effective_enabled="$( [ "$desired_disabled" = 0 ] && echo 1 || echo 0 )"
    runtime_changed=0
    if [ "$(uci -q get "wrtmonitor.$section.runtime_ifname" 2>/dev/null || true)" != "$ifname" ]; then
        uci set "wrtmonitor.$section.runtime_ifname=$ifname"
        runtime_changed=1
    fi
    if [ "$(uci -q get "wrtmonitor.$section.effective_enabled" 2>/dev/null || true)" != "$effective_enabled" ]; then
        uci set "wrtmonitor.$section.effective_enabled=$effective_enabled"
        runtime_changed=1
    fi
    [ "$runtime_changed" = 0 ] || uci commit wrtmonitor
}

apply_wifi_access_profiles() {
    sections="$(uci -q show wrtmonitor 2>/dev/null | sed -n 's/^wrtmonitor\.\([^.=]*\)=wifi_access_profile$/\1/p')"
    result=0
    for section in $sections; do
        apply_wifi_access_profile "$section" || result=1
    done
    return "$result"
}

wifi_access_profile_clear() {
    iface="$1"
    section="$(wifi_access_profile_section "$iface")"
    previous_ifname="$(uci -q get "wrtmonitor.$section.runtime_ifname" 2>/dev/null || true)"
    pref="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || wifi_access_profile_pref "$section")"
    upload_pref="$(wifi_access_profile_direction_pref "$pref" ingress)"
    download_pref="$(wifi_access_profile_direction_pref "$pref" egress)"
    base_enabled="$(uci -q get "wrtmonitor.$section.base_enabled" 2>/dev/null || echo 1)"
    wifi_access_profile_delete_filter "$previous_ifname" ingress "$upload_pref"
    wifi_access_profile_delete_filter "$previous_ifname" egress "$download_pref"
    uci -q delete "wrtmonitor.$section" || true
    uci commit wrtmonitor || return 1
    if uci -q get "wireless.$iface" >/dev/null 2>&1; then
        desired_disabled="$( [ "$base_enabled" = 1 ] && echo 0 || echo 1 )"
        current_disabled="$(uci -q get "wireless.$iface.disabled" 2>/dev/null || echo 0)"
        if [ "$current_disabled" != "$desired_disabled" ]; then
            uci set "wireless.$iface.disabled=$desired_disabled" && uci commit wireless && wifi reload >/dev/null 2>&1
        fi
    fi
}

verify_wifi_access_profile_postcondition() {
    payload_file="$1"
    iface="$(json_get_string "$payload_file" '@.iface')"
    enabled="$(json_get_bool "$payload_file" '@.enabled')"
    section="$(wifi_access_profile_section "$iface")"
    if [ "$enabled" != true ]; then
        ! uci -q get "wrtmonitor.$section" >/dev/null 2>&1
        return
    fi

    expected_profile_id="$(json_get_string "$payload_file" '@.profile_id')"
    expected_download="$(json_get_number "$payload_file" '@.qos.download_kbps')"
    expected_upload="$(json_get_number "$payload_file" '@.qos.upload_kbps')"
    [ -n "$expected_download" ] || expected_download=0
    [ -n "$expected_upload" ] || expected_upload=0
    verify_uci_value "wrtmonitor.$section.iface" "$iface" \
        && verify_uci_value "wrtmonitor.$section.profile_id" "$expected_profile_id" \
        && verify_uci_value "wrtmonitor.$section.download_kbps" "$expected_download" \
        && verify_uci_value "wrtmonitor.$section.upload_kbps" "$expected_upload" \
        || return 1

    effective_enabled="$(uci -q get "wrtmonitor.$section.effective_enabled" 2>/dev/null || echo 0)"
    [ "$effective_enabled" = 1 ] || return 0
    runtime_ifname="$(uci -q get "wrtmonitor.$section.runtime_ifname" 2>/dev/null || true)"
    pref="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || wifi_access_profile_pref "$section")"
    upload_pref="$(wifi_access_profile_direction_pref "$pref" ingress)"
    download_pref="$(wifi_access_profile_direction_pref "$pref" egress)"
    if [ "$expected_download" -gt 0 ] 2>/dev/null; then
        wifi_access_profile_filter_matches "$runtime_ifname" egress "$download_pref" "$expected_download" || return 1
    else
        wifi_access_profile_filter_absent "$runtime_ifname" egress "$download_pref" || return 1
    fi
    if [ "$expected_upload" -gt 0 ] 2>/dev/null; then
        wifi_access_profile_filter_matches "$runtime_ifname" ingress "$upload_pref" "$expected_upload"
    else
        wifi_access_profile_filter_absent "$runtime_ifname" ingress "$upload_pref"
    fi
}

wifi_access_profile_json() {
    iface="$1"
    section="$(wifi_access_profile_section "$iface")"
    if ! uci -q get "wrtmonitor.$section" >/dev/null 2>&1; then
        printf '{"configured":false,"profile_id":"","profile_name":"","effective_enabled":true,"qos":{"download_kbps":0,"upload_kbps":0,"download_active":false,"upload_active":false},"schedule":{"enabled":false,"weekdays":[],"start":"","stop":"","active_now":true}}'
        return 0
    fi
    profile_id="$(uci -q get "wrtmonitor.$section.profile_id" 2>/dev/null || true)"
    profile_name="$(uci -q get "wrtmonitor.$section.profile_name" 2>/dev/null || true)"
    blocked="$(uci -q get "wrtmonitor.$section.blocked" 2>/dev/null || echo 0)"
    schedule_enabled="$(uci -q get "wrtmonitor.$section.schedule_enabled" 2>/dev/null || echo 0)"
    weekdays="$(uci -q get "wrtmonitor.$section.weekdays" 2>/dev/null || true)"
    start="$(uci -q get "wrtmonitor.$section.start" 2>/dev/null || true)"
    stop="$(uci -q get "wrtmonitor.$section.stop" 2>/dev/null || true)"
    download="$(uci -q get "wrtmonitor.$section.download_kbps" 2>/dev/null || echo 0)"
    upload="$(uci -q get "wrtmonitor.$section.upload_kbps" 2>/dev/null || echo 0)"
    ifname="$(uci -q get "wrtmonitor.$section.runtime_ifname" 2>/dev/null || true)"
    pref="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || wifi_access_profile_pref "$section")"
    upload_pref="$(wifi_access_profile_direction_pref "$pref" ingress)"
    download_pref="$(wifi_access_profile_direction_pref "$pref" egress)"
    effective_enabled="$(uci -q get "wrtmonitor.$section.effective_enabled" 2>/dev/null || echo 1)"
    active_now=false; wifi_access_profile_active_now "$section" && active_now=true
    download_active=false; upload_active=false
    if [ "$download" -gt 0 ] 2>/dev/null && wifi_access_profile_filter_matches "$ifname" egress "$download_pref" "$download"; then
        download_active=true
    fi
    if [ "$upload" -gt 0 ] 2>/dev/null && wifi_access_profile_filter_matches "$ifname" ingress "$upload_pref" "$upload"; then
        upload_active=true
    fi
    weekdays_json=""
    for day in $weekdays; do
        [ -n "$weekdays_json" ] && weekdays_json="$weekdays_json,"
        weekdays_json="$weekdays_json\"$(json_escape "$day")\""
    done
    printf '{"configured":true,"profile_id":"%s","profile_name":"%s","blocked":%s,"effective_enabled":%s,"qos":{"download_kbps":%s,"upload_kbps":%s,"download_active":%s,"upload_active":%s,"interface":"%s"},"schedule":{"enabled":%s,"weekdays":[%s],"start":"%s","stop":"%s","active_now":%s}}' \
        "$(json_escape "$profile_id")" "$(json_escape "$profile_name")" "$( [ "$blocked" = 1 ] && printf true || printf false )" \
        "$( [ "$effective_enabled" = 1 ] && printf true || printf false )" "$download" "$upload" "$download_active" "$upload_active" "$(json_escape "$ifname")" \
        "$( [ "$schedule_enabled" = 1 ] && printf true || printf false )" "$weekdays_json" "$(json_escape "$start")" "$(json_escape "$stop")" "$active_now"
}
