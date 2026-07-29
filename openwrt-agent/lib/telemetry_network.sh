dhcp_json() {
    leases=""
    static_leases=""
    pools=""
    lease_file="/tmp/dhcp.leases"
    if [ -r "$lease_file" ]; then
        while IFS=' ' read -r expires mac ip hostname client_id; do
            [ -n "$mac" ] || continue
            [ -n "$leases" ] && leases="$leases,"
            leases="$leases{\"expires\":\"$(json_escape "$expires")\",\"mac\":\"$(json_escape "$mac")\",\"ip\":\"$(json_escape "$ip")\",\"hostname\":\"$(json_escape "$hostname")\",\"client_id\":\"$(json_escape "$client_id")\"}"
        done <"$lease_file"
    fi
    host_index=0
    while uci -q get "dhcp.@host[$host_index]" >/dev/null 2>&1; do
        static_name="$(uci -q get "dhcp.@host[$host_index].name" 2>/dev/null || true)"
        static_mac="$(uci -q get "dhcp.@host[$host_index].mac" 2>/dev/null || true)"
        static_ip="$(uci -q get "dhcp.@host[$host_index].ip" 2>/dev/null || true)"
        if [ -n "$static_mac" ]; then
            [ -n "$static_leases" ] && static_leases="$static_leases,"
            static_leases="$static_leases{\"mac\":\"$(json_escape "$static_mac")\",\"ip\":\"$(json_escape "$static_ip")\",\"hostname\":\"$(json_escape "$static_name")\"}"
        fi
        host_index=$((host_index + 1))
    done
    for pool_name in $(uci -q show dhcp 2>/dev/null | sed -n 's/^dhcp\.\([^.=]*\)=dhcp$/\1/p'); do
        pool_start="$(uci -q get "dhcp.$pool_name.start" 2>/dev/null || true)"
        pool_limit="$(uci -q get "dhcp.$pool_name.limit" 2>/dev/null || true)"
        pool_leasetime="$(uci -q get "dhcp.$pool_name.leasetime" 2>/dev/null || true)"
        [ -n "$pool_start$pool_limit$pool_leasetime" ] || continue
        case "$pool_start" in ""|*[!0-9]*) pool_start=0 ;; esac
        case "$pool_limit" in ""|*[!0-9]*) pool_limit=0 ;; esac
        [ -n "$pools" ] && pools="$pools,"
        pool_ignore="$(uci -q get "dhcp.$pool_name.ignore" 2>/dev/null || echo 0)"
        pool_ra="$(uci -q get "dhcp.$pool_name.ra" 2>/dev/null || true)"
        pool_dhcpv6="$(uci -q get "dhcp.$pool_name.dhcpv6" 2>/dev/null || true)"
        pool_ndp="$(uci -q get "dhcp.$pool_name.ndp" 2>/dev/null || true)"
        pool_ra_management="$(uci -q get "dhcp.$pool_name.ra_management" 2>/dev/null || true)"
        pools="$pools{\"interface\":\"$(json_escape "$pool_name")\",\"start\":$pool_start,\"limit\":$pool_limit,\"leasetime\":\"$(json_escape "$pool_leasetime")\",\"enabled\":$( [ "$pool_ignore" = 1 ] && printf false || printf true ),\"ra\":\"$(json_escape "$pool_ra")\",\"dhcpv6\":\"$(json_escape "$pool_dhcpv6")\",\"ndp\":\"$(json_escape "$pool_ndp")\",\"ra_management\":\"$(json_escape "$pool_ra_management")\"}"
    done
    printf '{"leases":[%s],"static_leases":[%s],"pools":[%s]}' "$leases" "$static_leases" "$pools"
}

