vpn_json() {
    wg_interfaces=""
    if uci -q show network >/dev/null 2>&1; then
        for wg_iface in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=interface$/\1/p'); do
            [ "$(uci -q get "network.$wg_iface.proto" 2>/dev/null || true)" = wireguard ] || continue
            wg_public="$(wg show "$wg_iface" public-key 2>/dev/null || true)"
            wg_port="$(wg show "$wg_iface" listen-port 2>/dev/null || uci -q get "network.$wg_iface.listen_port" 2>/dev/null || echo 0)"
            wg_addresses="$(uci -q get "network.$wg_iface.addresses" 2>/dev/null || true)"
            wg_disabled="$(uci -q get "network.$wg_iface.disabled" 2>/dev/null || echo 0)"
            wg_runtime=false; wg show "$wg_iface" >/dev/null 2>&1 && wg_runtime=true
            wg_peers=""
            wg_dump="$(wg show "$wg_iface" dump 2>/dev/null | sed '1d' || true)"
            while IFS="$(printf '\t')" read -r peer_public _ peer_endpoint peer_allowed peer_handshake peer_rx peer_tx peer_keepalive; do
                [ -n "$peer_public" ] || continue
                [ -n "$wg_peers" ] && wg_peers="$wg_peers,"
                wg_peers="$wg_peers{\"public_key\":\"$(json_escape "$peer_public")\",\"endpoint\":\"$(json_escape "$peer_endpoint")\",\"allowed_ips\":\"$(json_escape "$peer_allowed")\",\"latest_handshake\":${peer_handshake:-0},\"rx_bytes\":${peer_rx:-0},\"tx_bytes\":${peer_tx:-0},\"persistent_keepalive\":${peer_keepalive:-0}}"
            done <<EOF
$wg_dump
EOF
            [ -n "$wg_interfaces" ] && wg_interfaces="$wg_interfaces,"
            wg_interfaces="$wg_interfaces{\"section\":\"$(json_escape "$wg_iface")\",\"name\":\"$(json_escape "$wg_iface")\",\"configured\":true,\"enabled\":$( [ "$wg_disabled" = 1 ] && printf false || printf true ),\"runtime\":$wg_runtime,\"addresses\":$(json_word_list "$wg_addresses"),\"public_key\":\"$(json_escape "$wg_public")\",\"listen_port\":${wg_port:-0},\"peers\":[${wg_peers}]}"
        done
    fi
    openvpn_clients=""
    if uci -q show openvpn >/dev/null 2>&1; then
        for ovpn_ref in $(uci -q show openvpn 2>/dev/null | sed -n 's/^openvpn\.\([^.=]*\)=openvpn$/\1/p'); do
            ovpn_name="$(uci -q get "openvpn.$ovpn_ref.wrtmonitor_name" 2>/dev/null || echo "$ovpn_ref")"
            ovpn_enabled="$(uci -q get "openvpn.$ovpn_ref.enabled" 2>/dev/null || echo 0)"
            [ -n "$openvpn_clients" ] && openvpn_clients="$openvpn_clients,"
            openvpn_clients="$openvpn_clients{\"section\":\"$(json_escape "$ovpn_ref")\",\"name\":\"$(json_escape "$ovpn_name")\",\"enabled\":$( [ "$ovpn_enabled" = 1 ] && printf true || printf false ),\"runtime\":$(pgrep -f "wrtmonitor-$ovpn_ref.conf" >/dev/null 2>&1 && printf true || printf false),\"export_available\":$( [ -n "$(uci -q get "openvpn.$ovpn_ref.wrtmonitor_config_b64" 2>/dev/null || true)" ] && printf true || printf false )}"
        done
    fi
    policies=""
    if uci -q show pbr >/dev/null 2>&1; then
        for policy_ref in $(uci -q show pbr 2>/dev/null | sed -n 's/^pbr\.\([^.=]*\)=policy$/\1/p'); do
            [ -n "$policies" ] && policies="$policies,"
            policies="$policies{\"section\":\"$(json_escape "$policy_ref")\",\"name\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.name" 2>/dev/null || echo "${policy_ref#wrtmonitor_}")")\",\"enabled\":$( [ "$(uci -q get "pbr.$policy_ref.enabled" 2>/dev/null || echo 0)" = 1 ] && printf true || printf false ),\"interface\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.interface" 2>/dev/null || true)")\",\"source\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.src_addr" 2>/dev/null || true)")\",\"destination\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.dest_addr" 2>/dev/null || true)")\",\"protocol\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.proto" 2>/dev/null || echo all)")\"}"
        done
    fi
    printf '{"wireguard":{"interfaces":[%s]},"openvpn":{"service":"%s","clients":[%s]},"policy":{"service":"%s","policies":[%s]}}' "$wg_interfaces" "$(service_state openvpn)" "$openvpn_clients" "$(service_state pbr)" "$policies"
}

