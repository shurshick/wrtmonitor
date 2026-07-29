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
