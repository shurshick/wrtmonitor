CAPABILITIES_VERSION="1"

agent_capabilities_json() {
    printf '{"agent.status":true,"agent.update":true,"agent.set_interval":true,"agent.rollback":true,"agent.restart":true,"agent.support_bundle":true,"agent.disable":true,"telemetry.system":true,"telemetry.hardware":true,"telemetry.network":true,"telemetry.wifi":true,"wifi.read":true,"wifi.enable":true,"wifi.disable":true,"wifi.set_ssid":true,"wifi.set_password":true,"network.read":true,"network.restart":false,"network.write":false,"system.reboot":true,"diagnostics.check_server":true,"diagnostics.check_dependencies":true,"diagnostics.check_dns":true,"diagnostics.check_route":true,"diagnostics.check_wifi":true}'
}

capabilities_json() {
    printf '{"agent":{"version":"%s","platform":"openwrt","capabilities_version":%s},"capabilities":%s}' \
        "$(json_escape "$AGENT_VERSION")" \
        "$CAPABILITIES_VERSION" \
        "$(agent_capabilities_json)"
}
