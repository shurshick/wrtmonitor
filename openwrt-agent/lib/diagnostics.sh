server_host() {
    server_url | sed -n 's#^[a-zA-Z]*://\([^/:]*\).*$#\1#p'
}

dependencies_json() {
    manifest="$(dependency_manifest_json)"
    if dependencies_healthy; then
        printf '{"status":"ok","manifest":%s}' "$manifest"
    else
        printf '{"status":"failed","manifest":%s}' "$manifest"
    fi
}

check_server_json() {
    url="$(server_url)"
    if [ -z "$url" ]; then
        printf '{"status":"failed","reason":"server_url not configured"}'
        return
    fi
    if ! command -v curl >/dev/null 2>&1; then
        printf '{"status":"failed","reason":"curl not installed"}'
        return
    fi
    status="$(curl -sS --connect-timeout 5 --max-time 15 -o /tmp/wrtmonitor-health-$$ -w '%{http_code}' "$url/health" 2>/dev/null || true)"
    rm -f /tmp/wrtmonitor-health-$$
    case "$status" in
        200) printf '{"status":"ok","http_status":200}' ;;
        "") printf '{"status":"failed","reason":"request failed"}' ;;
        *) printf '{"status":"failed","http_status":%s}' "$status" ;;
    esac
}

check_dns_json() {
    host="$(server_host)"
    if [ -z "$host" ]; then
        printf '{"status":"failed","reason":"server host not configured"}'
        return
    fi
    if nslookup "$host" >/dev/null 2>&1 || ping -c 1 -W 1 "$host" >/dev/null 2>&1; then
        printf '{"status":"ok"}'
    else
        printf '{"status":"failed","reason":"dns lookup failed"}'
    fi
}

check_route_json() {
    default_route="$(ip route 2>/dev/null | awk '/^default / {print; exit}')"
    if [ -n "$default_route" ]; then
        gateway="$(printf '%s' "$default_route" | awk '{for (i = 1; i <= NF; i++) if ($i == "via") {print $(i + 1); exit}}')"
        printf '{"status":"ok","gateway":"%s"}' "$(json_escape "$gateway")"
    else
        printf '{"status":"failed","reason":"default route not found"}'
    fi
}

check_wifi_json() {
    if ! uci -q get wireless.@wifi-device[0] >/dev/null 2>&1; then
        printf '{"status":"unavailable","reason":"no radio","radio_count":0}'
        return
    fi
    count=0
    while uci -q get "wireless.@wifi-device[$count]" >/dev/null 2>&1; do
        count=$((count + 1))
    done
    printf '{"status":"ok","wifi_status_available":%s,"iwinfo_available":%s,"radio_count":%s}' \
        "$(command -v wifi >/dev/null 2>&1 && printf true || printf false)" \
        "$(command -v iwinfo >/dev/null 2>&1 && printf true || printf false)" \
        "$count"
}

diagnostics_json() {
    printf '{"server":%s,"dns":%s,"route":%s,"wifi":%s,"dependencies":%s}' \
        "$(check_server_json)" \
        "$(check_dns_json)" \
        "$(check_route_json)" \
        "$(check_wifi_json)" \
        "$(dependencies_json)"
}

diagnostics_checks_json() {
    checks="$1"
    printf '{'
    first=1
    case ",$checks," in
        *",server,"*) printf '"server":%s' "$(check_server_json)"; first=0 ;;
    esac
    case ",$checks," in
        *",dns,"*) [ "$first" -eq 0 ] && printf ','; printf '"dns":%s' "$(check_dns_json)"; first=0 ;;
    esac
    case ",$checks," in
        *",route,"*) [ "$first" -eq 0 ] && printf ','; printf '"route":%s' "$(check_route_json)"; first=0 ;;
    esac
    case ",$checks," in
        *",wifi,"*) [ "$first" -eq 0 ] && printf ','; printf '"wifi":%s' "$(check_wifi_json)"; first=0 ;;
    esac
    case ",$checks," in
        *",dependencies,"*) [ "$first" -eq 0 ] && printf ','; printf '"dependencies":%s' "$(dependencies_json)" ;;
    esac
    printf '}'
}
