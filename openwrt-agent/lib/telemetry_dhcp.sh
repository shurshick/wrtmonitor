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
