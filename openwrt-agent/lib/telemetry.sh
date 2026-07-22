telemetry() {
    agent_enabled || return 0
    [ -n "$(device_id)" ] || register_device
    body="$(telemetry_payload)"
    api POST /api/v1/agent/telemetry "$body" >/dev/null
}

telemetry_payload() {
    [ -n "$(device_id)" ] || register_device
    uptime_value="$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 0)"
    load_values="$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo '0 0 0')"
    load_value="$(printf '%s' "$load_values" | cut -d' ' -f1)"
    load_5m="$(printf '%s' "$load_values" | cut -d' ' -f2)"
    load_15m="$(printf '%s' "$load_values" | cut -d' ' -f3)"
    case "$uptime_value" in
        ""|*[!0-9]*) uptime_value="0" ;;
    esac
    load_value="$(json_escape "$load_value")"
    printf '{"device_id":"%s","telemetry":{"schema_version":2,"system":{"uptime":%s,"load":"%s","load_5m":"%s","load_15m":"%s","hostname":"%s","kernel":"%s","local_time":"%s","time":%s,"memory":%s,"processes":%s,"conntrack":%s,"services":%s,"ubus":%s},"cpu":%s,"storage":%s,"thermal":%s,"traffic":%s,"board":%s,"network":%s,"network_devices":%s,"wifi":%s,"wireless_status":%s,"clients":%s,"dhcp":%s,"perimeter":%s,"vpn":%s,"maintenance":%s,"agent":%s}}' \
        "$(device_id)" \
        "$uptime_value" \
        "$load_value" \
        "$(json_escape "$load_5m")" \
        "$(json_escape "$load_15m")" \
        "$(json_escape "$(uci -q get system.@system[0].hostname 2>/dev/null || hostname)")" \
        "$(json_escape "$(uname -r 2>/dev/null || true)")" \
        "$(json_escape "$(iso_now)")" \
        "$(system_time_json)" \
        "$(memory_json)" \
        "$(processes_json)" \
        "$(conntrack_json)" \
        "$(services_json)" \
        "$(ubus_json system info)" \
        "$(cpu_json)" \
        "$(storage_json)" \
        "$(thermal_json)" \
        "$(traffic_json)" \
        "$(ubus_json system board)" \
        "$(network_summary_json)" \
        "$(ubus_json network.device status)" \
        "$(wifi_status_json)" \
        "$(ubus_json network.wireless status)" \
        "$(clients_json)" \
        "$(dhcp_json)" \
        "$(perimeter_json)" \
        "$(vpn_json)" \
        "$(maintenance_json)" \
        "$(agent_status_json)"
}

system_time_json() {
    ntp_servers=""
    for server in $(uci -q get system.ntp.server 2>/dev/null || true); do
        [ -n "$ntp_servers" ] && ntp_servers="$ntp_servers,"
        ntp_servers="$ntp_servers\"$(json_escape "$server")\""
    done
    printf '{"zonename":"%s","timezone":"%s","ntp_enabled":%s,"ntp_servers":[%s]}' \
        "$(json_escape "$(uci -q get system.@system[0].zonename 2>/dev/null || true)")" \
        "$(json_escape "$(uci -q get system.@system[0].timezone 2>/dev/null || true)")" \
        "$( [ "$(uci -q get system.ntp.enabled 2>/dev/null || echo 0)" = 1 ] && printf true || printf false )" \
        "$ntp_servers"
}