mwan3_json() {
    installed=false
    [ -x /etc/init.d/mwan3 ] && installed=true
    enabled="$(uci -q get mwan3.globals.enabled 2>/dev/null || echo 0)"
    members=""
    for member in wrtmonitor_primary wrtmonitor_secondary; do
        interface="$(uci -q get "mwan3.$member.interface" 2>/dev/null || true)"
        [ -n "$interface" ] || continue
        metric="$(uci -q get "mwan3.$member.metric" 2>/dev/null || true)"
        tracking="$(uci -q get "mwan3.$interface.track_ip" 2>/dev/null || true)"
        interval="$(uci -q get "mwan3.$interface.interval" 2>/dev/null || true)"
        down="$(uci -q get "mwan3.$interface.down" 2>/dev/null || true)"
        up="$(uci -q get "mwan3.$interface.up" 2>/dev/null || true)"
        case "$metric" in ''|*[!0-9]*) metric=null ;; esac
        case "$interval" in ''|*[!0-9]*) interval=null ;; esac
        case "$down" in ''|*[!0-9]*) down=null ;; esac
        case "$up" in ''|*[!0-9]*) up=null ;; esac
        [ -n "$members" ] && members="$members,"
        members="$members{\"role\":\"$(json_escape "${member#wrtmonitor_}")\",\"interface\":\"$(json_escape "$interface")\",\"metric\":$metric,\"track_ips\":$(json_word_list "$tracking"),\"interval\":$interval,\"down\":$down,\"up\":$up}"
    done
    raw_status=""
    if command -v mwan3 >/dev/null 2>&1; then
        raw_status="$(mwan3 status 2>/dev/null | tr '\n' ' ' || true)"
    fi
    printf '{"installed":%s,"service":"%s","enabled":%s,"members":[%s],"status":"%s"}' \
        "$installed" "$(service_state mwan3)" "$( [ "$enabled" = 1 ] && printf true || printf false )" \
        "$members" "$(json_escape "$raw_status")"
}

