encrypted_dns_provider() {
    mode="$1"
    provider="$2"
    case "$mode:$provider" in
        dot:cloudflare) printf '%s|%s|%s' '1.1.1.1 1.0.0.1' 'cloudflare-dns.com' '' ;;
        dot:quad9) printf '%s|%s|%s' '9.9.9.9 149.112.112.112' 'dns.quad9.net' '' ;;
        dot:google) printf '%s|%s|%s' '8.8.8.8 8.8.4.4' 'dns.google' '' ;;
        *) return 1 ;;
    esac
}

backup_plain_dns() {
    if [ -z "$(uci -q get wrtmonitor.main.dns_backup_present 2>/dev/null || true)" ]; then
        uci set wrtmonitor.main.dns_backup_present=1
        current_noresolv="$(uci -q get 'dhcp.@dnsmasq[0].noresolv' 2>/dev/null || printf unset)"
        uci set "wrtmonitor.main.dns_backup_noresolv=$current_noresolv"
        uci -q delete wrtmonitor.main.dns_backup_servers || true
        for server in $(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null || true); do
            uci add_list "wrtmonitor.main.dns_backup_servers=$server"
        done
        uci commit wrtmonitor
    fi
}

restore_plain_dns() {
    if [ "$(uci -q get wrtmonitor.main.dns_backup_present 2>/dev/null || true)" != 1 ]; then
        restore_package_dns_backup
        return
    fi
    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    for server in $(uci -q get wrtmonitor.main.dns_backup_servers 2>/dev/null || true); do
        uci add_list "dhcp.@dnsmasq[0].server=$server"
    done
    old_noresolv="$(uci -q get wrtmonitor.main.dns_backup_noresolv 2>/dev/null || printf unset)"
    if [ "$old_noresolv" = unset ]; then uci -q delete 'dhcp.@dnsmasq[0].noresolv' || true; else uci set "dhcp.@dnsmasq[0].noresolv=$old_noresolv"; fi
    uci -q delete 'dhcp.@dnsmasq[0].doh_backup_noresolv' || true
    uci -q delete 'dhcp.@dnsmasq[0].doh_backup_server' || true
    uci -q delete 'dhcp.@dnsmasq[0].doh_server' || true
    uci -q delete wrtmonitor.main.dns_backup_present || true
    uci -q delete wrtmonitor.main.dns_backup_noresolv || true
    uci -q delete wrtmonitor.main.dns_backup_servers || true
    uci commit wrtmonitor
    uci commit dhcp
}

restore_package_dns_backup() {
    package_noresolv="$(uci -q get 'dhcp.@dnsmasq[0].doh_backup_noresolv' 2>/dev/null || printf unset)"
    package_servers="$(uci -q get 'dhcp.@dnsmasq[0].doh_backup_server' 2>/dev/null || true)"
    current_servers="$(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null || true)"
    encrypted_server_found=0
    for server in $current_servers; do
        case "$server" in
            127.0.0.1#5053|127.0.0.1#5054|127.0.0.1#5453) encrypted_server_found=1 ;;
        esac
    done
    [ "$package_noresolv" != unset ] || [ -n "$package_servers" ] || [ "$encrypted_server_found" = 1 ] || return 0

    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    for server in $package_servers; do
        case "$server" in
            127.0.0.1#5053|127.0.0.1#5054|127.0.0.1#5453) continue ;;
        esac
        uci add_list "dhcp.@dnsmasq[0].server=$server"
    done
    case "$package_noresolv" in
        unset|-1) uci -q delete 'dhcp.@dnsmasq[0].noresolv' || true ;;
        *) uci set "dhcp.@dnsmasq[0].noresolv=$package_noresolv" ;;
    esac
    uci -q delete 'dhcp.@dnsmasq[0].doh_backup_noresolv' || true
    uci -q delete 'dhcp.@dnsmasq[0].doh_backup_server' || true
    uci -q delete 'dhcp.@dnsmasq[0].doh_server' || true
    uci commit dhcp
}

dns_resolution_works() {
    nslookup openwrt.org 127.0.0.1 >/dev/null 2>&1
}

remove_dnsmasq_server() {
    target="$1"
    for server in $(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null || true); do
        [ "$server" != "$target" ] || uci -q del_list "dhcp.@dnsmasq[0].server=$target" || true
    done
}

