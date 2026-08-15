# shellcheck disable=SC2034,SC2154
handle_network_command() {
    handle_network_core_command && return 0
    handle_network_topology_command && return 0
    handle_network_services_command && return 0
    handle_network_policy_command && return 0
    return 1
}