perimeter_json() {
    routes=""
    for route_type in route route6; do
        index=0
        while uci -q get "network.@${route_type}[$index]" >/dev/null 2>&1; do
            ref="@${route_type}[$index]"; [ -n "$routes" ] && routes="$routes,"
            routes="$routes{\"section\":\"$(json_escape "$ref")\",\"name\":\"$(json_escape "$(uci -q get "network.$ref.wrtmonitor_name" 2>/dev/null || echo $route_type$index)")\",\"family\":\"$( [ "$route_type" = route6 ] && printf ipv6 || printf ipv4 )\",\"interface\":\"$(json_escape "$(uci -q get "network.$ref.interface" 2>/dev/null || true)")\",\"target\":\"$(json_escape "$(uci -q get "network.$ref.target" 2>/dev/null || true)")\",\"gateway\":\"$(json_escape "$(uci -q get "network.$ref.gateway" 2>/dev/null || true)")\",\"metric\":\"$(json_escape "$(uci -q get "network.$ref.metric" 2>/dev/null || true)")\"}"
            index=$((index + 1))
        done
    done
    zones=""; index=0
    while uci -q get "firewall.@zone[$index]" >/dev/null 2>&1; do
        ref="@zone[$index]"; [ -n "$zones" ] && zones="$zones,"
        zones="$zones{\"section\":\"$(json_escape "$ref")\",\"name\":\"$(json_escape "$(uci -q get "firewall.$ref.name" 2>/dev/null || true)")\",\"networks\":\"$(json_escape "$(uci -q get "firewall.$ref.network" 2>/dev/null || true)")\",\"input\":\"$(json_escape "$(uci -q get "firewall.$ref.input" 2>/dev/null || true)")\",\"output\":\"$(json_escape "$(uci -q get "firewall.$ref.output" 2>/dev/null || true)")\",\"forward\":\"$(json_escape "$(uci -q get "firewall.$ref.forward" 2>/dev/null || true)")\",\"masquerade\":$( [ "$(uci -q get "firewall.$ref.masq" 2>/dev/null || echo 0)" = 1 ] && printf true || printf false )}"
        index=$((index + 1))
    done
    forwardings=""; index=0
    while uci -q get "firewall.@forwarding[$index]" >/dev/null 2>&1; do
        ref="@forwarding[$index]"; [ -n "$forwardings" ] && forwardings="$forwardings,"
        forwardings="$forwardings{\"section\":\"$(json_escape "$ref")\",\"src\":\"$(json_escape "$(uci -q get "firewall.$ref.src" 2>/dev/null || true)")\",\"dest\":\"$(json_escape "$(uci -q get "firewall.$ref.dest" 2>/dev/null || true)")\"}"
        index=$((index + 1))
    done
    rules=""; index=0
    while uci -q get "firewall.@rule[$index]" >/dev/null 2>&1; do
        ref="@rule[$index]"; [ -n "$rules" ] && rules="$rules,"
        rules="$rules{\"section\":\"$(json_escape "$ref")\",\"name\":\"$(json_escape "$(uci -q get "firewall.$ref.name" 2>/dev/null || echo rule$index)")\",\"src\":\"$(json_escape "$(uci -q get "firewall.$ref.src" 2>/dev/null || true)")\",\"dest\":\"$(json_escape "$(uci -q get "firewall.$ref.dest" 2>/dev/null || true)")\",\"protocol\":\"$(json_escape "$(uci -q get "firewall.$ref.proto" 2>/dev/null || true)")\",\"src_ip\":\"$(json_escape "$(uci -q get "firewall.$ref.src_ip" 2>/dev/null || true)")\",\"dest_ip\":\"$(json_escape "$(uci -q get "firewall.$ref.dest_ip" 2>/dev/null || true)")\",\"src_port\":\"$(json_escape "$(uci -q get "firewall.$ref.src_port" 2>/dev/null || true)")\",\"dest_port\":\"$(json_escape "$(uci -q get "firewall.$ref.dest_port" 2>/dev/null || true)")\",\"target\":\"$(json_escape "$(uci -q get "firewall.$ref.target" 2>/dev/null || true)")\"}"
        index=$((index + 1))
    done
    redirects=""; index=0
    while uci -q get "firewall.@redirect[$index]" >/dev/null 2>&1; do
        ref="@redirect[$index]"; [ -n "$redirects" ] && redirects="$redirects,"
        redirects="$redirects{\"section\":\"$(json_escape "$ref")\",\"name\":\"$(json_escape "$(uci -q get "firewall.$ref.name" 2>/dev/null || echo redirect$index)")\",\"enabled\":$( [ "$(uci -q get "firewall.$ref.enabled" 2>/dev/null || echo 1)" = 0 ] && printf false || printf true ),\"src\":\"$(json_escape "$(uci -q get "firewall.$ref.src" 2>/dev/null || true)")\",\"dest\":\"$(json_escape "$(uci -q get "firewall.$ref.dest" 2>/dev/null || true)")\",\"protocol\":\"$(json_escape "$(uci -q get "firewall.$ref.proto" 2>/dev/null || true)")\",\"src_ip\":\"$(json_escape "$(uci -q get "firewall.$ref.src_ip" 2>/dev/null || true)")\",\"src_port\":\"$(json_escape "$(uci -q get "firewall.$ref.src_dport" 2>/dev/null || uci -q get "firewall.$ref.src_port" 2>/dev/null || true)")\",\"dest_ip\":\"$(json_escape "$(uci -q get "firewall.$ref.dest_ip" 2>/dev/null || true)")\",\"dest_port\":\"$(json_escape "$(uci -q get "firewall.$ref.dest_port" 2>/dev/null || true)")\",\"target\":\"$(json_escape "$(uci -q get "firewall.$ref.target" 2>/dev/null || echo DNAT)")\"}"
        index=$((index + 1))
    done
    ddns_services=""; index=0
    while uci -q get "ddns.@service[$index]" >/dev/null 2>&1; do
        ref="@service[$index]"; [ -n "$ddns_services" ] && ddns_services="$ddns_services,"
        ddns_services="$ddns_services{\"name\":\"$(json_escape "$(uci -q get "ddns.$ref.lookup_host" 2>/dev/null || uci -q get "ddns.$ref.domain" 2>/dev/null || echo service$index)")\",\"enabled\":$( [ "$(uci -q get "ddns.$ref.enabled" 2>/dev/null || echo 0)" = 1 ] && printf true || printf false ),\"provider\":\"$(json_escape "$(uci -q get "ddns.$ref.service_name" 2>/dev/null || true)")\",\"interface\":\"$(json_escape "$(uci -q get "ddns.$ref.interface" 2>/dev/null || true)")\"}"
        index=$((index + 1))
    done
    upnp_mappings=""; leases_file=""
    for candidate in /var/run/miniupnpd.leases /tmp/miniupnpd.leases /tmp/upnp.leases; do [ -r "$candidate" ] && leases_file="$candidate" && break; done
    if [ -n "$leases_file" ]; then
        while IFS= read -r mapping; do [ -n "$mapping" ] || continue; [ -n "$upnp_mappings" ] && upnp_mappings="$upnp_mappings,"; upnp_mappings="$upnp_mappings\"$(json_escape "$mapping")\""; done <"$leases_file"
    fi
    printf '{"routes":[%s],"firewall_zones":[%s],"firewall_forwardings":[%s],"firewall_rules":[%s],"firewall_redirects":[%s],"mwan3":%s,"ddns":{"service":"%s","services":[%s]},"upnp":{"service":"%s","mappings":[%s]}}' "$routes" "$zones" "$forwardings" "$rules" "$redirects" "$(mwan3_json)" "$(service_state ddns)" "$ddns_services" "$(service_state miniupnpd)" "$upnp_mappings"
}
