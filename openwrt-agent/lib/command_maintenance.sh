handle_maintenance_command() {
    case "$command_type" in
        maintenance.packages.refresh)
            package_manager_value="$(package_manager_name 2>/dev/null || true)"
            if [ -n "$package_manager_value" ] && package_refresh_indexes >/dev/null 2>&1; then
                upgrades="$(package_list_upgradeable | head -n 50 | tr '\n' ';')"
                result="$(command_success_result "package lists refreshed" "\"manager\":\"$package_manager_value\",\"upgradable\":\"$(json_escape "$upgrades")\"")"
            else status=failed; result="$(command_failed_result "apk/opkg package index update failed")"; fi
            ;;
        maintenance.package.install|maintenance.package.remove|maintenance.package.upgrade)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; package="$(json_get_string "$payload_file" '@.package')"; rm -f "$payload_file"
            package_action=install; [ "$command_type" = maintenance.package.remove ] && package_action=remove
            case "$package_action:$package" in
                remove:base-files|remove:busybox|remove:dnsmasq|remove:dropbear|remove:firewall4|remove:kernel|remove:libc|remove:netifd|remove:procd|remove:ubus|remove:uci|remove:wrtmonitor|remove:wrtmonitor-agent)
                    status=failed; result="$(command_failed_result "system package removal is not allowed")"
                    ;;
                *)
                    if package_output="$(package_apply "$package_action" "$package" 2>&1)"; then
                        if [ "$package_action" = install ] && [ "$package" = nlbwmon ]; then
                            if ! ensure_nlbwmon_runtime >/dev/null 2>&1; then
                                status="failed"
                                result="$(command_failed_result "nlbwmon installed, but runtime initialization failed")"
                            fi
                        fi
                        if [ "$status" != failed ]; then
                            package_message="package operation completed"
                            [ "$command_type" = maintenance.package.upgrade ] && package_message="package upgraded"
                            result="$(command_success_result "$package_message" "\"package\":\"$(json_escape "$package")\",\"manager\":\"$(package_manager_name)\",\"output\":\"$(json_escape "$package_output")\"")"
                        fi
                    else status=failed; result="$(command_failed_result "$package_output")"; fi
                    ;;
            esac
            ;;
        maintenance.backup.create)
            backup_path="/tmp/wrtmonitor-backup-$command_id.tar.gz"
            if sysupgrade -b "$backup_path" >/dev/null 2>&1 && [ -s "$backup_path" ]; then backup_b64="$(base64 <"$backup_path" | tr -d '\n')"; result="$(command_success_result "configuration backup created" "\"filename\":\"wrtmonitor-openwrt-backup.tar.gz\",\"archive_base64\":\"$backup_b64\"")"; rm -f "$backup_path"; else status=failed; result="$(command_failed_result "failed to create configuration backup")"; fi
            ;;
        maintenance.backup.restore)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; restore_b64="$(json_get_string "$payload_file" '@.archive_base64')"; rm -f "$payload_file"; restore_path="/tmp/wrtmonitor-restore-$command_id.tar.gz"
            if ! printf '%s' "$restore_b64" | base64 -d >"$restore_path" 2>/dev/null; then status=failed; result="$(command_failed_result "backup decoding failed")"
            elif ! tar -tzf "$restore_path" 2>/dev/null | awk 'BEGIN{ok=1} /^\//{ok=0} /(^|\/)\.\.($|\/)/{ok=0} !/^etc\//{ok=0} END{exit !ok}'; then status=failed; result="$(command_failed_result "backup contains unsafe paths")"
            elif sysupgrade -r "$restore_path" >/dev/null 2>&1; then result="$(command_success_result "configuration backup restored; reboot recommended")"; else status=failed; result="$(command_failed_result "configuration restore failed")"; fi
            rm -f "$restore_path"
            ;;
        maintenance.sysupgrade.check)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; firmware_url="$(json_get_string "$payload_file" '@.url')"; firmware_sha="$(json_get_string "$payload_file" '@.sha256')"; expected_model="$(json_get_string "$payload_file" '@.expected_model')"; preserve_config="$(json_get_bool "$payload_file" '@.preserve_config')"; rm -f "$payload_file"; firmware_path=/tmp/wrtmonitor-sysupgrade.bin
            local_model="$(cat /tmp/sysinfo/model 2>/dev/null || true)"
            if [ -n "$expected_model" ] && [ "$expected_model" != "$local_model" ]; then status=failed; result="$(command_failed_result "firmware model does not match router")"
            elif ! curl -fsS --connect-timeout 15 --max-time 600 -o "$firmware_path" "$firmware_url"; then status=failed; result="$(command_failed_result "firmware download failed")"
            elif [ "$(sha256sum "$firmware_path" | awk '{print $1}')" != "$firmware_sha" ]; then status=failed; result="$(command_failed_result "firmware checksum mismatch")"
            elif firmware_size="$(wc -c <"$firmware_path" | tr -d ' ')" && tmp_free_bytes="$(df -k /tmp | awk 'NR == 2 {print $4 * 1024}')" && [ "$tmp_free_bytes" -lt 8388608 ]; then status=failed; result="$(command_failed_result "not enough free space to safely validate firmware")"
            elif ! sysupgrade -T "$firmware_path" >/tmp/wrtmonitor-sysupgrade-check.log 2>&1; then status=failed; result="$(command_failed_result "$(cat /tmp/wrtmonitor-sysupgrade-check.log 2>/dev/null || echo firmware validation failed)")"
            else uci set "$CONFIG.staged_firmware_sha256=$firmware_sha"; uci set "$CONFIG.staged_firmware_preserve=$( [ "$preserve_config" = true ] && printf 1 || printf 0 )"; uci commit wrtmonitor; firmware_size="$(wc -c <"$firmware_path" | tr -d ' ')"; result="$(command_success_result "firmware staged and validated" "\"sha256\":\"$firmware_sha\",\"size_bytes\":$firmware_size,\"model\":\"$(json_escape "$local_model")\"")"; fi
            rm -f /tmp/wrtmonitor-sysupgrade-check.log
            ;;
        maintenance.sysupgrade.apply)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; firmware_sha="$(json_get_string "$payload_file" '@.sha256')"; preserve_config="$(json_get_bool "$payload_file" '@.preserve_config')"; rm -f "$payload_file"; firmware_path=/tmp/wrtmonitor-sysupgrade.bin; staged_sha="$(uci -q get "$CONFIG.staged_firmware_sha256" 2>/dev/null || true)"
            if [ ! -s "$firmware_path" ] || [ "$staged_sha" != "$firmware_sha" ] || [ "$(sha256sum "$firmware_path" | awk '{print $1}')" != "$firmware_sha" ]; then status=failed; result="$(command_failed_result "validated firmware is not staged")"
            else result="$(command_success_result "sysupgrade scheduled")"; if [ "$preserve_config" = true ]; then (sleep 2; sysupgrade "$firmware_path") >/dev/null 2>&1 & else (sleep 2; sysupgrade -n "$firmware_path") >/dev/null 2>&1 & fi; fi
            ;;
        maintenance.logs.read)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; log_lines="$(json_get_number "$payload_file" '@.lines')"; rm -f "$payload_file"; logs="$(logread 2>/dev/null | tail -n "$log_lines")"; result="$(command_success_result "system log collected" "\"logs\":\"$(json_escape "$logs")\"")"
            ;;
        maintenance.processes.read)
            process_output="$(ps w 2>/dev/null | head -n 100 || true)"
            result="$(command_success_result "process list collected" "\"processes\":\"$(json_escape "$process_output")\"")"
            ;;
        maintenance.process.signal)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; process_pid="$(json_get_number "$payload_file" '@.pid')"; process_signal="$(json_get_string "$payload_file" '@.signal')"; rm -f "$payload_file"; if kill -"$process_signal" "$process_pid" 2>/dev/null; then result="$(command_success_result "signal sent to process")"; else status=failed; result="$(command_failed_result "failed to signal process")"; fi
            ;;
        maintenance.cron.set)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"; cron_content="$(json_get_string "$payload_file" '@.content')"; rm -f "$payload_file"; cron_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root"; cp "$cron_path" "$cron_path.wrtmonitor.bak" 2>/dev/null || true; if printf '%s' "$cron_content" >"$cron_path" && /etc/init.d/cron restart >/dev/null 2>&1; then result="$(command_success_result "cron updated")"; else status=failed; result="$(command_failed_result "failed to update cron")"; fi
            ;;
        maintenance.cron.read)
            cron_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root"
            cron_content="$(cat "$cron_path" 2>/dev/null || true)"
            result="$(command_success_result "cron schedule collected" "\"content\":\"$(json_escape "$cron_content")\"")"
            ;;
        maintenance.services.read)
            service_rows=""
            for service_path in "${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/"*; do
                [ -x "$service_path" ] || continue
                service_name="${service_path##*/}"
                service_running=false; "$service_path" running >/dev/null 2>&1 && service_running=true
                service_enabled=false; "$service_path" enabled >/dev/null 2>&1 && service_enabled=true
                [ -n "$service_rows" ] && service_rows="$service_rows,"
                service_rows="$service_rows{\"name\":\"$(json_escape "$service_name")\",\"running\":$service_running,\"enabled\":$service_enabled}"
            done
            result="$(command_success_result "service list collected" "\"services\":[$service_rows]")"
            ;;
        maintenance.service.set)
            payload_file=/tmp/wrtmonitor-command-payload; printf '%s' "$command_payload" >"$payload_file"
            service_name="$(json_get_string "$payload_file" '@.service')"; service_action="$(json_get_string "$payload_file" '@.action')"; rm -f "$payload_file"
            service_path="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$service_name"
            case "$service_action" in start|stop|restart|enable|disable) ;; *) service_action="" ;; esac
            if [ -n "$service_action" ] && [ -x "$service_path" ] && "$service_path" "$service_action" >/dev/null 2>&1; then
                result="$(command_success_result "service action completed" "\"service\":\"$(json_escape "$service_name")\",\"action\":\"$service_action\"")"
            else status=failed; result="$(command_failed_result "service action failed or service does not exist")"; fi
            ;;
        maintenance.diagnostics.bundle)
            bundle_dir="/tmp/wrtmonitor-diagnostics-$command_id"; bundle_path="$bundle_dir.tar.gz"; mkdir -p "$bundle_dir"; ubus call system board >"$bundle_dir/board.json" 2>&1 || true; ubus call system info >"$bundle_dir/system.json" 2>&1 || true; ubus call network.interface dump >"$bundle_dir/network.json" 2>&1 || true; logread 2>/dev/null | tail -n 500 >"$bundle_dir/logread.txt"; ps w >"$bundle_dir/processes.txt" 2>&1 || true; df -h >"$bundle_dir/storage.txt" 2>&1 || true; package_list_installed >"$bundle_dir/packages.txt" 2>&1 || true; capabilities_json >"$bundle_dir/capabilities.json"; if tar -czf "$bundle_path" -C "$bundle_dir" .; then bundle_b64="$(base64 <"$bundle_path" | tr -d '\n')"; result="$(command_success_result "diagnostic bundle created" "\"filename\":\"wrtmonitor-diagnostics.tar.gz\",\"bundle_base64\":\"$bundle_b64\"")"; else status=failed; result="$(command_failed_result "failed to create diagnostic bundle")"; fi; rm -rf "$bundle_dir" "$bundle_path"
            ;;
        maintenance.recovery.enable)
            recovery_path=/tmp/wrtmonitor-recovery.tar.gz; if sysupgrade -b "$recovery_path" >/dev/null 2>&1; then uci set "$CONFIG.recovery_mode=1"; uci commit wrtmonitor; result="$(command_success_result "recovery mode enabled")"; else status=failed; result="$(command_failed_result "failed to create recovery backup")"; fi
            ;;
        maintenance.recovery.disable)
            uci set "$CONFIG.recovery_mode=0"; uci commit wrtmonitor; result="$(command_success_result "recovery mode disabled")"
            ;;
        *) return 1 ;;
    esac
    return 0
}
