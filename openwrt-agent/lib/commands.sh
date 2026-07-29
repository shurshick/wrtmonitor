command_requires_state_refresh() {
    case "$1" in
        wifi.status|network.interfaces|diagnostics.run|maintenance.logs.read|maintenance.processes.read|maintenance.cron.read|maintenance.services.read|maintenance.backup.create|maintenance.diagnostics.bundle|vpn.wireguard.export_peer|agent.status|agent.update|agent.rollback|agent.disconnect) return 1 ;;
        *) return 0 ;;
    esac
}

refresh_state_after_command() {
    command_requires_state_refresh "$1" || return 0
    if telemetry >/dev/null 2>&1; then
        log_notice "state refreshed after $1"
        return 0
    fi
    log_notice "state refresh failed after $1"
    return 1
}

execute_command() {
    command_id="$1"
    command_type="$2"
    command_payload="${3:-{}}"
    status="done"
    result="{}"
    disconnect_after=0
    transaction_active=0
    recovery_mode="$(uci -q get "$CONFIG.recovery_mode" 2>/dev/null || echo 0)"
    if [ "$recovery_mode" = 1 ]; then
        case "$command_type" in
            wifi.status|network.interfaces|diagnostics.run|maintenance.packages.refresh|maintenance.backup.create|maintenance.logs.read|maintenance.processes.read|maintenance.cron.read|maintenance.services.read|maintenance.diagnostics.bundle|maintenance.recovery.disable|agent.status) ;;
            *)
                result="$(command_failed_result "recovery mode blocks configuration changes")"
                report_command_result "$command_id" failed "$result" >/dev/null || true
                return 1
                ;;
        esac
    fi
    if transaction_configs_for_command "$command_type" >/dev/null 2>&1; then
        transaction_timeout="$(transaction_timeout_from_payload "$command_payload")"
        if transaction_begin "$command_id" "$command_type" "$transaction_timeout"; then
            transaction_active=1
        else
            result="$(transaction_failure_result "$command_id" "configuration preflight or backup failed" "not_applied")"
            report_command_result "$command_id" failed "$result" >/dev/null || true
            return 1
        fi
    fi
    if handle_wifi_command; then :
    elif handle_network_command; then :
    elif handle_firewall_command; then :
    elif handle_vpn_command; then :
    elif handle_system_command; then :
    elif handle_maintenance_command; then :
    elif handle_module_command; then :
    elif handle_agent_command; then :
    else
        status="failed"
        result='{"error":"unsupported command"}'
    fi
    if [ "$status" = "done" ] && ! verify_command_postcondition "$command_type" "$command_payload"; then
        status="failed"
        result="$(command_failed_result "post-condition verification failed")"
    fi
    if [ "$transaction_active" = "1" ]; then
        if [ "$status" = "done" ] && transaction_is_connectivity_sensitive "$command_type"; then
            result="{\"message\":\"configuration applied; connectivity verification is running\",\"transaction\":{\"id\":\"$(json_escape "$command_id")\",\"state\":\"verifying\",\"rollback_timeout_seconds\":$transaction_timeout}}"
            api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"running\",\"result\":$result}" >/dev/null || true
            transaction_schedule_verification "$command_id"
            return 0
        fi
        if [ "$status" = "done" ]; then
            transaction_set_state "$command_id" "confirmed"
            result="$(transaction_success_result "$command_id")"
        elif transaction_restore "$command_id"; then
            result="$(transaction_failure_result "$command_id" "configuration command failed; backup restored" "rolled_back")"
        else
            result="$(transaction_failure_result "$command_id" "configuration command failed and rollback failed" "rollback_failed")"
        fi
    fi
    if [ "$status" = "done" ] || [ "$status" = "success" ]; then
        refresh_state_after_command "$command_type" || true
    fi
    report_command_result "$command_id" "$status" "$result" >/dev/null || true
    if [ "$disconnect_after" = "1" ] && [ "$status" = "done" ]; then
        uci set "$CONFIG.enabled=0"
        uci commit wrtmonitor
        log_notice "agent disconnected by server command"
        exit 0
    fi
    if [ "$PENDING_AGENT_EXEC" = "1" ] && [ "$status" = "done" ]; then
        handoff_to_updated_agent
    fi
}
