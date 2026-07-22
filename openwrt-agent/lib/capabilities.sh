CAPABILITIES_VERSION="13"

capability_path() {
    printf '%s%s' "${WRTMONITOR_SYSTEM_ROOT:-}" "$1"
}

capability_keys() {
    printf '%s\n' \
        agent.status agent.update agent.set_interval agent.rollback agent.disable config.transaction \
        telemetry.system telemetry.hardware telemetry.network telemetry.wifi telemetry.wifi.stations telemetry.clients telemetry.clients.traffic telemetry.services \
        wifi.read wifi.enable wifi.disable wifi.set_ssid wifi.set_password wifi.set_channel wifi.set_country wifi.guest \
        wifi.radio.configure wifi.manage_ssid wifi.schedule wifi.roaming wifi.mesh \
        network.read network.interface_restart network.restart network.write network.wan.configure network.lan.configure \
        network.ipv6.configure network.multiwan.configure network.routes.configure network.ddns.configure \
        firewall.zones.configure firewall.rules.configure firewall.upnp.configure telemetry.perimeter \
        vpn.wireguard.read vpn.wireguard.configure vpn.openvpn.read vpn.openvpn.configure vpn.policy.read vpn.policy.configure telemetry.vpn \
        maintenance.packages.read maintenance.packages.write maintenance.backup maintenance.sysupgrade.check maintenance.sysupgrade.apply \
        maintenance.logs maintenance.processes maintenance.cron maintenance.diagnostics.bundle maintenance.recovery telemetry.maintenance \
        clients.read clients.block clients.policy qos.sqm dhcp.set_lease dhcp.delete_lease dhcp.configure dns.configure firewall.port_forward \
        system.reboot system.set_hostname system.restart_service system.set_timezone system.set_ntp \
        diagnostics.check_server diagnostics.check_dependencies diagnostics.check_dns diagnostics.check_route diagnostics.check_wifi
}

has_commands() {
    for CAP_COMMAND in "$@"; do
        command -v "$CAP_COMMAND" >/dev/null 2>&1 || return 1
    done
}

package_manager_name() {
    if command -v apk >/dev/null 2>&1; then
        printf 'apk'
    elif command -v opkg >/dev/null 2>&1; then
        printf 'opkg'
    else
        return 1
    fi
}

package_refresh_indexes() {
    case "$(package_manager_name)" in
        apk) apk update ;;
        opkg) opkg update ;;
    esac
}

package_apply() {
    action="$1"
    package="$2"
    case "$(package_manager_name)" in
        apk)
            if [ "$action" = install ]; then apk add "$package"; else apk del "$package"; fi
            ;;
        opkg) opkg "$action" "$package" ;;
    esac
}

package_list_installed() {
    case "$(package_manager_name)" in
        apk) apk list --installed --manifest 2>/dev/null | awk 'NF >= 2 {print $1 "|" $2}' ;;
        opkg) opkg list-installed 2>/dev/null | awk 'NF >= 3 {print $1 "|" $3}' ;;
    esac
}

package_list_upgradeable() {
    case "$(package_manager_name)" in
        apk)
            {
                apk list --installed --manifest 2>/dev/null | awk 'NF >= 2 {print "I|" $1 "|" $2}'
                apk list --upgradeable --manifest 2>/dev/null | awk 'NF >= 2 {print "U|" $1 "|" $2}'
            } | awk -F'|' '$1 == "I" {current[$2] = $3; next} $1 == "U" {print $2 "|" current[$2] "|" $3}'
            ;;
        opkg) opkg list-upgradable 2>/dev/null | awk 'NF >= 5 {print $1 "|" $3 "|" $5}' ;;
    esac
}

has_uci_config() {
    has_commands uci || return 1
    uci -q show "$1" >/dev/null 2>&1
}

has_wifi_radio() {
    has_uci_config wireless || return 1
    uci -q get 'wireless.@wifi-device[0]' >/dev/null 2>&1
}