maintenance_json() {
    installed=0
    upgrades=0
    installed_items=""
    upgrade_items=""
    package_manager_value="$(package_manager_name 2>/dev/null || true)"
    if [ -n "$package_manager_value" ]; then
        installed_data="$(package_list_installed || true)"
        upgrade_data="$(package_list_upgradeable || true)"
        installed="$(printf '%s\n' "$installed_data" | awk 'NF {count++} END {print count + 0}')"
        upgrades="$(printf '%s\n' "$upgrade_data" | awk 'NF {count++} END {print count + 0}')"
        package_count=0
        while IFS='|' read -r package_name package_version; do
            [ -n "$package_name" ] || continue
            [ -n "$installed_items" ] && installed_items="$installed_items,"
            installed_items="$installed_items{\"name\":\"$(json_escape "$package_name")\",\"version\":\"$(json_escape "$package_version")\"}"
            package_count=$((package_count + 1)); [ "$package_count" -ge 250 ] && break
        done <<EOF
$installed_data
EOF
        package_count=0
        while IFS='|' read -r package_name current_version available_version; do
            [ -n "$package_name" ] || continue
            [ -n "$upgrade_items" ] && upgrade_items="$upgrade_items,"
            upgrade_items="$upgrade_items{\"name\":\"$(json_escape "$package_name")\",\"current_version\":\"$(json_escape "$current_version")\",\"available_version\":\"$(json_escape "$available_version")\"}"
            package_count=$((package_count + 1)); [ "$package_count" -ge 100 ] && break
        done <<EOF
$upgrade_data
EOF
    fi
    cron_entries=0
    if [ -r "${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root" ]; then
        cron_entries="$(sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root" | wc -l | tr -d ' ')"
    fi
    recovery="$(uci -q get wrtmonitor.main.recovery_mode 2>/dev/null || echo 0)"
    staged_checksum="$(uci -q get wrtmonitor.main.staged_firmware_sha256 2>/dev/null || true)"
    printf '{"packages":{"manager":"%s","installed":%s,"upgradable":%s,"installed_items":[%s],"upgradable_items":[%s]},"cron_entries":%s,"recovery_mode":%s,"staged_firmware_sha256":"%s"}' \
        "$(json_escape "$package_manager_value")" "${installed:-0}" "${upgrades:-0}" "$installed_items" "$upgrade_items" "${cron_entries:-0}" \
        "$( [ "$recovery" = 1 ] && printf true || printf false )" \
        "$(json_escape "$staged_checksum")"
}