clients_json() {
    neighbours=""
    traffic_available=false
    traffic_status="$(nlbwmon_runtime_status)"
    traffic_records=0
    traffic_installed=false
    traffic_service="missing"
    traffic_recovery_attempted=false
    traffic_error=""
    command -v nlbw >/dev/null 2>&1 && traffic_installed=true
    nlbwmon_init="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/nlbwmon"
    if [ -x "$nlbwmon_init" ]; then
        traffic_service="stopped"
        "$nlbwmon_init" running >/dev/null 2>&1 && traffic_service="running"
    fi
    if command -v ip >/dev/null 2>&1; then
        while IFS='|' read -r ip_address device mac state; do
            [ -n "$mac" ] || continue
            [ -n "$neighbours" ] && neighbours="$neighbours,"
            neighbours="$neighbours{\"ip\":\"$(json_escape "$ip_address")\",\"mac\":\"$(json_escape "$mac")\",\"interface\":\"$(json_escape "$device")\",\"state\":\"$(json_escape "$state")\"}"
        done <<EOF
$(ip neigh show 2>/dev/null | awk '
{
    ip_address=$1; device=""; mac=""; state=""
    for (i=2; i<=NF; i++) {
        if ($i == "dev" && i < NF) device=$(i+1)
        if ($i == "lladdr" && i < NF) mac=$(i+1)
        if ($i ~ /^(INCOMPLETE|REACHABLE|STALE|DELAY|PROBE|FAILED|NOARP|PERMANENT)$/) state=$i
    }
    if (device != "" && mac != "") print ip_address "|" device "|" mac "|" state
}' || true)
EOF
    fi
    case "$traffic_status" in
    service_stopped|query_failed)
        traffic_recovery_attempted=true
        ensure_nlbwmon_runtime >/dev/null 2>&1 || true
        traffic_status="$(nlbwmon_runtime_status)"
        if [ -x "$nlbwmon_init" ]; then
            traffic_service="stopped"
            "$nlbwmon_init" running >/dev/null 2>&1 && traffic_service="running"
        fi
        ;;
    esac
    if [ "$traffic_status" = "ready" ]; then
        traffic_file="/tmp/wrtmonitor-nlbw-$$.csv"
        if nlbw -c csv -g mac -n -q -s ';' >"$traffic_file" 2>/dev/null; then
            traffic_available=true
            traffic_status="ready"
            traffic_rows="/tmp/wrtmonitor-nlbw-$$.rows"
            awk -F';' '
                NR == 1 {
                    for (i = 1; i <= NF; i++) {
                        name = $i
                        gsub(/^[[:space:]\"]+|[[:space:]\"\r]+$/, "", name)
                        column[name] = i
                    }
                    next
                }
                column["mac"] && column["rx_bytes"] && column["tx_bytes"] {
                    mac = $(column["mac"])
                    rx = $(column["rx_bytes"])
                    tx = $(column["tx_bytes"])
                    gsub(/^[[:space:]\"]+|[[:space:]\"\r]+$/, "", mac)
                    gsub(/[^0-9]/, "", rx)
                    gsub(/[^0-9]/, "", tx)
                    print mac "|" (rx == "" ? 0 : rx) "|" (tx == "" ? 0 : tx)
                }
            ' "$traffic_file" >"$traffic_rows"
            while IFS='|' read -r mac rx_bytes tx_bytes; do
                case "$mac" in ""|00:00:00:00:00:00) continue ;; esac
                case "$rx_bytes" in ""|*[!0-9]*) rx_bytes=0 ;; esac
                case "$tx_bytes" in ""|*[!0-9]*) tx_bytes=0 ;; esac
                [ -n "$neighbours" ] && neighbours="$neighbours,"
                neighbours="$neighbours{\"mac\":\"$(json_escape "$mac")\",\"state\":\"traffic\",\"rx_bytes\":$rx_bytes,\"tx_bytes\":$tx_bytes}"
                traffic_records=$((traffic_records + 1))
            done <"$traffic_rows"
            rm -f "$traffic_rows"
        else
            traffic_status="query_failed"
        fi
        rm -f "$traffic_file"
    fi
    case "$traffic_status" in
        not_installed) traffic_error="nlbw executable is missing" ;;
        service_missing) traffic_error="nlbwmon init service is missing" ;;
        service_stopped) traffic_error="nlbwmon service did not start" ;;
        query_failed) traffic_error="nlbwmon query failed after recovery" ;;
    esac
    printf '{"neighbours":[%s],"dhcp":%s,"traffic":{"available":%s,"status":"%s","records":%s,"installed":%s,"service":"%s","recovery_attempted":%s,"error":"%s"}}' \
        "$neighbours" "$(dhcp_json)" "$traffic_available" "$traffic_status" "$traffic_records" \
        "$traffic_installed" "$traffic_service" "$traffic_recovery_attempted" "$(json_escape "$traffic_error")"
}

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