has_wifi_iface() {
    has_wifi_radio || return 1
    uci -q get 'wireless.@wifi-iface[0]' >/dev/null 2>&1
}

has_wifi_stations() {
    has_commands ubus jsonfilter || return 1
    [ -n "$(ubus list 'hostapd.*' 2>/dev/null | head -n 1)" ]
}

has_client_traffic() {
    has_commands nlbw || return 1
    nlbw -c json -g mac -n >/dev/null 2>&1
}

has_wifi_roaming() {
    has_wifi_iface || return 1
    package_list_installed 2>/dev/null \
        | cut -d'|' -f1 \
        | grep -Eq '^(wpad|hostapd)(-(basic-)?(mbedtls|openssl|wolfssl))?$'
}

has_wifi_mesh() {
    has_wifi_iface && has_commands iw && iw list 2>/dev/null | grep -qi 'mesh point'
}

has_network_runtime() {
    has_commands ubus jsonfilter || return 1
    ubus list network.interface >/dev/null 2>&1
}

has_network_write() {
    has_uci_config network && [ -x "$(capability_path /etc/init.d/network)" ]
}

has_dhcp_write() {
    has_uci_config dhcp && [ -x "$(capability_path /etc/init.d/dnsmasq)" ]
}

has_firewall_write() {
    has_uci_config firewall && [ -x "$(capability_path /etc/init.d/firewall)" ]
}

has_system_write() {
    has_uci_config system
}

has_config_transactions() {
    has_commands uci curl cp df sed awk && [ -d "$(capability_path /etc/config)" ]
}

