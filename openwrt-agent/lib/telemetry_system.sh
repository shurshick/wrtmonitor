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
    cores="$(find /sys/devices/system/cpu -maxdepth 1 -type d -name 'cpu[0-9]*' 2>/dev/null | wc -l | tr -d ' ')"
    [ "$cores" -gt 0 ] 2>/dev/null || cores="$(grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo 0)"
    model="$(sed -n 's/^model name[[:space:]]*:[[:space:]]*//p; s/^Hardware[[:space:]]*:[[:space:]]*//p; s/^Processor[[:space:]]*:[[:space:]]*//p; s/^system type[[:space:]]*:[[:space:]]*//p' /proc/cpuinfo 2>/dev/null | head -n 1)"
    compatible="$(read_device_tree_value /proc/device-tree/cpus/cpu@0/compatible | head -n 1)"
    [ -n "$compatible" ] || compatible="$(read_device_tree_value /sys/firmware/devicetree/base/cpus/cpu@0/compatible | head -n 1)"
    [ -n "$model" ] || model="$compatible"
    architecture="$(uname -m 2>/dev/null || true)"
    current_khz="0"
    max_khz="0"
    frequencies=""
    for cpu_path in /sys/devices/system/cpu/cpu[0-9]*; do
        [ -d "$cpu_path" ] || continue
        cpu_name="$(basename "$cpu_path")"
        current="$(cat "$cpu_path/cpufreq/scaling_cur_freq" 2>/dev/null || cat "$cpu_path/cpufreq/cpuinfo_cur_freq" 2>/dev/null || echo 0)"
        maximum="$(cat "$cpu_path/cpufreq/cpuinfo_max_freq" 2>/dev/null || cat "$cpu_path/cpufreq/scaling_max_freq" 2>/dev/null || echo 0)"
        case "$current" in ""|*[!0-9]*) current="0" ;; esac
        case "$maximum" in ""|*[!0-9]*) maximum="0" ;; esac
        [ "$current" -gt "$current_khz" ] 2>/dev/null && current_khz="$current"
        [ "$maximum" -gt "$max_khz" ] 2>/dev/null && max_khz="$maximum"
        [ -n "$frequencies" ] && frequencies="$frequencies,"
        frequencies="$frequencies{\"cpu\":\"$(json_escape "$cpu_name")\",\"current_khz\":$current,\"max_khz\":$maximum}"
    done
    case "$cores" in ""|*[!0-9]*) cores="0" ;; esac
    printf '{"cores":%s,"model":"%s","architecture":"%s","compatible":"%s","current_khz":%s,"max_khz":%s,"frequencies":[%s]}' \
        "$cores" "$(json_escape "$model")" "$(json_escape "$architecture")" \
        "$(json_escape "$compatible")" "$current_khz" "$max_khz" "$frequencies"
}

read_device_tree_value() {
    path="$1"
    [ -r "$path" ] || return 0
    tr '\000' '\n' <"$path" 2>/dev/null | sed '/^$/d'
}

