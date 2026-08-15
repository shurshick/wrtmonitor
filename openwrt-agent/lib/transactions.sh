verify_transaction() {
    command_id="$1"
    directory="$(transaction_dir "$command_id")" || return 1
    [ -r "$directory/meta" ] || return 1
    rollback_timeout="$(transaction_meta_value "$command_id" rollback_timeout)"
    started_epoch="$(transaction_meta_value "$command_id" started_epoch)"
    case "$rollback_timeout" in ""|*[!0-9]*) rollback_timeout=90 ;; esac
    case "$started_epoch" in ""|*[!0-9]*) started_epoch="$(date +%s 2>/dev/null || echo 0)" ;; esac
    while true; do
        if curl -fsS --connect-timeout 5 --max-time 10 "$(server_url)/health" >/dev/null 2>&1 && transaction_runtime_ready "$command_id"; then
            transaction_set_state "$command_id" "confirmed"
            result="$(transaction_success_result "$command_id")"
            report_command_result "$command_id" success "$result" >/dev/null || true
            return 0
        fi
        now_epoch="$(date +%s 2>/dev/null || echo 0)"
        [ "$now_epoch" -lt $((started_epoch + rollback_timeout)) ] || break
        sleep 5
    done
    if transaction_restore "$command_id"; then rollback_state="rolled_back"; else rollback_state="rollback_failed"; fi
    sleep 8
    result="$(transaction_failure_result "$command_id" "connectivity verification timed out" "$rollback_state")"
    report_command_result "$command_id" failed "$result" >/dev/null || true
    return 1
}