capability_supported() {
    case "$1" in
        agent.status) return 0 ;;
        agent.update) has_commands curl sha256sum cp mv ;;
        agent.set_interval) has_uci_config wrtmonitor ;;
        agent.rollback) has_commands cp mv && [ -x "$(capability_path /etc/init.d/wrtmonitor)" ] ;;
        agent.disable) has_uci_config wrtmonitor && [ -x "$(capability_path /etc/init.d/wrtmonitor)" ] ;;
        config.transaction) has_config_transactions ;;
        telemetry.system) [ -r "$(capability_path /proc/uptime)" ] && [ -r "$(capability_path /proc/loadavg)" ] ;;
        telemetry.hardware) [ -r "$(capability_path /proc/cpuinfo)" ] && has_commands df ;;
        telemetry.network|network.read) has_network_runtime ;;
        telemetry.wifi|wifi.read) has_wifi_radio ;;
        telemetry.wifi.stations) has_wifi_stations ;;
        telemetry.clients|clients.read) has_commands ip || [ -r "$(capability_path /tmp/dhcp.leases)" ] ;;
        telemetry.clients.traffic) has_client_traffic ;;
        telemetry.services) [ -d "$(capability_path /etc/init.d)" ] ;;
        wifi.enable|wifi.disable|wifi.set_channel|wifi.set_country) has_wifi_radio && has_commands wifi ;;
        wifi.set_ssid|wifi.set_password) has_wifi_iface && has_commands wifi ;;
        wifi.guest) has_wifi_iface && has_network_write && has_dhcp_write && has_firewall_write && has_commands wifi ;;
        wifi.radio.configure|wifi.manage_ssid|wifi.schedule) has_wifi_radio && has_commands wifi uci ;;
        wifi.roaming) has_wifi_roaming && has_commands wifi ;;
        wifi.mesh) has_wifi_mesh && has_commands wifi ;;
        network.interface_restart) has_network_runtime && has_commands ifup ifdown ;;
        network.restart) [ -x "$(capability_path /etc/init.d/network)" ] ;;
        network.write|network.wan.configure|network.lan.configure) has_network_write && has_commands ifup ifdown ;;
        network.ipv6.configure|network.routes.configure) has_network_write && has_dhcp_write ;;
        network.multiwan.configure) has_uci_config mwan3 && [ -x "$(capability_path /etc/init.d/mwan3)" ] ;;
        network.ddns.configure) has_uci_config ddns && [ -x "$(capability_path /etc/init.d/ddns)" ] ;;
        firewall.zones.configure|firewall.rules.configure) has_firewall_write ;;
        firewall.upnp.configure) has_uci_config upnpd && [ -x "$(capability_path /etc/init.d/miniupnpd)" ] ;;
        telemetry.perimeter) has_uci_config firewall && has_network_runtime ;;
        vpn.wireguard.read) has_commands wg ubus jsonfilter ;;
        vpn.wireguard.configure) has_network_write && has_commands wg ifup ifdown ;;
        vpn.openvpn.read) has_uci_config openvpn && [ -x "$(capability_path /etc/init.d/openvpn)" ] ;;
        vpn.openvpn.configure) has_uci_config openvpn && [ -x "$(capability_path /etc/init.d/openvpn)" ] && has_commands openvpn base64 ;;
        vpn.policy.read|vpn.policy.configure) has_uci_config pbr && [ -x "$(capability_path /etc/init.d/pbr)" ] ;;
        telemetry.vpn) capability_supported vpn.wireguard.read || capability_supported vpn.openvpn.read || capability_supported vpn.policy.read ;;
        maintenance.packages.read|maintenance.packages.write) package_manager_name >/dev/null 2>&1 ;;
        maintenance.backup) has_commands sysupgrade tar base64 ;;
        maintenance.sysupgrade.check) has_commands sysupgrade curl sha256sum df ;;
        maintenance.sysupgrade.apply) has_commands sysupgrade sha256sum ;;
        maintenance.logs) has_commands logread ;;
        maintenance.processes) has_commands ps kill ;;
        maintenance.cron) [ -d "$(capability_path /etc/crontabs)" ] && [ -x "$(capability_path /etc/init.d/cron)" ] ;;
        maintenance.diagnostics.bundle) has_commands tar gzip base64 ubus logread ps df ;;
        maintenance.recovery) has_uci_config wrtmonitor ;;
        telemetry.maintenance) capability_supported maintenance.packages.read || capability_supported maintenance.recovery ;;
        clients.block|clients.policy|firewall.port_forward) has_firewall_write ;;
        qos.sqm) has_uci_config sqm && [ -x "$(capability_path /etc/init.d/sqm)" ] ;;
        dhcp.set_lease|dhcp.delete_lease|dhcp.configure|dns.configure) has_dhcp_write ;;
        system.reboot) has_commands reboot ;;
        system.set_hostname|system.set_timezone) has_system_write ;;
        system.restart_service) [ -d "$(capability_path /etc/init.d)" ] ;;
        system.set_ntp) has_system_write && [ -x "$(capability_path /etc/init.d/sysntpd)" ] ;;
        diagnostics.check_server) has_commands curl ;;
        diagnostics.check_dependencies) return 0 ;;
        diagnostics.check_dns) has_commands nslookup ;;
        diagnostics.check_route) has_commands ip ;;
        diagnostics.check_wifi) has_commands wifi && has_wifi_radio ;;
        *) return 1 ;;
    esac
}

