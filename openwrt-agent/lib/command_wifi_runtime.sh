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

wifi_security_key_valid() {
    iface="$1"
    encryption="$2"
    supplied_key="$3"
    [ "$encryption" = none ] && return 0
    effective_key="$supplied_key"
    [ -n "$effective_key" ] || effective_key="$(uci -q get "wireless.$iface.key" 2>/dev/null || true)"
    [ "${#effective_key}" -ge 8 ] && [ "${#effective_key}" -le 63 ]
}

wifi_iface_runtime_active() {
    iface="$1"
    radio="$(uci -q get "wireless.$iface.device" 2>/dev/null || true)"
    [ -n "$radio" ] || return 1
    attempt=0
    while [ "$attempt" -lt 10 ]; do
        runtime="$(wifi status "$radio" 2>/dev/null | tr -d '[:space:]' || true)"
        if printf '%s' "$runtime" | grep -Fq '"up":true' \
            && printf '%s' "$runtime" | grep -Fq "\"section\":\"$iface\""; then
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    return 1
}