vpn_json() {
    wg_interfaces=""
    if command -v wg >/dev/null 2>&1; then
        for wg_iface in $(wg show interfaces 2>/dev/null || true); do
            wg_public="$(wg show "$wg_iface" public-key 2>/dev/null || true)"
            wg_port="$(wg show "$wg_iface" listen-port 2>/dev/null || echo 0)"
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
            wg_interfaces="$wg_interfaces{\"name\":\"$(json_escape "$wg_iface")\",\"public_key\":\"$(json_escape "$wg_public")\",\"listen_port\":${wg_port:-0},\"peers\":[${wg_peers}]}"
        done
    fi
    openvpn_clients=""
    if uci -q show openvpn >/dev/null 2>&1; then
        for ovpn_ref in $(uci -q show openvpn 2>/dev/null | sed -n 's/^openvpn\.\([^.=]*\)=openvpn$/\1/p'); do
            ovpn_name="$(uci -q get "openvpn.$ovpn_ref.wrtmonitor_name" 2>/dev/null || echo "$ovpn_ref")"
            ovpn_enabled="$(uci -q get "openvpn.$ovpn_ref.enabled" 2>/dev/null || echo 0)"
            [ -n "$openvpn_clients" ] && openvpn_clients="$openvpn_clients,"
            openvpn_clients="$openvpn_clients{\"name\":\"$(json_escape "$ovpn_name")\",\"enabled\":$( [ "$ovpn_enabled" = 1 ] && printf true || printf false )}"
        done
    fi
    policies=""
    if uci -q show pbr >/dev/null 2>&1; then
        for policy_ref in $(uci -q show pbr 2>/dev/null | sed -n 's/^pbr\.\(wrtmonitor_[^.=]*\)=policy$/\1/p'); do
            [ -n "$policies" ] && policies="$policies,"
            policies="$policies{\"name\":\"$(json_escape "${policy_ref#wrtmonitor_}")\",\"enabled\":$( [ "$(uci -q get "pbr.$policy_ref.enabled" 2>/dev/null || echo 0)" = 1 ] && printf true || printf false ),\"interface\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.interface" 2>/dev/null || true)")\",\"source\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.src_addr" 2>/dev/null || true)")\",\"destination\":\"$(json_escape "$(uci -q get "pbr.$policy_ref.dest_addr" 2>/dev/null || true)")\"}"
        done
    fi
    printf '{"wireguard":{"interfaces":[%s]},"openvpn":{"service":"%s","clients":[%s]},"policy":{"service":"%s","policies":[%s]}}' "$wg_interfaces" "$(service_state openvpn)" "$openvpn_clients" "$(service_state pbr)" "$policies"
}

perimeter_json() {
    routes=""
    for route_type in route route6; do
        index=0
        while uci -q get "network.@${route_type}[$index]" >/dev/null 2>&1; do
            ref="@${route_type}[$index]"; [ -n "$routes" ] && routes="$routes,"
            routes="$routes{\"name\":\"$(json_escape "$(uci -q get "network.$ref.wrtmonitor_name" 2>/dev/null || echo $route_type$index)")\",\"family\":\"$( [ "$route_type" = route6 ] && printf ipv6 || printf ipv4 )\",\"interface\":\"$(json_escape "$(uci -q get "network.$ref.interface" 2>/dev/null || true)")\",\"target\":\"$(json_escape "$(uci -q get "network.$ref.target" 2>/dev/null || true)")\",\"gateway\":\"$(json_escape "$(uci -q get "network.$ref.gateway" 2>/dev/null || true)")\",\"metric\":\"$(json_escape "$(uci -q get "network.$ref.metric" 2>/dev/null || true)")\"}"
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
    mwan_status=""
    if command -v mwan3 >/dev/null 2>&1; then
        mwan_status="$(mwan3 status 2>/dev/null | tr '\n' ' ' || true)"
    fi
    printf '{"routes":[%s],"firewall_zones":[%s],"firewall_forwardings":[%s],"firewall_rules":[%s],"mwan3":{"service":"%s","status":"%s"},"ddns":{"service":"%s","services":[%s]},"upnp":{"service":"%s","mappings":[%s]}}' "$routes" "$zones" "$forwardings" "$rules" "$(service_state mwan3)" "$(json_escape "$mwan_status")" "$(service_state ddns)" "$ddns_services" "$(service_state miniupnpd)" "$upnp_mappings"
}

memory_json() {
    total="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
    free="$(awk '/^MemFree:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
    available="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
    case "$total" in ""|*[!0-9]*) total="0" ;; esac
    case "$free" in ""|*[!0-9]*) free="0" ;; esac
    case "$available" in ""|*[!0-9]*) available="0" ;; esac
    printf '{"total_kb":%s,"free_kb":%s,"available_kb":%s}' "$total" "$free" "$available"
}

cpu_json() {
    cores="$(grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo 0)"
    model="$(sed -n 's/^model name[[:space:]]*:[[:space:]]*//p; s/^system type[[:space:]]*:[[:space:]]*//p' /proc/cpuinfo 2>/dev/null | head -n 1)"
    case "$cores" in ""|*[!0-9]*) cores="0" ;; esac
    printf '{"cores":%s,"model":"%s"}' "$cores" "$(json_escape "$model")"
}

storage_json() {
    line="$(df -k /overlay 2>/dev/null | awk 'NR==2 {print $2, $3, $4}')"
    [ -n "$line" ] || line="$(df -k / 2>/dev/null | awk 'NR==2 {print $2, $3, $4}')"
    total="0"
    used="0"
    available="0"
    IFS=' ' read -r total used available <<EOF
$line
EOF
    case "$total" in ""|*[!0-9]*) total="0" ;; esac
    case "$used" in ""|*[!0-9]*) used="0" ;; esac
    case "$available" in ""|*[!0-9]*) available="0" ;; esac
    printf '{"mount":"/overlay","total_kb":%s,"used_kb":%s,"available_kb":%s}' "$total" "$used" "$available"
}