configure_dot() {
    provider="$1"
    enabled="$2"
    [ -x /etc/init.d/stubby ] || return 1
    if [ "$enabled" != true ]; then
        service_action stubby stop 20 >/dev/null 2>&1 || true
        service_action stubby disable 20 >/dev/null 2>&1 || true
        restore_plain_dns
        service_action dnsmasq restart 20 >/dev/null 2>&1 && dns_resolution_works
        return $?
    fi
    provider_data="$(encrypted_dns_provider dot "$provider")" || return 1
    addresses="${provider_data%%|*}"
    auth_name="${provider_data#*|}"; auth_name="${auth_name%%|*}"
    while uci -q get 'stubby.@resolver[0]' >/dev/null 2>&1; do uci -q delete 'stubby.@resolver[0]'; done
    uci set stubby.global=stubby
    uci set stubby.global.manual=0
    uci set stubby.global.trigger=wan
    uci -q delete stubby.global.dns_transport || true
    uci add_list stubby.global.dns_transport=GETDNS_TRANSPORT_TLS
    uci set stubby.global.tls_authentication=1
    uci -q delete stubby.global.listen_address || true
    uci add_list stubby.global.listen_address='127.0.0.1@5453'
    for address in $addresses; do
        resolver="$(uci add stubby resolver)"
        uci set "stubby.$resolver.address=$address"
        uci set "stubby.$resolver.tls_auth_name=$auth_name"
        uci set "stubby.$resolver.tls_port=853"
    done
    backup_plain_dns
    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    uci add_list 'dhcp.@dnsmasq[0].server=127.0.0.1#5453'
    uci set 'dhcp.@dnsmasq[0].noresolv=1'
    uci commit stubby && uci commit dhcp
    [ ! -x /etc/init.d/https-dns-proxy ] || { service_action https-dns-proxy stop 20 >/dev/null 2>&1 || true; service_action https-dns-proxy disable 20 >/dev/null 2>&1 || true; }
    /etc/init.d/stubby enable >/dev/null 2>&1
    service_action stubby restart 20 >/dev/null 2>&1
    service_action dnsmasq restart 20 >/dev/null 2>&1 && dns_resolution_works
}

configure_doh() {
    provider="$1"
    enabled="$2"
    [ -x /etc/init.d/https-dns-proxy ] || return 1
    if [ "$enabled" != true ]; then
        service_action https-dns-proxy stop 20 >/dev/null 2>&1 || true
        service_action https-dns-proxy disable 20 >/dev/null 2>&1 || true
        restore_plain_dns
        service_action dnsmasq restart 20 >/dev/null 2>&1 && dns_resolution_works
        return $?
    fi
    case "$provider" in
        cloudflare) resolver_url='https://cloudflare-dns.com/dns-query'; bootstrap_dns='1.1.1.1,1.0.0.1' ;;
        quad9) resolver_url='https://dns.quad9.net/dns-query'; bootstrap_dns='9.9.9.9,149.112.112.112' ;;
        google) resolver_url='https://dns.google/dns-query'; bootstrap_dns='8.8.8.8,8.8.4.4' ;;
        *) return 1 ;;
    esac
    [ ! -x /etc/init.d/stubby ] || {
        service_action stubby stop 20 >/dev/null 2>&1 || true
        service_action stubby disable 20 >/dev/null 2>&1 || true
        restore_plain_dns
    }
    backup_plain_dns
    while uci -q get 'https-dns-proxy.@https-dns-proxy[0]' >/dev/null 2>&1; do uci -q delete 'https-dns-proxy.@https-dns-proxy[0]'; done
    section="$(uci add https-dns-proxy https-dns-proxy)"
    uci set "https-dns-proxy.$section.resolver_url=$resolver_url"
    uci set "https-dns-proxy.$section.bootstrap_dns=$bootstrap_dns"
    uci set "https-dns-proxy.$section.listen_port=5053"
    uci -q delete 'dhcp.@dnsmasq[0].server' || true
    uci add_list 'dhcp.@dnsmasq[0].server=127.0.0.1#5053'
    uci set 'dhcp.@dnsmasq[0].noresolv=1'
    uci commit https-dns-proxy && uci commit dhcp
    /etc/init.d/https-dns-proxy enable >/dev/null 2>&1
    service_action https-dns-proxy restart 20 >/dev/null 2>&1
    service_action dnsmasq restart 20 >/dev/null 2>&1 && dns_resolution_works
}
