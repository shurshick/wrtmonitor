module_packages() {
    case "$1" in
        storage) printf '%s\n' block-mount kmod-usb-storage e2fsprogs usbutils ;;
        smb) printf '%s\n' samba4-server ;;
        nfs) printf '%s\n' nfs-kernel-server ;;
        ftp) printf '%s\n' vsftpd ;;
        dlna) printf '%s\n' minidlna ;;
        printer) printf '%s\n' p910nd kmod-usb-printer ;;
        modem) printf '%s\n' umbim uqmi comgt kmod-usb-net ;;
        *) return 1 ;;
    esac
}

module_set_service_state() {
    module="$1"
    action="$2"
    service="$(module_service "$module" 2>/dev/null || true)"
    [ -n "$service" ] || return 0
    service_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service"
    [ -x "$service_path" ] || return 1
    case "$action" in
        install|enable) "$service_path" enable >/dev/null 2>&1 && "$service_path" restart >/dev/null 2>&1 ;;
        disable) "$service_path" stop >/dev/null 2>&1 || true; "$service_path" disable >/dev/null 2>&1 ;;
        *) return 0 ;;
    esac
}

handle_module_command() {
    case "$command_type" in
        maintenance.module.configure)
            ;;
        *) return 1 ;;
    esac
    payload_file=/tmp/wrtmonitor-command-payload
    printf '%s' "$command_payload" >"$payload_file"
    module="$(json_get_string "$payload_file" '@.module')"
    action="$(json_get_string "$payload_file" '@.action')"
    rm -f "$payload_file"
    packages="$(module_packages "$module" 2>/dev/null || true)"
    if [ -z "$packages" ]; then
        status=failed
        result="$(command_failed_result "unsupported OpenWrt module")"
        return 0
    fi
    case "$action" in
        install) :
            if ! package_refresh_indexes >/dev/null 2>&1; then
                status=failed; result="$(command_failed_result "package index update failed")"; return 0
            fi
            while IFS= read -r package; do
                [ -n "$package" ] || continue
                if ! module_package_installed "$package" && ! package_apply install "$package" >/dev/null 2>&1; then
                    status=failed; result="$(command_failed_result "failed to install module dependency: $package")"; return 0
                fi
            done <<EOF
$packages
EOF
            if module_set_service_state "$module" install; then
                result="$(command_success_result "OpenWrt module installed" "\"module\":\"$(json_escape "$module")\",\"action\":\"install\"")"
            else
                status=failed; result="$(command_failed_result "module installed, but its service failed to start")"
            fi
            ;;
        enable|disable) :
            if module_set_service_state "$module" "$action"; then
                result="$(command_success_result "OpenWrt module state changed" "\"module\":\"$(json_escape "$module")\",\"action\":\"$action\"")"
            else
                status=failed; result="$(command_failed_result "module service is unavailable")"
            fi
            ;;
        remove) :
            if printf '%s\n' "$packages" | awk 'NF {line[NR]=$0} END {for (i=NR; i>0; i--) print line[i]}' | while IFS= read -r package; do
                module_package_installed "$package" || continue
                package_apply remove "$package" >/dev/null 2>&1 || exit 1
            done; then
                result="$(command_success_result "OpenWrt module removed" "\"module\":\"$(json_escape "$module")\",\"action\":\"remove\"")"
            else
                status=failed; result="$(command_failed_result "failed to remove module packages")"
            fi
            ;;
        *) status=failed; result="$(command_failed_result "unsupported module action")" ;;
    esac
    return 0
}