thermal_json() {
    sensor="$(find /sys/class/thermal -name temp -type f 2>/dev/null | head -n 1)"
    if [ -z "$sensor" ] || [ ! -r "$sensor" ]; then
        printf '{"available":false}'
        return
    fi
    milli_celsius="$(cat "$sensor" 2>/dev/null || echo 0)"
    case "$milli_celsius" in ""|*[!0-9]*) milli_celsius="0" ;; esac
    printf '{"available":true,"milli_celsius":%s}' "$milli_celsius"
}

traffic_json() {
    values="$(awk 'NR > 2 && $1 !~ /^lo:/ { rx += $2; tx += $10 } END { printf "%d %d", rx, tx }' /proc/net/dev 2>/dev/null)"
    rx="0"
    tx="0"
    IFS=' ' read -r rx tx <<EOF
$values
EOF
    case "$rx" in ""|*[!0-9]*) rx="0" ;; esac
    case "$tx" in ""|*[!0-9]*) tx="0" ;; esac
    printf '{"rx_bytes":%s,"tx_bytes":%s}' "$rx" "$tx"
}

processes_json() {
    count="$(ps 2>/dev/null | wc -l | tr -d ' ' || echo 0)"
    case "$count" in ""|*[!0-9]*) count="0" ;; esac
    printf '{"count":%s}' "$count"
}

conntrack_json() {
    count="$(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null || echo 0)"
    maximum="$(cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || echo 0)"
    case "$count" in ""|*[!0-9]*) count="0" ;; esac
    case "$maximum" in ""|*[!0-9]*) maximum="0" ;; esac
    printf '{"count":%s,"max":%s}' "$count" "$maximum"
}

service_state() {
    service_name="$1"
    if [ ! -x "/etc/init.d/$service_name" ]; then
        printf 'unavailable'
    elif "/etc/init.d/$service_name" running >/dev/null 2>&1; then
        printf 'running'
    else
        printf 'stopped'
    fi
}

services_json() {
    printf '{"network":"%s","dnsmasq":"%s","firewall":"%s","odhcpd":"%s"}' \
        "$(service_state network)" \
        "$(service_state dnsmasq)" \
        "$(service_state firewall)" \
        "$(service_state odhcpd)"
}

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
    traffic_status="unavailable"
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
    if command -v nlbw >/dev/null 2>&1; then
        if [ -x /etc/init.d/nlbwmon ] && ! /etc/init.d/nlbwmon running >/dev/null 2>&1; then
            /etc/init.d/nlbwmon start >/dev/null 2>&1 || true
        fi
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
            done <"$traffic_rows"
            rm -f "$traffic_rows"
        else
            traffic_status="query_failed"
        fi
        rm -f "$traffic_file"
    fi
    printf '{"neighbours":[%s],"dhcp":%s,"traffic":{"available":%s,"status":"%s"}}' "$neighbours" "$(dhcp_json)" "$traffic_available" "$traffic_status"
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
    printf '{"interfaces":[%s]}' "$items"
}

wireless_section_name() {
    section_type="$1"
    section_index="$2"
    uci -q show wireless 2>/dev/null \
        | sed -n "s/^wireless\.\([^.=]*\)=$section_type$/\1/p" \
        | sed -n "$((section_index + 1))p"
}

wifi_schedule_json() {
    requested_radio="$1"
    schedule_index=0
    while uci -q get "wrtmonitor.@wifi_schedule[$schedule_index]" >/dev/null 2>&1; do
        schedule_radio="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].radio" 2>/dev/null || true)"
        if [ "$schedule_radio" = "$requested_radio" ]; then
            schedule_enabled="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].enabled" 2>/dev/null || echo 0)"
            schedule_start="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].start" 2>/dev/null || true)"
            schedule_stop="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].stop" 2>/dev/null || true)"
            schedule_days="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].weekdays" 2>/dev/null || true)"
            days_json=""
            for schedule_day in $schedule_days; do
                [ -n "$days_json" ] && days_json="$days_json,"
                days_json="$days_json\"$(json_escape "$schedule_day")\""
            done
            printf '{"enabled":%s,"weekdays":[%s],"start":"%s","stop":"%s"}' \
                "$( [ "$schedule_enabled" = "1" ] && printf true || printf false )" \
                "$days_json" "$(json_escape "$schedule_start")" "$(json_escape "$schedule_stop")"
            return 0
        fi
        schedule_index=$((schedule_index + 1))
    done
    printf '{"enabled":false,"weekdays":[],"start":"","stop":""}'
}

