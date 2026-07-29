module_primary_package() {
    case "$1" in
        storage) printf block-mount ;;
        smb) printf samba4-server ;;
        nfs) printf nfs-kernel-server ;;
        ftp) printf vsftpd ;;
        dlna) printf minidlna ;;
        printer) printf p910nd ;;
        modem) printf umbim ;;
        *) return 1 ;;
    esac
}

module_service() {
    case "$1" in
        smb) printf samba4 ;;
        nfs) printf nfsd ;;
        ftp) printf vsftpd ;;
        dlna) printf minidlna ;;
        printer) printf p910nd ;;
        *) return 1 ;;
    esac
}

module_package_installed() {
    package="$1"
    package_list_installed 2>/dev/null | grep -Eq "^${package}([|[:space:]]|$)"
}

module_hardware_items() {
    kind="$1"
    root="${WRTMONITOR_SYSTEM_ROOT:-}"
    case "$kind" in
        block)
            for item in "$root"/sys/class/block/*; do
                [ -e "$item" ] || continue
                name="${item##*/}"
                case "$name" in loop*|ram*|mtd*|ubiblock*) continue ;; esac
                printf '%s\n' "$name"
            done
            ;;
        printer)
            for item in "$root"/dev/usb/lp*; do [ -e "$item" ] && printf '%s\n' "${item#"${root}"}"; done
            ;;
        modem)
            for item in "$root"/dev/cdc-wdm* "$root"/dev/ttyUSB* "$root"/dev/ttyACM*; do [ -e "$item" ] && printf '%s\n' "${item#"${root}"}"; done
            ;;
    esac
}

module_item_json() {
    module="$1"
    hardware_count="$2"
    primary_package="$(module_primary_package "$module")"
    installed=false
    module_package_installed "$primary_package" && installed=true
    service="$(module_service "$module" 2>/dev/null || true)"
    running=false
    enabled=false
    if [ -n "$service" ] && [ -x "${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service" ]; then
        "${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service" running >/dev/null 2>&1 && running=true
        "${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service" enabled >/dev/null 2>&1 && enabled=true
    fi
    supported=true
    case "$module" in
        printer|modem) [ "$hardware_count" -gt 0 ] || [ "$installed" = true ] || supported=false ;;
    esac
    printf '{"id":"%s","supported":%s,"installed":%s,"running":%s,"enabled":%s,"hardware_count":%s,"primary_package":"%s"}' \
        "$module" "$supported" "$installed" "$running" "$enabled" "$hardware_count" "$(json_escape "$primary_package")"
}

modules_json() {
    block_items="$(module_hardware_items block)"
    printer_items="$(module_hardware_items printer)"
    modem_items="$(module_hardware_items modem)"
    block_count="$(printf '%s\n' "$block_items" | awk 'NF {count++} END {print count + 0}')"
    printer_count="$(printf '%s\n' "$printer_items" | awk 'NF {count++} END {print count + 0}')"
    modem_count="$(printf '%s\n' "$modem_items" | awk 'NF {count++} END {print count + 0}')"
    items=""
    for module in storage smb nfs ftp dlna printer modem; do
        count=0
        case "$module" in storage) count="$block_count" ;; printer) count="$printer_count" ;; modem) count="$modem_count" ;; esac
        item="$(module_item_json "$module" "$count")"
        [ -n "$items" ] && items="$items,"
        items="$items$item"
    done
    printf '{"state":"observed","items":[%s],"hardware":{"block_devices":"%s","printers":"%s","modems":"%s"}}' \
        "$items" "$(json_escape "$(printf '%s' "$block_items" | tr '\n' ' ')")" \
        "$(json_escape "$(printf '%s' "$printer_items" | tr '\n' ' ')")" \
        "$(json_escape "$(printf '%s' "$modem_items" | tr '\n' ' ')")"
}