hardware_identity_json() {
    dt_root="/sys/firmware/devicetree/base"
    [ -d "$dt_root" ] || dt_root="/proc/device-tree"
    model="$(read_device_tree_value "$dt_root/model" | head -n 1)"
    compatible_json=""
    compatible_text=""
    while IFS= read -r item; do
        [ -n "$item" ] || continue
        [ -n "$compatible_json" ] && compatible_json="$compatible_json,"
        compatible_json="$compatible_json\"$(json_escape "$item")\""
        [ -n "$compatible_text" ] && compatible_text="$compatible_text,"
        compatible_text="$compatible_text$item"
    done <<EOF
$(read_device_tree_value "$dt_root/compatible")
EOF
    board_name="$(ubus call system board 2>/dev/null | jsonfilter -e '@.board_name' 2>/dev/null || true)"
    [ -n "$model" ] || model="$(ubus call system board 2>/dev/null | jsonfilter -e '@.model' 2>/dev/null || true)"
    target="$(sed -n "s/^DISTRIB_TARGET='\([^']*\)'.*/\1/p" /etc/openwrt_release 2>/dev/null | head -n 1)"
    package_arch="$(opkg print-architecture 2>/dev/null | awk 'END {print $2}' || true)"
    [ -n "$package_arch" ] || package_arch="$(apk --print-arch 2>/dev/null || true)"
    printf '{"state":"observed","model":"%s","board_name":"%s","compatible":[%s],"compatible_text":"%s","target":"%s","package_arch":"%s","architecture":"%s"}' \
        "$(json_escape "$model")" "$(json_escape "$board_name")" "$compatible_json" \
        "$(json_escape "$compatible_text")" "$(json_escape "$target")" \
        "$(json_escape "$package_arch")" "$(json_escape "$(uname -m 2>/dev/null || true)")"
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
    sensors=""
    primary=""
    count="0"
    throttling_supported="false"
    throttling_active="false"
    thermal_pressure="0"
    for pressure_path in /sys/devices/system/cpu/cpu[0-9]*/thermal_pressure; do
        [ -r "$pressure_path" ] || continue
        throttling_supported="true"
        pressure="$(cat "$pressure_path" 2>/dev/null || echo 0)"
        case "$pressure" in ""|*[!0-9]*) pressure="0" ;; esac
        [ "$pressure" -gt "$thermal_pressure" ] 2>/dev/null && thermal_pressure="$pressure"
        [ "$pressure" -gt 0 ] 2>/dev/null && throttling_active="true"
    done
    for zone in /sys/class/thermal/thermal_zone*; do
        [ -r "$zone/temp" ] || continue
        value="$(cat "$zone/temp" 2>/dev/null || true)"
        case "$value" in ""|*[!0-9-]*) continue ;; esac
        sensor_id="$(basename "$zone")"
        sensor_type="$(cat "$zone/type" 2>/dev/null || echo "$sensor_id")"
        warning=""
        critical=""
        for trip_temp_path in "$zone"/trip_point_*_temp; do
            [ -r "$trip_temp_path" ] || continue
            trip_temp="$(cat "$trip_temp_path" 2>/dev/null || true)"
            case "$trip_temp" in ""|*[!0-9]*) continue ;; esac
            trip_prefix="${trip_temp_path%_temp}"
            trip_type="$(cat "${trip_prefix}_type" 2>/dev/null || true)"
            case "$trip_type" in
                passive|hot)
                    if [ -z "$warning" ] || [ "$trip_temp" -lt "$warning" ]; then warning="$trip_temp"; fi
                    ;;
                critical)
                    if [ -z "$critical" ] || [ "$trip_temp" -lt "$critical" ]; then critical="$trip_temp"; fi
                    ;;
            esac
        done
        warning_json="null"; [ -n "$warning" ] && warning_json="$warning"
        critical_json="null"; [ -n "$critical" ] && critical_json="$critical"
        [ -n "$sensors" ] && sensors="$sensors,"
        sensors="$sensors{\"id\":\"$(json_escape "$sensor_id")\",\"subsystem\":\"thermal\",\"type\":\"$(json_escape "$sensor_type")\",\"label\":\"$(json_escape "$sensor_type")\",\"milli_celsius\":$value,\"warning_milli_celsius\":$warning_json,\"critical_milli_celsius\":$critical_json}"
        [ -n "$primary" ] || primary="$value"
        count=$((count + 1))
    done
    for hwmon in /sys/class/hwmon/hwmon*; do
        [ -d "$hwmon" ] || continue
        hwmon_name="$(cat "$hwmon/name" 2>/dev/null || basename "$hwmon")"
        for input in "$hwmon"/temp*_input; do
            [ -r "$input" ] || continue
            value="$(cat "$input" 2>/dev/null || true)"
            case "$value" in ""|*[!0-9-]*) continue ;; esac
            input_name="$(basename "$input" _input)"
            label="$(cat "$hwmon/${input_name}_label" 2>/dev/null || echo "$hwmon_name $input_name")"
            sensor_id="$(basename "$hwmon")_$input_name"
            warning="$(cat "$hwmon/${input_name}_max" 2>/dev/null || true)"
            critical="$(cat "$hwmon/${input_name}_crit" 2>/dev/null || true)"
            case "$warning" in ""|*[!0-9]*) warning="" ;; esac
            case "$critical" in ""|*[!0-9]*) critical="" ;; esac
            warning_json="null"; [ -n "$warning" ] && warning_json="$warning"
            critical_json="null"; [ -n "$critical" ] && critical_json="$critical"
            [ -n "$sensors" ] && sensors="$sensors,"
            sensors="$sensors{\"id\":\"$(json_escape "$sensor_id")\",\"subsystem\":\"hwmon\",\"type\":\"$(json_escape "$hwmon_name")\",\"label\":\"$(json_escape "$label")\",\"milli_celsius\":$value,\"warning_milli_celsius\":$warning_json,\"critical_milli_celsius\":$critical_json}"
            [ -n "$primary" ] || primary="$value"
            count=$((count + 1))
        done
    done
    if [ "$count" -eq 0 ]; then
        if [ "$throttling_supported" = "true" ]; then
            printf '{"available":false,"state":"unsupported","sensors":[],"throttling":{"state":"observed","active":%s,"thermal_pressure":%s}}' "$throttling_active" "$thermal_pressure"
        else
            printf '{"available":false,"state":"unsupported","sensors":[],"throttling":{"state":"unsupported","active":null}}'
        fi
        return
    fi
    if [ "$throttling_supported" = "true" ]; then
        throttling_json="{\"state\":\"observed\",\"active\":$throttling_active,\"thermal_pressure\":$thermal_pressure}"
    else
        throttling_json='{"state":"unsupported","active":null}'
    fi
    printf '{"available":true,"state":"observed","milli_celsius":%s,"sensor_count":%s,"sensors":[%s],"throttling":%s}' "$primary" "$count" "$sensors" "$throttling_json"
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
