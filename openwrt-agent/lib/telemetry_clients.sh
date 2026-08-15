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
        traffic_error_file="/tmp/wrtmonitor-nlbw-$$.err"
        if nlbw_query_csv >"$traffic_file" 2>"$traffic_error_file"; then
            traffic_available=true
            traffic_status="ready"
            traffic_rows="/tmp/wrtmonitor-nlbw-$$.rows"
            if awk -F '\t' '
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
                END {
                    if (!column["mac"] || !column["rx_bytes"] || !column["tx_bytes"])
                        exit 42
                }
            ' "$traffic_file" >"$traffic_rows"; then
                parser_status=0
            else
                parser_status=$?
            fi
            if [ "$parser_status" -ne 0 ]; then
                traffic_available=false
                traffic_status="invalid_output"
                if [ "$parser_status" -eq 42 ]; then
                    traffic_error="nlbw CSV header does not contain mac, rx_bytes and tx_bytes"
                else
                    traffic_error="nlbw CSV parser failed with exit code $parser_status"
                fi
            fi
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
            traffic_error="$(head -c 240 "$traffic_error_file" 2>/dev/null || true)"
        fi
        rm -f "$traffic_error_file"
        rm -f "$traffic_file"
    fi
    case "$traffic_status" in
        not_installed) traffic_error="nlbw executable is missing" ;;
        service_missing) traffic_error="nlbwmon init service is missing" ;;
        service_stopped) traffic_error="nlbwmon service did not start" ;;
        query_failed) [ -n "$traffic_error" ] || traffic_error="nlbwmon query failed after recovery" ;;
        invalid_output) [ -n "$traffic_error" ] || traffic_error="nlbwmon returned an unsupported CSV format" ;;
    esac
    printf '{"neighbours":[%s],"dhcp":%s,"traffic":{"available":%s,"status":"%s","records":%s,"installed":%s,"service":"%s","recovery_attempted":%s,"error":"%s"}}' \
        "$neighbours" "$(dhcp_json)" "$traffic_available" "$traffic_status" "$traffic_records" \
        "$traffic_installed" "$traffic_service" "$traffic_recovery_attempted" "$(json_escape "$traffic_error")"
}
