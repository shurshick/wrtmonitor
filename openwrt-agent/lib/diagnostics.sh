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
    curl_code=0
    status="$(curl -sS --connect-timeout 5 --max-time 15 -o /tmp/wrtmonitor-health-$$ -w '%{http_code}' "$url/health" 2>/dev/null)" || curl_code=$?
    rm -f /tmp/wrtmonitor-health-$$
    if [ "$curl_code" -ne 0 ]; then
        case "$curl_code" in
            6) code=dns_failed; reason='Server name could not be resolved'; action='Check router DNS and server hostname' ;;
            7) code=server_unreachable; reason='Server connection failed'; action='Check URL, port, route and server availability' ;;
            28) code=connection_timeout; reason='Server did not respond in time'; action='Check WAN and backend availability' ;;
            35|51|60) code=tls_failed; reason='HTTPS verification failed'; action='Check router clock, CA bundle and server certificate; do not disable TLS verification' ;;
            *) code=transport_failed; reason='Server request failed'; action='Run diagnostics and check network connectivity' ;;
        esac
        printf '{"status":"failed","code":"%s","reason":"%s","action":"%s","curl_exit":%s}' "$code" "$reason" "$action" "$curl_code"
        return
    fi
    case "$status" in
        200) printf '{"status":"ok","http_status":200}' ;;
        401|403) printf '{"status":"failed","code":"authorization_failed","http_status":%s,"action":"Check registration and revoked credentials; re-enroll using the installer"}' "$status" ;;
        503) printf '{"status":"failed","code":"backend_unavailable","http_status":503,"action":"Check server ready endpoint and PostgreSQL"}' ;;
        [1-5][0-9][0-9]) printf '{"status":"failed","code":"http_error","http_status":%s,"action":"Check server URL and reverse proxy"}' "$status" ;;
        *) printf '{"status":"failed","code":"transport_failed","reason":"No valid HTTP response","action":"Check network and server URL"}' ;;
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

write_public_diagnostic_files() {
    diagnostic_dir="$1"
    printf '{"agent_version":"%s","firmware":"%s","model":"%s"}\n' \
        "$(json_escape "$AGENT_VERSION")" \
        "$(json_escape "$(openwrt_firmware_description)")" \
        "$(json_escape "$(cat /tmp/sysinfo/model 2>/dev/null || printf unknown)")" \
        >"$diagnostic_dir/version.json"
    diagnostics_checks_json 'server,dns,wifi,dependencies' >"$diagnostic_dir/diagnostics.json"
    package_list_installed >"$diagnostic_dir/packages.txt" 2>/dev/null || true
    capabilities_json >"$diagnostic_dir/capabilities.json"
    printf '%s\n' 'Public diagnostic archive: raw configuration, addresses, hostnames, logs and process arguments are intentionally excluded.' >"$diagnostic_dir/README.txt"
}
