transaction_schedule_verification() {
    transaction_set_state "$1" "verifying"
    (sleep 10; "$SCRIPT_PATH" verify-transaction "$1") >/dev/null 2>&1 &
}

transaction_restart_verification_window() {
    directory="$(transaction_dir "$1")" || return 1
    recovery_count="$(transaction_meta_value "$1" recovery_count)"
    case "$recovery_count" in ""|*[!0-9]*) recovery_count=0 ;; esac
    [ "$recovery_count" -lt 1 ] || return 1
    recovery_count=$((recovery_count + 1))
    sed -i "/^started_epoch=/d;/^recovery_count=/d" "$directory/meta"
    {
        printf 'started_epoch=%s\n' "$(date +%s 2>/dev/null || echo 0)"
        printf 'recovery_count=%s\n' "$recovery_count"
    } >>"$directory/meta"
}

transaction_runtime_ready() {
    command_id="$1"
    command_type="$(transaction_meta_value "$command_id" command_type)"
    [ "$command_type" = network.set_lan ] || return 0
    directory="$(transaction_dir "$command_id")" || return 1
    payload_file="$directory/payload.json"
    [ -r "$payload_file" ] || return 1
    interface="$(json_get_string "$payload_file" '@.interface')"
    [ -n "$interface" ] || interface=lan
    expected_ipv4="$(json_get_string "$payload_file" '@.ip_address')"
    network_interface_has_ipv4 "$interface" "$expected_ipv4"
}

transaction_has_newer_confirmed_overlap() {
    current_id="$1"
    current_configs="$2"
    current_started="$3"
    for other_directory in "$CONFIG_TRANSACTION_DIR"/*; do
        [ -r "$other_directory/meta" ] || continue
        other_id="${other_directory##*/}"
        [ "$other_id" != "$current_id" ] || continue
        [ "$(transaction_meta_value "$other_id" state)" = "confirmed" ] || continue
        other_started="$(transaction_meta_value "$other_id" started_epoch)"
        case "$other_started" in ""|*[!0-9]*) continue ;; esac
        [ "$other_started" -gt "$current_started" ] || continue
        other_configs="$(transaction_meta_value "$other_id" configs)"
        for config_name in $current_configs; do
            if printf '%s\n' "$other_configs" | grep -qw "$config_name"; then
                return 0
            fi
        done
    done
    return 1
}

transaction_recover_pending() {
    ensure_state_dirs
    now_epoch="$(date +%s 2>/dev/null || echo 0)"
    for directory in "$CONFIG_TRANSACTION_DIR"/*; do
        [ -r "$directory/meta" ] || continue
        command_id="${directory##*/}"
        transaction_valid_id "$command_id" || continue
        state="$(transaction_meta_value "$command_id" state)"
        case "$state" in prepared|verifying) ;; *) continue ;; esac
        rollback_timeout="$(transaction_meta_value "$command_id" rollback_timeout)"
        started_epoch="$(transaction_meta_value "$command_id" started_epoch)"
        case "$rollback_timeout" in ""|*[!0-9]*) rollback_timeout=90 ;; esac
        case "$started_epoch" in ""|*[!0-9]*) started_epoch=0 ;; esac
        configs="$(transaction_meta_value "$command_id" configs)"
        if transaction_has_newer_confirmed_overlap "$command_id" "$configs" "$started_epoch"; then
            transaction_set_state "$command_id" "superseded"
            result="$(transaction_failure_result "$command_id" "unfinished transaction superseded by a newer confirmed change" "not_applied")"
            report_command_result "$command_id" failed "$result" >/dev/null 2>&1 || true
            log_notice "abandoned superseded transaction $command_id"
            continue
        fi
        if [ "$started_epoch" -gt 0 ] && [ "$now_epoch" -lt $((started_epoch + rollback_timeout)) ]; then
            transaction_schedule_verification "$command_id"
            continue
        fi
        if transaction_restart_verification_window "$command_id"; then
            transaction_schedule_verification "$command_id"
            log_notice "resumed unfinished transaction $command_id after agent restart"
            continue
        fi
        if transaction_restore "$command_id"; then
            rollback_state="rolled_back"
        else
            rollback_state="rollback_failed"
        fi
        result="$(transaction_failure_result "$command_id" "agent restarted before transaction confirmation" "$rollback_state")"
        report_command_result "$command_id" failed "$result" >/dev/null 2>&1 || true
        log_notice "recovered unfinished transaction $command_id: $rollback_state"
    done
}
