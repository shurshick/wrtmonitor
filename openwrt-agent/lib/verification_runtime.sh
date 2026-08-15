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
