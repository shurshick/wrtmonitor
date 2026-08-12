client_policy_suffix() {
    printf '%s' "$1" | tr -d ':' | tr 'A-F' 'a-f'
}

client_policy_section() {
    printf 'wrtmonitor_client_%s' "$(client_policy_suffix "$1")"
}

client_policy_filter_pref() {
    mac="$(printf '%s' "$1" | tr 'A-F' 'a-f')"
    section="$(client_policy_section "$mac")"
    existing="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || true)"
    case "$existing" in ""|*[!0-9]*) ;; *) printf '%s' "$existing"; return 0 ;; esac
    suffix="$(client_policy_suffix "$1")"
    tail="$(printf '%s' "$suffix" | sed 's/.*\(....\)$/\1/')"
    value="$((0x${tail:-0}))"
    candidate=$((31000 + value % 30000))
    attempts=0
    while [ "$attempts" -lt 30000 ]; do
        conflict=0
        sections="$(uci -q show wrtmonitor 2>/dev/null | sed -n "s/^wrtmonitor\.\([^.=]*\)=client_policy$/\1/p")"
        for other in $sections; do
            other_mac="$(uci -q get "wrtmonitor.$other.mac" 2>/dev/null || true)"
            other_pref="$(uci -q get "wrtmonitor.$other.shaping_pref" 2>/dev/null || true)"
            if [ "$other_mac" != "$mac" ] && [ "$other_pref" = "$candidate" ]; then conflict=1; break; fi
        done
        if [ "$conflict" = 0 ]; then
            device="$(client_policy_lan_device)"
            client_policy_filter_present "$device" ingress "$candidate" && conflict=1
            client_policy_filter_present "$device" egress "$candidate" && conflict=1
        fi
        if [ "$conflict" = 0 ]; then printf '%s' "$candidate"; return 0; fi
        candidate=$((candidate + 1))
        [ "$candidate" -le 60999 ] || candidate=31000
        attempts=$((attempts + 1))
    done
    return 1
}

client_policy_lan_device() {
    device="$(uci -q get network.lan.device 2>/dev/null || true)"
    [ -n "$device" ] || device="$(uci -q get network.lan.ifname 2>/dev/null | awk '{print $1}')"
    [ -n "$device" ] || device=br-lan
    printf '%s' "$device"
}

client_policy_delete_filter() {
    device="$1"
    direction="$2"
    pref="$3"
    command -v tc >/dev/null 2>&1 || return 0
    tc filter del dev "$device" "$direction" pref "$pref" >/dev/null 2>&1 || true
}

client_policy_filter_present() {
    device="$1"
    direction="$2"
    pref="$3"
    command -v tc >/dev/null 2>&1 || return 1
    tc filter show dev "$device" "$direction" 2>/dev/null \
        | grep -Eq "(^|[[:space:]])pref[[:space:]]+$pref([[:space:]]|$)"
}

client_policy_filter_matches() {
    device="$1"
    direction="$2"
    pref="$3"
    mac="$(printf '%s' "$4" | tr 'A-F' 'a-f')"
    expected_kbps="$5"
    case "$expected_kbps" in ""|*[!0-9]*) return 1 ;; esac
    details="$(tc -d filter show dev "$device" "$direction" pref "$pref" 2>/dev/null)" || return 1
    printf '%s\n' "$details" | tr 'A-F' 'a-f' | grep -Fq "_mac $mac" || return 1
    rate="$(printf '%s\n' "$details" | awk '/police/ { for (i = 1; i <= NF; i++) if ($i == "rate") { print $(i + 1); exit } }')"
    case "$rate" in
        *Kbit) actual_kbps="${rate%Kbit}" ;;
        *Mbit) actual_kbps=$(( ${rate%Mbit} * 1000 )) ;;
        *Gbit) actual_kbps=$(( ${rate%Gbit} * 1000000 )) ;;
        *) return 1 ;;
    esac
    [ "$actual_kbps" -eq "$expected_kbps" ]
}

client_policy_apply_runtime_limits() {
    mac="$1"
    download_kbps="${2:-0}"
    upload_kbps="${3:-0}"
    device="${4:-$(client_policy_lan_device)}"
    pref="${5:-$(client_policy_filter_pref "$mac")}"
    case "$download_kbps" in ""|*[!0-9]*) download_kbps=0 ;; esac
    case "$upload_kbps" in ""|*[!0-9]*) upload_kbps=0 ;; esac

    client_policy_delete_filter "$device" ingress "$pref"
    client_policy_delete_filter "$device" egress "$pref"
    [ "$download_kbps" -gt 0 ] || [ "$upload_kbps" -gt 0 ] || return 0
    command -v tc >/dev/null 2>&1 || return 2
    ip link show dev "$device" >/dev/null 2>&1 || return 3
    tc qdisc show dev "$device" 2>/dev/null | grep -qw clsact \
        || tc qdisc add dev "$device" clsact >/dev/null 2>&1 \
        || return 4
    if [ "$upload_kbps" -gt 0 ]; then
        tc filter replace dev "$device" ingress protocol all pref "$pref" \
            flower src_mac "$mac" \
            action police rate "${upload_kbps}kbit" burst 64k conform-exceed drop \
            >/dev/null 2>&1 || return 5
    fi
    if [ "$download_kbps" -gt 0 ]; then
        tc filter replace dev "$device" egress protocol all pref "$pref" \
            flower dst_mac "$mac" \
            action police rate "${download_kbps}kbit" burst 64k conform-exceed drop \
            >/dev/null 2>&1 || return 6
    fi
}