wifi_stations_json() {
    station_groups=""
    if command -v ubus >/dev/null 2>&1; then
        for hostapd_object in $(ubus list 'hostapd.*' 2>/dev/null || true); do
            station_interface="${hostapd_object#hostapd.}"
            station_response="$(ubus call "$hostapd_object" get_clients 2>/dev/null || true)"
            [ -n "$station_response" ] || continue
            station_file="/tmp/wrtmonitor-stations-$$"
            printf '%s' "$station_response" >"$station_file"
            station_clients="$(jsonfilter -i "$station_file" -e '@.clients' 2>/dev/null || printf '{}')"
            rm -f "$station_file"
            case "$station_clients" in \{*\}) ;; *) station_clients='{}' ;; esac
            station_ssid=""
            station_band=""
            if command -v iwinfo >/dev/null 2>&1; then
                station_info="$(iwinfo "$station_interface" info 2>/dev/null || true)"
                station_ssid="$(printf '%s\n' "$station_info" | sed -n 's/.*ESSID: "\(.*\)".*/\1/p' | head -n 1)"
                case "$station_info" in
                    *" GHz"*)
                        station_frequency="$(printf '%s\n' "$station_info" | sed -n 's/.*(\([0-9][0-9]*\.[0-9][0-9]*\) GHz).*/\1/p' | head -n 1)"
                        case "$station_frequency" in 2.*) station_band="2g" ;; 5.*) station_band="5g" ;; 6.*) station_band="6g" ;; esac
                        ;;
                esac
            fi
            [ -n "$station_groups" ] && station_groups="$station_groups,"
            station_groups="$station_groups{\"interface\":\"$(json_escape "$station_interface")\",\"ssid\":\"$(json_escape "$station_ssid")\",\"band\":\"$(json_escape "$station_band")\",\"clients\":$station_clients}"
        done
    fi
    printf '[%s]' "$station_groups"
}

