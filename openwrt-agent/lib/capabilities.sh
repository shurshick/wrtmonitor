CAPABILITIES_VERSION="3"

agent_capabilities_json() {
    printf '{"agent.status":true,"agent.update":true,"agent.set_interval":true,"agent.rollback":true,"agent.disable":true,"telemetry.system":true,"telemetry.hardware":true,"telemetry.network":true,"telemetry.wifi":true,"telemetry.clients":true,"telemetry.services":true,"wifi.read":true,"wifi.enable":true,"wifi.disable":true,"wifi.set_ssid":true,"wifi.set_password":true,"wifi.set_channel":true,"wifi.set_country":true,"wifi.guest":true,"network.read":true,"network.interface_restart":true,"network.restart":true,"network.write":true,"network.wan.configure":true,"network.lan.configure":true,"clients.read":true,"clients.block":true,"dhcp.set_lease":true,"dhcp.delete_lease":true,"dhcp.configure":true,"dns.configure":true,"firewall.port_forward":true,"system.reboot":true,"system.set_hostname":true,"system.restart_service":true,"system.set_timezone":true,"system.set_ntp":true,"diagnostics.check_server":true,"diagnostics.check_dependencies":true,"diagnostics.check_dns":true,"diagnostics.check_route":true,"diagnostics.check_wifi":true}'
}

capabilities_json() {
    printf '{"agent":{"version":"%s","platform":"openwrt","capabilities_version":%s},"capabilities":%s}' \
        "$(json_escape "$AGENT_VERSION")" \
        "$CAPABILITIES_VERSION" \
        "$(agent_capabilities_json)"
}
