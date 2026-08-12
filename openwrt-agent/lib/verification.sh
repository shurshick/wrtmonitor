verify_uci_value() {
    verify_uci_key="$1"
    verify_uci_expected="$2"
    verify_uci_actual="$(uci -q get "$verify_uci_key" 2>/dev/null || true)"
    [ "$verify_uci_actual" = "$verify_uci_expected" ]
}

postcondition_mode_for_command() {
    case "$1" in
        diagnostics.run|maintenance.backup.create|maintenance.cron.read|maintenance.diagnostics.bundle|maintenance.logs.read|maintenance.packages.refresh|maintenance.processes.read|maintenance.services.read|network.interfaces|vpn.openvpn.export_client|vpn.wireguard.export_peer|wifi.status)
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

verify_package_postcondition() {
    command_type="$1"
    payload_file="$2"
    case "$command_type" in
        dns.install_dot) package=stubby ;;
        dns.install_doh) package=https-dns-proxy ;;
        *) package="$(json_get_string "$payload_file" '@.package')" ;;
    esac
    [ -n "$package" ] || return 1
    package_list_installed 2>/dev/null | grep -Eq "^${package}([|[:space:]]|$)" && installed=1 || installed=0
    if [ "$command_type" = maintenance.package.remove ]; then
        [ "$installed" = 0 ]
    elif [ "$command_type" = dns.install_dot ] || [ "$command_type" = dns.install_doh ]; then
        [ "$installed" = 1 ] && dns_resolution_works
    else
        [ "$installed" = 1 ]
    fi
}

verify_service_postcondition() {
    command_type="$1"
    payload_file="$2"
    if [ "$command_type" = system.restart_service ]; then
        service="$(json_get_string "$payload_file" '@.service')"
        action=restart
    else
        service="$(json_get_string "$payload_file" '@.service')"
        action="$(json_get_string "$payload_file" '@.action')"
    fi
    service_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service"
    [ -x "$service_path" ] || return 1
    case "$action" in
        start|restart) "$service_path" running >/dev/null 2>&1 ;;
        stop) ! "$service_path" running >/dev/null 2>&1 ;;
        enable) "$service_path" enabled >/dev/null 2>&1 ;;
        disable) ! "$service_path" enabled >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}

verify_module_postcondition() {
    payload_file="$1"
    module="$(json_get_string "$payload_file" '@.module')"
    action="$(json_get_string "$payload_file" '@.action')"
    package="$(module_primary_package "$module" 2>/dev/null || true)"
    [ -n "$package" ] || return 1
    case "$action" in
        install) module_package_installed "$package" ;;
        remove) ! module_package_installed "$package" ;;
        enable|disable)
            service="$(module_service "$module" 2>/dev/null || true)"
            [ -n "$service" ] || return 1
            service_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service"
            [ -x "$service_path" ] || return 1
            if [ "$action" = enable ]; then
                "$service_path" enabled >/dev/null 2>&1 && "$service_path" running >/dev/null 2>&1
            else
                ! "$service_path" enabled >/dev/null 2>&1 && ! "$service_path" running >/dev/null 2>&1
            fi
            ;;
        *) return 1 ;;
    esac
}

