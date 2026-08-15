verify_uci_value() {
    verify_uci_key="$1"
    verify_uci_expected="$2"
    verify_uci_actual="$(uci -q get "$verify_uci_key" 2>/dev/null || true)"
    [ "$verify_uci_actual" = "$verify_uci_expected" ]
}

postcondition_mode_for_command() {
    case "$1" in
        diagnostics.run|maintenance.backup.create|maintenance.cron.read|maintenance.diagnostics.bundle|maintenance.logs.read|maintenance.packages.refresh|maintenance.processes.read|maintenance.services.read|network.interfaces|vpn.openvpn.export_client|vpn.wireguard.export_peer|wifi.status|wifi.get_qr)
            printf result_payload ;;
        agent.disconnect|agent.rollback|agent.update|maintenance.backup.restore|maintenance.sysupgrade.apply|network.interface_restart|network.restart|router.reboot)
            printf service_or_connectivity_state ;;
        agent.rotate_token|agent.set_auto_update|agent.set_interval)
            printf agent_state ;;
        dns.install_doh|dns.install_dot|maintenance.package.install|maintenance.package.remove|maintenance.package.upgrade)
            printf package_state ;;
        maintenance.service.set|system.restart_service)
            printf service_state ;;
        maintenance.module.configure)
            printf module_state ;;
        agent.bash_script|agent.ssh_session|maintenance.process.signal|maintenance.sysupgrade.check)
            printf handler_result ;;
        client.set_blocked|client.set_policy|dhcp.delete_lease|dhcp.set_lease|dhcp.set_pool|dns.set_doh|dns.set_dot|dns.set_servers|firewall.delete_forwarding|firewall.delete_port_forward|firewall.delete_redirect|firewall.delete_rule|firewall.delete_zone|firewall.set_forwarding|firewall.set_port_forward|firewall.set_redirect|firewall.set_rule|firewall.set_zone|maintenance.cron.set|maintenance.recovery.disable|maintenance.recovery.enable|network.delete_route|network.delete_segment|network.delete_vlan|network.set_ddns|network.set_ipv6|network.set_lan|network.set_multiwan|network.set_route|network.set_segment|network.set_upnp|network.set_vlan|network.set_wan|qos.set_sqm|system.set_hostname|system.set_ntp|system.set_timezone|vpn.openvpn.delete_client|vpn.openvpn.set_client|vpn.openvpn.set_enabled|vpn.policy.delete|vpn.policy.set|vpn.wireguard.delete_interface|vpn.wireguard.delete_peer|vpn.wireguard.set_interface|vpn.wireguard.set_peer|wifi.add_ssid|wifi.delete_ssid|wifi.set_channel|wifi.set_country|wifi.set_enabled|wifi.set_guest|wifi.set_mesh|wifi.set_password|wifi.set_radio|wifi.set_schedule|wifi.set_ssid|wifi.update_ssid)
            printf read_after_write_config ;;
        *) return 1 ;;
    esac
}
verify_uci_package() {
    uci -q export "$1" >/dev/null 2>&1 || uci -q show "$1" >/dev/null 2>&1
}

verify_config_integrity_for_command() {
    case "$1" in
        wifi.set_schedule|maintenance.recovery.*) verify_uci_package wrtmonitor ;;
        wifi.*) verify_uci_package wireless ;;
        dhcp.*) verify_uci_package dhcp ;;
        dns.set_servers) verify_uci_package dhcp ;;
        dns.set_dot) verify_uci_package unbound || verify_uci_package stubby ;;
        dns.set_doh) verify_uci_package https-dns-proxy ;;
        firewall.*|client.*) verify_uci_package firewall ;;
        qos.*) verify_uci_package sqm ;;
        system.*) verify_uci_package system ;;
        network.set_multiwan) verify_uci_package mwan3 ;;
        network.set_ddns) verify_uci_package ddns ;;
        network.set_upnp) verify_uci_package upnpd ;;
        network.*) verify_uci_package network ;;
        vpn.openvpn.*) verify_uci_package openvpn ;;
        vpn.policy.*) verify_uci_package pbr ;;
        vpn.wireguard.*) verify_uci_package network ;;
        maintenance.cron.set)
            [ -r "${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root" ] ;;
        *) return 1 ;;
    esac
}