capability_unavailable_reason() {
    case "$1" in
        agent.update) printf 'curl, sha256sum or file tools are unavailable' ;;
        agent.set_interval|agent.disable) printf 'wrtmonitor UCI configuration is unavailable' ;;
        agent.rollback) printf 'agent init service or file tools are unavailable' ;;
        config.transaction) printf 'UCI configuration, connectivity or backup tools are unavailable' ;;
        telemetry.system) printf 'required procfs metrics are unavailable' ;;
        telemetry.hardware) printf 'hardware metrics or df are unavailable' ;;
        telemetry.network|network.read) printf 'ubus network runtime or jsonfilter is unavailable' ;;
        telemetry.wifi|wifi.*|diagnostics.check_wifi) printf 'wireless configuration, required radio features or wifi utility is unavailable' ;;
        telemetry.wifi.stations) printf 'hostapd ubus client telemetry is unavailable' ;;
        telemetry.clients|clients.read) printf 'neighbour and DHCP lease sources are unavailable' ;;
        telemetry.clients.traffic) printf 'nlbwmon is not installed or its client is unavailable' ;;
        telemetry.services|system.restart_service) printf 'OpenWrt init services are unavailable' ;;
        network.interface_restart) printf 'ubus network runtime, ifup or ifdown is unavailable' ;;
        network.*) printf 'network UCI configuration or init service is unavailable' ;;
        vpn.wireguard.*|telemetry.vpn) printf 'wireguard-tools or network support is unavailable' ;;
        vpn.openvpn.*) printf 'openvpn-openssl package or OpenVPN service is unavailable' ;;
        vpn.policy.*) printf 'pbr package or service is unavailable' ;;
        maintenance.packages.*) printf 'apk and opkg are unavailable' ;;
        maintenance.backup) printf 'sysupgrade, tar or base64 is unavailable' ;;
        maintenance.sysupgrade.*) printf 'sysupgrade verification tools are unavailable' ;;
        maintenance.logs) printf 'logread is unavailable' ;;
        maintenance.processes) printf 'process tools are unavailable' ;;
        maintenance.cron) printf 'cron service or crontab storage is unavailable' ;;
        maintenance.diagnostics.bundle) printf 'diagnostic archive tools are unavailable' ;;
        maintenance.recovery|telemetry.maintenance) printf 'maintenance runtime is unavailable' ;;
        clients.block|clients.policy|firewall.port_forward) printf 'firewall UCI configuration or service is unavailable' ;;
        qos.sqm) printf 'sqm-scripts package or SQM init service is unavailable' ;;
        dhcp.*|dns.configure) printf 'DHCP configuration or dnsmasq service is unavailable' ;;
        system.reboot) printf 'reboot utility is unavailable' ;;
        system.set_hostname|system.set_timezone) printf 'system UCI configuration is unavailable' ;;
        system.set_ntp) printf 'system UCI configuration or sysntpd is unavailable' ;;
        diagnostics.check_server) printf 'curl is unavailable' ;;
        diagnostics.check_dns) printf 'nslookup is unavailable' ;;
        diagnostics.check_route) printf 'ip utility is unavailable' ;;
        *) printf 'capability requirements are unavailable' ;;
    esac
}

agent_capabilities_json() {
    CAP_OUTPUT=""
    for CAP_KEY in $(capability_keys); do
        CAP_VALUE=false
        capability_supported "$CAP_KEY" && CAP_VALUE=true
        [ -n "$CAP_OUTPUT" ] && CAP_OUTPUT="$CAP_OUTPUT,"
        CAP_OUTPUT="$CAP_OUTPUT\"$CAP_KEY\":$CAP_VALUE"
    done
    printf '{%s}' "$CAP_OUTPUT"
}

agent_capability_details_json() {
    CAP_OUTPUT=""
    for CAP_KEY in $(capability_keys); do
        CAP_VALUE=false
        CAP_REASON="$(capability_unavailable_reason "$CAP_KEY")"
        if capability_supported "$CAP_KEY"; then
            CAP_VALUE=true
            CAP_REASON="available"
        fi
        [ -n "$CAP_OUTPUT" ] && CAP_OUTPUT="$CAP_OUTPUT,"
        CAP_OUTPUT="$CAP_OUTPUT\"$CAP_KEY\":{\"supported\":$CAP_VALUE,\"reason\":\"$(json_escape "$CAP_REASON")\"}"
    done
    printf '{%s}' "$CAP_OUTPUT"
}

capabilities_json() {
    printf '{"agent":{"version":"%s","platform":"openwrt","capabilities_version":%s},"capabilities":%s,"capability_details":%s}' \
        "$(json_escape "$AGENT_VERSION")" \
        "$CAPABILITIES_VERSION" \
        "$(agent_capabilities_json)" \
        "$(agent_capability_details_json)"
}
