network_devices_json() {
    root="${WRTMONITOR_SYSTEM_ROOT:-}"
    items=""
    for path in "$root"/sys/class/net/*; do
        [ -e "$path" ] || continue
        name="$(basename "$path")"
        read_value() { cat "$path/$1" 2>/dev/null || true; }
        carrier="$(read_value carrier)"
        mtu="$(read_value mtu)"
        mac="$(read_value address)"
        operstate="$(read_value operstate)"
        speed="$(read_value speed)"
        duplex="$(read_value duplex)"
        [ "$speed" = "-1" ] && speed=""
        if [ -z "$speed" ] && command -v ethtool >/dev/null 2>&1; then
            speed="$(ethtool "$name" 2>/dev/null | sed -n 's/^[[:space:]]*Speed:[[:space:]]*\([0-9][0-9]*\)Mb\/s.*/\1/p' | head -n 1)"
            duplex="$(ethtool "$name" 2>/dev/null | sed -n 's/^[[:space:]]*Duplex:[[:space:]]*//p' | tr '[:upper:]' '[:lower:]' | head -n 1)"
        fi
        rx_bytes="$(read_value statistics/rx_bytes)"; tx_bytes="$(read_value statistics/tx_bytes)"
        rx_packets="$(read_value statistics/rx_packets)"; tx_packets="$(read_value statistics/tx_packets)"
        rx_errors="$(read_value statistics/rx_errors)"; tx_errors="$(read_value statistics/tx_errors)"
        rx_dropped="$(read_value statistics/rx_dropped)"; tx_dropped="$(read_value statistics/tx_dropped)"
        case "$mtu" in ''|*[!0-9]*) mtu=null ;; esac
        case "$speed" in ''|*[!0-9]*) speed=null ;; esac
        case "$rx_bytes" in ''|*[!0-9]*) rx_bytes=null ;; esac
        case "$tx_bytes" in ''|*[!0-9]*) tx_bytes=null ;; esac
        case "$rx_packets" in ''|*[!0-9]*) rx_packets=null ;; esac
        case "$tx_packets" in ''|*[!0-9]*) tx_packets=null ;; esac
        case "$rx_errors" in ''|*[!0-9]*) rx_errors=null ;; esac
        case "$tx_errors" in ''|*[!0-9]*) tx_errors=null ;; esac
        case "$rx_dropped" in ''|*[!0-9]*) rx_dropped=null ;; esac
        case "$tx_dropped" in ''|*[!0-9]*) tx_dropped=null ;; esac
        [ -n "$items" ] && items="$items,"
        items="$items\"$(json_escape "$name")\":{\"carrier\":$( [ "$carrier" = 1 ] && printf true || printf false ),\"operstate\":\"$(json_escape "$operstate")\",\"mtu\":$mtu,\"macaddr\":\"$(json_escape "$mac")\",\"speed_mbps\":$speed,\"duplex\":\"$(json_escape "$duplex")\",\"rx_bytes\":$rx_bytes,\"tx_bytes\":$tx_bytes,\"rx_packets\":$rx_packets,\"tx_packets\":$tx_packets,\"rx_errors\":$rx_errors,\"tx_errors\":$tx_errors,\"rx_dropped\":$rx_dropped,\"tx_dropped\":$tx_dropped}"
    done
    printf '{%s}' "$items"
}

network_summary_json() {
    tmp="/tmp/wrtmonitor-network-$$.json"
    if ! ubus call network.interface dump >"$tmp" 2>/dev/null; then
        rm -f "$tmp"
        printf '{"interfaces":[]}'
        return
    fi
    if ! require_json_tool; then
        rm -f "$tmp"
        printf '{"interfaces":[]}'
        return
    fi
    index=0
    items=""
    while true; do
        name="$(json_get_string "$tmp" "@.interface[$index].interface")"
        [ -n "$name" ] || break
        up="$(json_get_bool "$tmp" "@.interface[$index].up")"
        proto="$(json_get_string "$tmp" "@.interface[$index].proto")"
        device_name="$(json_get_string "$tmp" "@.interface[$index].l3_device")"
        gateway="$(jsonfilter -i "$tmp" -e "@.interface[$index].route[@.target='0.0.0.0'].nexthop" 2>/dev/null | head -n 1)"
        ip4="$(jsonfilter -i "$tmp" -e "@.interface[$index]['ipv4-address'][*].address" 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
        ip6="$(jsonfilter -i "$tmp" -e "@.interface[$index]['ipv6-address'][*].address" 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
        dns="$(jsonfilter -i "$tmp" -e "@.interface[$index]['dns-server'][*]" 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
        ipv4_json=""
        ipv4_details_json=""
        ipv6_json=""
        dns_json=""
        old_ifs="$IFS"
        IFS=','
        for value in $ip4; do
            [ -n "$value" ] || continue
            [ -n "$ipv4_json" ] && ipv4_json="$ipv4_json,"
            ipv4_json="$ipv4_json\"$(json_escape "$value")\""
        done
        address_index=0
        while true; do
            address="$(json_get_string "$tmp" "@.interface[$index]['ipv4-address'][$address_index].address")"
            [ -n "$address" ] || break
            prefix_length="$(json_get_number "$tmp" "@.interface[$index]['ipv4-address'][$address_index].mask")"
            case "$prefix_length" in ""|*[!0-9]*) prefix_length="" ;; esac
            [ -n "$ipv4_details_json" ] && ipv4_details_json="$ipv4_details_json,"
            ipv4_details_json="$ipv4_details_json{\"address\":\"$(json_escape "$address")\",\"prefix_length\":${prefix_length:-null}}"
            address_index=$((address_index + 1))
        done
        for value in $ip6; do
            [ -n "$value" ] || continue
            [ -n "$ipv6_json" ] && ipv6_json="$ipv6_json,"
            ipv6_json="$ipv6_json\"$(json_escape "$value")\""
        done
        for value in $dns; do
            [ -n "$value" ] || continue
            [ -n "$dns_json" ] && dns_json="$dns_json,"
            dns_json="$dns_json\"$(json_escape "$value")\""
        done
        IFS="$old_ifs"
        [ -n "$items" ] && items="$items,"
        configured_netmask="$(uci -q get "network.$name.netmask" 2>/dev/null || true)"
        configured_ip6assign="$(uci -q get "network.$name.ip6assign" 2>/dev/null || true)"
        configured_ip6hint="$(uci -q get "network.$name.ip6hint" 2>/dev/null || true)"
        items="$items{\"interface\":\"$(json_escape "$name")\",\"up\":$( [ "$up" = "true" ] && printf true || printf false ),\"proto\":\"$(json_escape "$proto")\",\"device\":\"$(json_escape "$device_name")\",\"ipv4\":[${ipv4_json}],\"ipv4_details\":[${ipv4_details_json}],\"netmask\":\"$(json_escape "$configured_netmask")\",\"ipv6\":[${ipv6_json}],\"ip6assign\":\"$(json_escape "$configured_ip6assign")\",\"ip6hint\":\"$(json_escape "$configured_ip6hint")\",\"gateway\":\"$(json_escape "$gateway")\",\"dns\":[${dns_json}],\"errors\":[]}"
        index=$((index + 1))
    done
    rm -f "$tmp"
    printf '{"interfaces":[%s],"topology":%s,"dns_privacy":%s}' "$items" "$(network_topology_json)" "$(dns_privacy_json)"
}