verify_client_policy_postcondition() {
    payload_file="$1"
    mac="$(json_get_string "$payload_file" '@.mac')"
    [ -n "$mac" ] || return 1
    blocked="$(json_get_bool "$payload_file" '@.blocked')"
    schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
    weekdays="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
    start="$(json_get_string "$payload_file" '@.schedule.start')"
    stop="$(json_get_string "$payload_file" '@.schedule.stop')"
    priority="$(json_get_string "$payload_file" '@.qos.priority')"
    download="$(json_get_number "$payload_file" '@.qos.download_kbps')"
    upload="$(json_get_number "$payload_file" '@.qos.upload_kbps')"
    dns="$(json_get_string "$payload_file" '@.dns.provider')"
    [ -n "$priority" ] || priority=normal
    [ -n "$download" ] || download=0
    [ -n "$upload" ] || upload=0
    [ -n "$dns" ] || dns=none
    suffix="$(client_policy_suffix "$mac")"
    policy_ref="wrtmonitor_policy_$suffix"
    qos_ref="wrtmonitor_qos_$suffix"
    dns_ref="wrtmonitor_dns_$suffix"
    dot_ref="wrtmonitor_dot_$suffix"
    state_ref="$(client_policy_section "$mac")"

    verify_uci_value "wrtmonitor.$state_ref.mac" "$mac" || return 1
    verify_uci_value "wrtmonitor.$state_ref.blocked" "$( [ "$blocked" = true ] && echo 1 || echo 0 )" || return 1
    verify_uci_value "wrtmonitor.$state_ref.schedule_enabled" "$( [ "$schedule_enabled" = true ] && echo 1 || echo 0 )" || return 1
    verify_uci_value "wrtmonitor.$state_ref.weekdays" "$weekdays" || return 1
    verify_uci_value "wrtmonitor.$state_ref.start" "$start" || return 1
    verify_uci_value "wrtmonitor.$state_ref.stop" "$stop" || return 1
    verify_uci_value "wrtmonitor.$state_ref.priority" "$priority" || return 1
    verify_uci_value "wrtmonitor.$state_ref.download_kbps" "$download" || return 1
    verify_uci_value "wrtmonitor.$state_ref.upload_kbps" "$upload" || return 1
    verify_uci_value "wrtmonitor.$state_ref.dns_provider" "$dns" || return 1

    if [ "$blocked" = true ] || [ "$schedule_enabled" = true ]; then
        verify_uci_value "firewall.$policy_ref.src_mac" "$mac" \
            && verify_uci_value "firewall.$policy_ref.target" REJECT || return 1
        if [ "$blocked" != true ] && [ "$schedule_enabled" = true ]; then
            [ -z "$weekdays" ] || verify_uci_value "firewall.$policy_ref.weekdays" "$weekdays" || return 1
            [ -z "$start" ] || verify_uci_value "firewall.$policy_ref.start_time" "$start" || return 1
            [ -z "$stop" ] || verify_uci_value "firewall.$policy_ref.stop_time" "$stop" || return 1
        fi
    else
        [ -z "$(uci -q get "firewall.$policy_ref" 2>/dev/null || true)" ] || return 1
    fi
    if [ "$priority" = normal ]; then
        [ -z "$(uci -q get "firewall.$qos_ref" 2>/dev/null || true)" ] || return 1
    else
        case "$priority" in low) mark=0x10 ;; high) mark=0x30 ;; realtime) mark=0x40 ;; *) return 1 ;; esac
        verify_uci_value "firewall.$qos_ref.src_mac" "$mac" \
            && verify_uci_value "firewall.$qos_ref.set_mark" "$mark" || return 1
    fi
    if [ "$dns" = none ]; then
        [ -z "$(uci -q get "firewall.$dns_ref" 2>/dev/null || true)" ] \
            && [ -z "$(uci -q get "firewall.$dot_ref" 2>/dev/null || true)" ] || return 1
    else
        case "$dns" in cloudflare-security) expected_dns=1.1.1.2 ;; cloudflare-family) expected_dns=1.1.1.3 ;; *) return 1 ;; esac
        verify_uci_value "firewall.$dns_ref.dest_ip" "$expected_dns" \
            && verify_uci_value "firewall.$dot_ref.dest_port" 853 || return 1
    fi
    device="$(uci -q get "wrtmonitor.$state_ref.shaping_device" 2>/dev/null || true)"
    pref="$(uci -q get "wrtmonitor.$state_ref.shaping_pref" 2>/dev/null || true)"
    if [ "$upload" -gt 0 ]; then client_policy_filter_matches "$device" ingress "$pref" "$mac" "$upload" || return 1; fi
    if [ "$download" -gt 0 ]; then client_policy_filter_matches "$device" egress "$pref" "$mac" "$download" || return 1; fi
}

