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