client_policy_save_state() {
    mac="$1"
    section="$(client_policy_section "$mac")"
    blocked="$2"
    schedule_enabled="$3"
    weekdays="$4"
    start="$5"
    stop="$6"
    priority="$7"
    download_kbps="$8"
    upload_kbps="$9"
    shift 9
    dns_provider="$1"
    device="$2"
    pref="$3"
    uci set "wrtmonitor.$section=client_policy" \
        && uci set "wrtmonitor.$section.mac=$mac" \
        && uci set "wrtmonitor.$section.blocked=$( [ "$blocked" = true ] && echo 1 || echo 0 )" \
        && uci set "wrtmonitor.$section.schedule_enabled=$( [ "$schedule_enabled" = true ] && echo 1 || echo 0 )" \
        && uci set "wrtmonitor.$section.weekdays=$weekdays" \
        && uci set "wrtmonitor.$section.start=$start" \
        && uci set "wrtmonitor.$section.stop=$stop" \
        && uci set "wrtmonitor.$section.priority=$priority" \
        && uci set "wrtmonitor.$section.download_kbps=$download_kbps" \
        && uci set "wrtmonitor.$section.upload_kbps=$upload_kbps" \
        && uci set "wrtmonitor.$section.dns_provider=$dns_provider" \
        && uci set "wrtmonitor.$section.shaping_device=$device" \
        && uci set "wrtmonitor.$section.shaping_pref=$pref"
}

client_policy_observed_json() {
    mac="$1"
    section="$(client_policy_section "$mac")"
    blocked="$(uci -q get "wrtmonitor.$section.blocked" 2>/dev/null || echo 0)"
    schedule_enabled="$(uci -q get "wrtmonitor.$section.schedule_enabled" 2>/dev/null || echo 0)"
    weekdays="$(uci -q get "wrtmonitor.$section.weekdays" 2>/dev/null || true)"
    start="$(uci -q get "wrtmonitor.$section.start" 2>/dev/null || true)"
    stop="$(uci -q get "wrtmonitor.$section.stop" 2>/dev/null || true)"
    priority="$(uci -q get "wrtmonitor.$section.priority" 2>/dev/null || echo normal)"
    download="$(uci -q get "wrtmonitor.$section.download_kbps" 2>/dev/null || echo 0)"
    upload="$(uci -q get "wrtmonitor.$section.upload_kbps" 2>/dev/null || echo 0)"
    dns="$(uci -q get "wrtmonitor.$section.dns_provider" 2>/dev/null || echo none)"
    device="$(uci -q get "wrtmonitor.$section.shaping_device" 2>/dev/null || client_policy_lan_device)"
    pref="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || client_policy_filter_pref "$mac")"
    [ "$blocked" = 1 ] && blocked_json=true || blocked_json=false
    [ "$schedule_enabled" = 1 ] && schedule_json=true || schedule_json=false
    upload_active=false
    download_active=false
    if [ "$upload" -gt 0 ] 2>/dev/null \
        && client_policy_filter_matches "$device" ingress "$pref" "$mac" "$upload"; then
        upload_active=true
    fi
    if [ "$download" -gt 0 ] 2>/dev/null \
        && client_policy_filter_matches "$device" egress "$pref" "$mac" "$download"; then
        download_active=true
    fi
    weekdays_json=""
    for day in $weekdays; do
        [ -n "$weekdays_json" ] && weekdays_json="$weekdays_json,"
        weekdays_json="$weekdays_json\"$(json_escape "$day")\""
    done
    printf '{"mac":"%s","blocked":%s,"schedule":{"enabled":%s,"weekdays":[%s],"start":"%s","stop":"%s"},"qos":{"priority":"%s","download_kbps":%s,"upload_kbps":%s,"download_active":%s,"upload_active":%s,"device":"%s"},"dns":{"provider":"%s"}}' \
        "$(json_escape "$mac")" "$blocked_json" "$schedule_json" "$weekdays_json" \
        "$(json_escape "$start")" "$(json_escape "$stop")" "$(json_escape "$priority")" \
        "${download:-0}" "${upload:-0}" "$download_active" "$upload_active" \
        "$(json_escape "$device")" "$(json_escape "$dns")"
}

restore_client_policy_runtime() {
    command -v tc >/dev/null 2>&1 || return 0
    sections="$(uci -q show wrtmonitor 2>/dev/null | sed -n "s/^wrtmonitor\.\([^.=]*\)=client_policy$/\1/p")"
    restore_status=0
    for section in $sections; do
        mac="$(uci -q get "wrtmonitor.$section.mac" 2>/dev/null || true)"
        [ -n "$mac" ] || continue
        download="$(uci -q get "wrtmonitor.$section.download_kbps" 2>/dev/null || echo 0)"
        upload="$(uci -q get "wrtmonitor.$section.upload_kbps" 2>/dev/null || echo 0)"
        device="$(uci -q get "wrtmonitor.$section.shaping_device" 2>/dev/null || client_policy_lan_device)"
        pref="$(uci -q get "wrtmonitor.$section.shaping_pref" 2>/dev/null || client_policy_filter_pref "$mac")"
        client_policy_apply_runtime_limits "$mac" "$download" "$upload" "$device" "$pref" || restore_status=1
    done
    return "$restore_status"
}