json_word_list() {
    values="$1"
    output=""
    set -f
    for value in $values; do
        [ -n "$output" ] && output="$output,"
        output="$output\"$(json_escape "$value")\""
    done
    set +f
    printf '[%s]' "$output"
}

network_topology_json() {
    segments=""
    for section in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=interface$/\1/p'); do
        proto="$(uci -q get "network.$section.proto" 2>/dev/null || true)"
        device="$(uci -q get "network.$section.device" 2>/dev/null || uci -q get "network.$section.ifname" 2>/dev/null || true)"
        ipaddr="$(uci -q get "network.$section.ipaddr" 2>/dev/null || true)"
        netmask="$(uci -q get "network.$section.netmask" 2>/dev/null || true)"
        ip6assign="$(uci -q get "network.$section.ip6assign" 2>/dev/null || true)"
        ip6hint="$(uci -q get "network.$section.ip6hint" 2>/dev/null || true)"
        disabled="$(uci -q get "network.$section.disabled" 2>/dev/null || echo 0)"
        dhcp_start="$(uci -q get "dhcp.$section.start" 2>/dev/null || true)"
        dhcp_limit="$(uci -q get "dhcp.$section.limit" 2>/dev/null || true)"
        dhcp_leasetime="$(uci -q get "dhcp.$section.leasetime" 2>/dev/null || true)"
        dhcp_ignore="$(uci -q get "dhcp.$section.ignore" 2>/dev/null || echo 0)"
        bridge_section=""
        if [ -n "$device" ]; then
            for candidate in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=device$/\1/p'); do
                [ "$(uci -q get "network.$candidate.type" 2>/dev/null || true)" = bridge ] || continue
                [ "$(uci -q get "network.$candidate.name" 2>/dev/null || true)" = "$device" ] || continue
                bridge_section="$candidate"
                break
            done
        fi
        segment_policy=isolated
        for zone_ref in $(uci -q show firewall 2>/dev/null | sed -n 's/^firewall\.\([^=]*\)=zone$/\1/p'); do
            zone_name="$(uci -q get "firewall.$zone_ref.name" 2>/dev/null || true)"
            zone_networks="$(uci -q get "firewall.$zone_ref.network" 2>/dev/null || true)"
            zone_matches=false
            [ "$zone_name" = "$section" ] && zone_matches=true
            for zone_network in $zone_networks; do [ "$zone_network" != "$section" ] || zone_matches=true; done
            [ "$zone_matches" = true ] || continue
            if [ "$(uci -q get "firewall.$zone_ref.input" 2>/dev/null || true)" = ACCEPT ]; then
                segment_policy=trusted
            else
                for forwarding_ref in $(uci -q show firewall 2>/dev/null | sed -n 's/^firewall\.\([^=]*\)=forwarding$/\1/p'); do
                    [ "$(uci -q get "firewall.$forwarding_ref.src" 2>/dev/null || true)" = "$zone_name" ] || continue
                    [ "$(uci -q get "firewall.$forwarding_ref.dest" 2>/dev/null || true)" = wan ] || continue
                    segment_policy=guest
                    break
                done
            fi
            break
        done
        [ -n "$segments" ] && segments="$segments,"
        segments="$segments{\"name\":\"$(json_escape "$section")\",\"proto\":\"$(json_escape "$proto")\",\"device\":\"$(json_escape "$device")\",\"bridge_section\":\"$(json_escape "$bridge_section")\",\"ip_address\":\"$(json_escape "$ipaddr")\",\"netmask\":\"$(json_escape "$netmask")\",\"ip6assign\":\"$(json_escape "$ip6assign")\",\"ip6hint\":\"$(json_escape "$ip6hint")\",\"policy\":\"$(json_escape "$segment_policy")\",\"enabled\":$( [ "$disabled" = 1 ] && printf false || printf true ),\"dhcp\":{\"enabled\":$( [ "$dhcp_ignore" = 1 ] || [ -z "$dhcp_start" ] && printf false || printf true ),\"start\":\"$(json_escape "$dhcp_start")\",\"limit\":\"$(json_escape "$dhcp_limit")\",\"leasetime\":\"$(json_escape "$dhcp_leasetime")\"}}"
    done

    bridges=""
    for section in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=device$/\1/p'); do
        type="$(uci -q get "network.$section.type" 2>/dev/null || true)"
        [ "$type" = bridge ] || continue
        name="$(uci -q get "network.$section.name" 2>/dev/null || echo "$section")"
        ports="$(uci -q get "network.$section.ports" 2>/dev/null || true)"
        stp="$(uci -q get "network.$section.stp" 2>/dev/null || echo 0)"
        igmp="$(uci -q get "network.$section.igmp_snooping" 2>/dev/null || echo 0)"
        vlan_filtering="$(uci -q get "network.$section.vlan_filtering" 2>/dev/null || echo 0)"
        [ -n "$bridges" ] && bridges="$bridges,"
        bridges="$bridges{\"section\":\"$(json_escape "$section")\",\"name\":\"$(json_escape "$name")\",\"ports\":$(json_word_list "$ports"),\"stp\":$( [ "$stp" = 1 ] && printf true || printf false ),\"igmp_snooping\":$( [ "$igmp" = 1 ] && printf true || printf false ),\"vlan_filtering\":$( [ "$vlan_filtering" = 1 ] && printf true || printf false )}"
    done

    vlans=""
    for ref in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^=]*\)=bridge-vlan$/\1/p'); do
        device="$(uci -q get "network.$ref.device" 2>/dev/null || true)"
        vlan_id="$(uci -q get "network.$ref.vlan" 2>/dev/null || true)"
        ports="$(uci -q get "network.$ref.ports" 2>/dev/null || true)"
        case "$vlan_id" in ''|*[!0-9]*) vlan_id=null ;; esac
        [ -n "$vlans" ] && vlans="$vlans,"
        vlans="$vlans{\"section\":\"$(json_escape "$ref")\",\"device\":\"$(json_escape "$device")\",\"vlan_id\":$vlan_id,\"ports\":$(json_word_list "$ports")}"
    done
    printf '{"segments":[%s],"bridges":[%s],"vlans":[%s]}' "$segments" "$bridges" "$vlans"
}

dns_privacy_json() {
    dot_installed=false; dot_running=false; doh_installed=false; doh_running=false
    [ -x /etc/init.d/stubby ] && dot_installed=true
    [ -x /etc/init.d/stubby ] && /etc/init.d/stubby running >/dev/null 2>&1 && dot_running=true
    [ -x /etc/init.d/https-dns-proxy ] && doh_installed=true
    [ -x /etc/init.d/https-dns-proxy ] && /etc/init.d/https-dns-proxy running >/dev/null 2>&1 && doh_running=true
    dot_provider="$(uci -q get 'stubby.@resolver[0].tls_auth_name' 2>/dev/null || true)"
    doh_url="$(uci -q get 'https-dns-proxy.@https-dns-proxy[0].resolver_url' 2>/dev/null || true)"
    printf '{"dot":{"installed":%s,"running":%s,"provider":"%s"},"doh":{"installed":%s,"running":%s,"resolver_url":"%s"}}' \
        "$dot_installed" "$dot_running" "$(json_escape "$dot_provider")" "$doh_installed" "$doh_running" "$(json_escape "$doh_url")"
}
