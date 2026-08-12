execute_command() {
    command_id="$1"
    command_type="$2"
    command_payload="${3:-}"
    [ -n "$command_payload" ] || command_payload="{}"
    status="done"
    result="{}"
    disconnect_after=0
    transaction_active=0
    transaction_noop=0
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
            transaction_store_payload "$command_id" "$command_payload"
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
        if [ "$status" = "done" ] && [ "$transaction_noop" != "1" ] && transaction_is_connectivity_sensitive "$command_type"; then
            result="{\"message\":\"configuration applied; connectivity verification is running\",\"transaction\":{\"id\":\"$(json_escape "$command_id")\",\"state\":\"verifying\",\"rollback_timeout_seconds\":$transaction_timeout}}"
            api POST "/api/v1/agent/commands/$command_id/result" "{\"status\":\"running\",\"result\":$result}" >/dev/null || true
            transaction_schedule_verification "$command_id"
            return 0
        fi
        if [ "$status" = "done" ]; then
            transaction_set_state "$command_id" "confirmed"
            if [ "$command_type" = client.set_policy ]; then
                policy_file="/tmp/wrtmonitor-policy-result-$$"
                printf '%s' "$command_payload" >"$policy_file"
                policy_mac="$(json_get_string "$policy_file" '@.mac')"
                rm -f "$policy_file"
                observed="$(client_policy_observed_json "$policy_mac")"
                result="{\"message\":\"client policy applied and verified\",\"observed\":$observed,\"transaction\":{\"id\":\"$(json_escape "$command_id")\",\"state\":\"confirmed\",\"configs\":\"firewall wrtmonitor\",\"rollback\":false}}"
            else
                result="$(transaction_success_result "$command_id")"
            fi
        elif transaction_restore "$command_id"; then
            result="$(transaction_failure_result "$command_id" "configuration command failed; backup restored" "rolled_back")"
        else
            result="$(transaction_failure_result "$command_id" "configuration command failed and rollback failed" "rollback_failed")"
        fi
    fi
    # Read-after-write is handled by the explicit post-condition above. Full
    # telemetry belongs to the next daemon cycle: running it here can stall the
    # command lifecycle or race a connectivity transaction helper.
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
