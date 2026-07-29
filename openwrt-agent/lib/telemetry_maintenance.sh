maintenance_json() {
    installed=0
    upgrades=0
    installed_items=""
    upgrade_items=""
    package_manager_value="$(package_manager_name 2>/dev/null || true)"
    if [ -n "$package_manager_value" ]; then
        installed_data="$(package_list_installed || true)"
        upgrade_data="$(package_list_upgradeable || true)"
        installed="$(printf '%s\n' "$installed_data" | awk 'NF {count++} END {print count + 0}')"
        upgrades="$(printf '%s\n' "$upgrade_data" | awk 'NF {count++} END {print count + 0}')"
        package_count=0
        while IFS='|' read -r package_name package_version; do
            [ -n "$package_name" ] || continue
            [ -n "$installed_items" ] && installed_items="$installed_items,"
            installed_items="$installed_items{\"name\":\"$(json_escape "$package_name")\",\"version\":\"$(json_escape "$package_version")\"}"
            package_count=$((package_count + 1)); [ "$package_count" -ge 250 ] && break
        done <<EOF
$installed_data
EOF
        package_count=0
        while IFS='|' read -r package_name current_version available_version; do
            [ -n "$package_name" ] || continue
            [ -n "$upgrade_items" ] && upgrade_items="$upgrade_items,"
            upgrade_items="$upgrade_items{\"name\":\"$(json_escape "$package_name")\",\"current_version\":\"$(json_escape "$current_version")\",\"available_version\":\"$(json_escape "$available_version")\"}"
            package_count=$((package_count + 1)); [ "$package_count" -ge 100 ] && break
        done <<EOF
$upgrade_data
EOF
    fi
    cron_entries=0
    cron_content=""
    if [ -r "${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root" ]; then
        cron_entries="$(sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root" | wc -l | tr -d ' ')"
        cron_content="$(cat "${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root" 2>/dev/null || true)"
    fi
    service_items=""
    service_count=0
    for service_path in "${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/"*; do
        [ -x "$service_path" ] || continue
        service_name="${service_path##*/}"
        service_running=false; "$service_path" running >/dev/null 2>&1 && service_running=true
        service_enabled=false; "$service_path" enabled >/dev/null 2>&1 && service_enabled=true
        [ -n "$service_items" ] && service_items="$service_items,"
        service_items="$service_items{\"name\":\"$(json_escape "$service_name")\",\"running\":$service_running,\"enabled\":$service_enabled}"
        service_count=$((service_count + 1)); [ "$service_count" -ge 100 ] && break
    done
    process_snapshot="$(ps w 2>/dev/null | head -n 80 || true)"
    recovery="$(uci -q get wrtmonitor.main.recovery_mode 2>/dev/null || echo 0)"
    staged_checksum="$(uci -q get wrtmonitor.main.staged_firmware_sha256 2>/dev/null || true)"
    printf '{"packages":{"manager":"%s","installed":%s,"upgradable":%s,"installed_items":[%s],"upgradable_items":[%s]},"cron_entries":%s,"cron_content":"%s","services":[%s],"process_snapshot":"%s","recovery_mode":%s,"staged_firmware_sha256":"%s"}' \
        "$(json_escape "$package_manager_value")" "${installed:-0}" "${upgrades:-0}" "$installed_items" "$upgrade_items" "${cron_entries:-0}" \
        "$(json_escape "$cron_content")" "$service_items" "$(json_escape "$process_snapshot")" \
        "$( [ "$recovery" = 1 ] && printf true || printf false )" \
        "$(json_escape "$staged_checksum")"
}