verify_command_postcondition() {
    command_type="$1"
    command_payload="$2"
    payload_file="/tmp/wrtmonitor-verify-payload-$$"
    printf '%s' "$command_payload" >"$payload_file"
    mode="$(postcondition_mode_for_command "$command_type" || true)"
    [ -n "$mode" ] || { rm -f "$payload_file"; return 1; }
    case "$mode" in
        result_payload|handler_result|service_or_connectivity_state)
            rm -f "$payload_file"
            return 0
            ;;
        package_state)
            verify_package_postcondition "$command_type" "$payload_file"
            verification_status=$?
            rm -f "$payload_file"
            return "$verification_status"
            ;;
        service_state)
            verify_service_postcondition "$command_type" "$payload_file"
            verification_status=$?
            rm -f "$payload_file"
            return "$verification_status"
            ;;
        module_state)
            verify_module_postcondition "$payload_file"
            verification_status=$?
            rm -f "$payload_file"
            return "$verification_status"
            ;;
    esac
    verified=0
    case "$command_type" in
        client.set_policy)
            verify_client_policy_postcondition "$payload_file" || verified=1
            ;;
        client.set_blocked)
            mac="$(json_get_string "$payload_file" '@.mac')"
            blocked="$(json_get_bool "$payload_file" '@.blocked')"
            ref="wrtmonitor_block_$(printf '%s' "$mac" | tr -d ':')"
            if [ "$blocked" = true ]; then
                verify_uci_value "firewall.$ref.src_mac" "$mac" \
                    && verify_uci_value "firewall.$ref.target" REJECT || verified=1
            else
                [ -z "$(uci -q get "firewall.$ref" 2>/dev/null || true)" ] || verified=1
            fi
            ;;
        dhcp.set_lease)
            mac="$(json_get_string "$payload_file" '@.mac')"
            expected_ip="$(json_get_string "$payload_file" '@.ip')"
            expected_name="$(json_get_string "$payload_file" '@.hostname')"
            lease_ref="$(resolve_dhcp_host_by_mac "$mac" || true)"
            [ -n "$lease_ref" ] \
                && verify_uci_value "dhcp.$lease_ref.mac" "$mac" \
                && verify_uci_value "dhcp.$lease_ref.ip" "$expected_ip" \
                && verify_uci_value "dhcp.$lease_ref.name" "$expected_name" \
                || verified=1
            ;;
        dhcp.delete_lease)
            mac="$(json_get_string "$payload_file" '@.mac')"
            [ -z "$(resolve_dhcp_host_by_mac "$mac" || true)" ] || verified=1
            ;;
        agent.set_interval)
            expected="$(json_get_number "$payload_file" '@.interval_seconds')"
            verify_uci_value "$CONFIG.interval" "$expected" || verified=1
            ;;
        agent.rotate_token)
            [ -n "$(device_token)" ] || verified=1
            ;;
        agent.set_auto_update)
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            expected=0
            [ "$enabled" = true ] && expected=1
            verify_uci_value "$CONFIG.auto_update" "$expected" || verified=1
            ;;
        system.set_hostname)
            expected="$(json_get_string "$payload_file" '@.hostname')"
            verify_uci_value 'system.@system[0].hostname' "$expected" || verified=1
            ;;
        system.set_timezone)
            expected="$(json_get_string "$payload_file" '@.timezone')"
            verify_uci_value 'system.@system[0].timezone' "$expected" || verified=1
            ;;
        wifi.set_enabled)
            radio="$(json_get_string "$payload_file" '@.radio')"
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            radio="$(resolve_wifi_radio "$radio" || true)"
            expected=1
            [ "$enabled" = true ] && expected=0
            [ -n "$radio" ] && verify_uci_value "wireless.$radio.disabled" "$expected" || verified=1
            ;;
        wifi.set_ssid)
            iface="$(json_get_string "$payload_file" '@.iface')"
            expected="$(json_get_string "$payload_file" '@.ssid')"
            iface="$(resolve_wifi_iface "$iface" "" || true)"
            [ -n "$iface" ] && verify_uci_value "wireless.$iface.ssid" "$expected" || verified=1
            ;;
        wifi.set_channel)
            radio="$(json_get_string "$payload_file" '@.radio')"
            expected="$(json_get_string "$payload_file" '@.channel')"
            radio="$(resolve_wifi_radio "$radio" || true)"
            [ -n "$radio" ] && verify_uci_value "wireless.$radio.channel" "$expected" || verified=1
            ;;
        wifi.set_country)
            radio="$(json_get_string "$payload_file" '@.radio')"
            expected="$(json_get_string "$payload_file" '@.country')"
            radio="$(resolve_wifi_radio "$radio" || true)"
            [ -n "$radio" ] && verify_uci_value "wireless.$radio.country" "$expected" || verified=1
            ;;
        network.set_wan)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface=wan
            protocol="$(json_get_string "$payload_file" '@.protocol')"
            [ -n "$protocol" ] && verify_uci_value "network.$interface.proto" "$protocol" || verified=1
            if [ "$verified" = 0 ] && [ "$protocol" = static ]; then
                expected="$(json_get_string "$payload_file" '@.ip_address')"
                verify_uci_value "network.$interface.ipaddr" "$expected" || verified=1
            fi
            ;;
        network.set_lan)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface=lan
            expected="$(json_get_string "$payload_file" '@.ip_address')"
            netmask="$(json_get_string "$payload_file" '@.netmask')"
            actual="$(uci -q get "network.$interface.ipaddr" 2>/dev/null || true)"
            actual_ip="${actual%%/*}"
            actual_prefix=""
            case "$actual" in
                */*) actual_prefix="${actual#*/}" ;;
                *) actual_prefix="$(ipv4_netmask_prefix "$(uci -q get "network.$interface.netmask" 2>/dev/null || true)" 2>/dev/null || true)" ;;
            esac
            expected_prefix="$(ipv4_netmask_prefix "$netmask" 2>/dev/null || true)"
            verify_uci_value "network.$interface.proto" static && \
                [ "$actual_ip" = "$expected" ] && \
                [ -n "$expected_prefix" ] && \
                [ "$actual_prefix" = "$expected_prefix" ] || verified=1
            ;;
        dhcp.set_pool)
            interface="$(json_get_string "$payload_file" '@.interface')"
            [ -n "$interface" ] || interface=lan
            start="$(json_get_number "$payload_file" '@.start')"
            limit="$(json_get_number "$payload_file" '@.limit')"
            lease="$(json_get_string "$payload_file" '@.leasetime')"
            verify_uci_value "dhcp.$interface.start" "$start" && \
                verify_uci_value "dhcp.$interface.limit" "$limit" && \
                verify_uci_value "dhcp.$interface.leasetime" "$lease" || verified=1
            ;;
        dns.set_servers)
            expected="$(jsonfilter -i "$payload_file" -e '@.servers[*]' 2>/dev/null | sed '/^$/d' | sort)"
            actual="$(uci -q get 'dhcp.@dnsmasq[0].server' 2>/dev/null | tr ' ' '\n' | sed '/^$/d' | sort)"
            [ -n "$expected" ] && [ "$actual" = "$expected" ] || verified=1
            ;;
        network.set_ipv6)
            interface="$(json_get_string "$payload_file" '@.interface')"
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            if [ "$enabled" = true ]; then
                assignment="$(json_get_number "$payload_file" '@.assignment_length')"
                verify_uci_value "network.$interface.ip6assign" "$assignment" || verified=1
            else
                [ -z "$(uci -q get "network.$interface.ip6assign" 2>/dev/null || true)" ] || verified=1
            fi
            ;;
        network.set_vlan)
            section="$(json_get_string "$payload_file" '@.section')"
            device="$(json_get_string "$payload_file" '@.device')"
            vlan_id="$(json_get_number "$payload_file" '@.vlan_id')"
            if [ -z "$section" ]; then
                vlan_key="$(printf '%s' "$device" | tr -c 'A-Za-z0-9_' '_')"
                section="wrtmonitor_vlan_${vlan_key}_$vlan_id"
            fi
            verify_uci_value "network.$section.device" "$device" && \
                verify_uci_value "network.$section.vlan" "$vlan_id" || verified=1
            ;;
        network.set_multiwan)
            enabled="$(json_get_bool "$payload_file" '@.enabled')"
            primary="$(json_get_string "$payload_file" '@.primary_interface')"
            secondary="$(json_get_string "$payload_file" '@.secondary_interface')"
            expected_enabled=0
            [ "$enabled" = true ] && expected_enabled=1
            verify_uci_value mwan3.globals.enabled "$expected_enabled" && \
                verify_uci_value mwan3.wrtmonitor_primary.interface "$primary" && \
                verify_uci_value mwan3.wrtmonitor_secondary.interface "$secondary" && \
                verify_uci_value mwan3.wrtmonitor_default.use_policy wrtmonitor_policy || verified=1
            ;;
        *)
            verify_config_integrity_for_command "$command_type" || verified=1
            ;;
    esac
    rm -f "$payload_file"
    [ "$verified" = 0 ]
}