wifi_status_json() {
    radios=""
    index=0
    while uci -q get "wireless.@wifi-device[$index]" >/dev/null 2>&1; do
        name="$(wireless_section_name wifi-device "$index")"
        [ -n "$name" ] || name="radio$index"
        disabled="$(uci -q get "wireless.@wifi-device[$index].disabled" 2>/dev/null || echo 0)"
        channel="$(uci -q get "wireless.@wifi-device[$index].channel" 2>/dev/null || true)"
        band="$(uci -q get "wireless.@wifi-device[$index].band" 2>/dev/null || true)"
        ssids=""
        interfaces=""
        encryption=""
        iface_index=0
        while uci -q get "wireless.@wifi-iface[$iface_index]" >/dev/null 2>&1; do
            iface_device="$(uci -q get "wireless.@wifi-iface[$iface_index].device" 2>/dev/null || true)"
            if [ "$iface_device" = "$name" ]; then
                iface_name="$(wireless_section_name wifi-iface "$iface_index")"
                [ -n "$iface_name" ] || iface_name="@wifi-iface[$iface_index]"
                ssid="$(uci -q get "wireless.@wifi-iface[$iface_index].ssid" 2>/dev/null || true)"
                encryption="$(uci -q get "wireless.@wifi-iface[$iface_index].encryption" 2>/dev/null || true)"
                mode="$(uci -q get "wireless.@wifi-iface[$iface_index].mode" 2>/dev/null || true)"
                network="$(uci -q get "wireless.@wifi-iface[$iface_index].network" 2>/dev/null || true)"
                hidden="$(uci -q get "wireless.@wifi-iface[$iface_index].hidden" 2>/dev/null || echo 0)"
                isolate="$(uci -q get "wireless.@wifi-iface[$iface_index].isolate" 2>/dev/null || echo 0)"
                iface_disabled="$(uci -q get "wireless.@wifi-iface[$iface_index].disabled" 2>/dev/null || echo 0)"
                ieee80211r="$(uci -q get "wireless.@wifi-iface[$iface_index].ieee80211r" 2>/dev/null || echo 0)"
                ieee80211k="$(uci -q get "wireless.@wifi-iface[$iface_index].ieee80211k" 2>/dev/null || echo 0)"
                bss_transition="$(uci -q get "wireless.@wifi-iface[$iface_index].bss_transition" 2>/dev/null || echo 0)"
                mobility_domain="$(uci -q get "wireless.@wifi-iface[$iface_index].mobility_domain" 2>/dev/null || true)"
                mesh_id="$(uci -q get "wireless.@wifi-iface[$iface_index].mesh_id" 2>/dev/null || true)"
                if [ -n "$ssid" ]; then
                    [ -n "$ssids" ] && ssids="$ssids,"
                    ssids="$ssids\"$(json_escape "$ssid")\""
                fi
                [ -n "$interfaces" ] && interfaces="$interfaces,"
                interfaces="$interfaces{\"id\":\"$(json_escape "$iface_name")\",\"index\":$iface_index,\"ssid\":\"$(json_escape "$ssid")\",\"enabled\":$( [ "$iface_disabled" = "1" ] && printf false || printf true ),\"encryption\":\"$(json_escape "$encryption")\",\"mode\":\"$(json_escape "$mode")\",\"network\":\"$(json_escape "$network")\",\"hidden\":$( [ "$hidden" = "1" ] && printf true || printf false ),\"isolate\":$( [ "$isolate" = "1" ] && printf true || printf false ),\"ieee80211r\":$( [ "$ieee80211r" = "1" ] && printf true || printf false ),\"ieee80211k\":$( [ "$ieee80211k" = "1" ] && printf true || printf false ),\"bss_transition\":$( [ "$bss_transition" = "1" ] && printf true || printf false ),\"mobility_domain\":\"$(json_escape "$mobility_domain")\",\"mesh_id\":\"$(json_escape "$mesh_id")\"}"
            fi
            iface_index=$((iface_index + 1))
        done
        up=true
        [ "$disabled" = "1" ] && up=false
        radio="{\"id\":\"$name\",\"name\":\"$name\",\"up\":$up,\"disabled\":$( [ "$disabled" = "1" ] && printf true || printf false ),\"ssid\":[$ssids],\"interfaces\":[${interfaces}]"
        [ -n "$channel" ] && radio="$radio,\"channel\":\"$(json_escape "$channel")\""
        [ -n "$band" ] && radio="$radio,\"band\":\"$(json_escape "$band")\""
        country="$(uci -q get "wireless.@wifi-device[$index].country" 2>/dev/null || true)"
        htmode="$(uci -q get "wireless.@wifi-device[$index].htmode" 2>/dev/null || true)"
        txpower="$(uci -q get "wireless.@wifi-device[$index].txpower" 2>/dev/null || true)"
        [ -n "$country" ] && radio="$radio,\"country\":\"$(json_escape "$country")\""
        [ -n "$htmode" ] && radio="$radio,\"htmode\":\"$(json_escape "$htmode")\""
        [ -n "$txpower" ] && radio="$radio,\"txpower\":\"$(json_escape "$txpower")\""
        [ -n "${encryption:-}" ] && radio="$radio,\"encryption\":\"$(json_escape "$encryption")\""
        radio="$radio,\"schedule\":$(wifi_schedule_json "$name")"
        radio="$radio}"
        [ -n "$radios" ] && radios="$radios,"
        radios="$radios$radio"
        index=$((index + 1))
    done
    if [ "$index" -gt 0 ]; then
        printf '{"available":true,"radios":[%s],"stations":%s}' "$radios" "$(wifi_stations_json)"
    else
        printf '{"available":false,"radios":[],"stations":[]}'
    fi
}
