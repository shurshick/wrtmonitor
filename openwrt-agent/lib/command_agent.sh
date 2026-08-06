# shellcheck disable=SC2034,SC2154
handle_agent_command() {
    case "$command_type" in
        diagnostics.run)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            checks="$(jsonfilter -i /tmp/wrtmonitor-command-payload -e '@.checks[*]' 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
            rm -f /tmp/wrtmonitor-command-payload
            if [ -n "$checks" ]; then
                result="$(diagnostics_checks_json "$checks")"
            else
                result="$(diagnostics_json)"
            fi
            ;;
        agent.disconnect)
            result="$(command_success_result "agent disabled")"
            disconnect_after=1
            ;;
        agent.ssh_session)
            if handle_command_agent_ssh_session "$command_id"; then
                # result is set in the handler
                :
            else
                status="failed"
            fi
            ;;
        agent.update)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            force="$(json_get_bool /tmp/wrtmonitor-command-payload '@.force')"
            allow_downgrade="$(json_get_bool /tmp/wrtmonitor-command-payload '@.allow_downgrade')"
            rm -f /tmp/wrtmonitor-command-payload
            [ "$force" = "true" ] || force="false"
            [ "$allow_downgrade" = "true" ] || allow_downgrade="false"
            if check_for_update "command" "$( [ "$force" = "true" ] && printf 1 || printf 0 )" "$( [ "$allow_downgrade" = "true" ] && printf 1 || printf 0 )"; then
                result="$(agent_status_json)"
            else
                status="failed"
                load_status
                result="{\"error\":\"$(json_escape "${LAST_UPDATE_ERROR:-update failed}")\"}"
            fi
            ;;
        agent.rollback)
            if perform_rollback "command" "rollback requested"; then
                result="$(agent_status_json)"
            else
                status="failed"
                load_status
                result="{\"error\":\"$(json_escape "${LAST_UPDATE_ERROR:-rollback unavailable}")\"}"
            fi
            ;;
        agent.set_auto_update)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            enabled="$(json_get_bool /tmp/wrtmonitor-command-payload '@.enabled')"
            rm -f /tmp/wrtmonitor-command-payload
            if [ "$enabled" = "false" ]; then
                set_auto_update_config 0
            else
                set_auto_update_config 1
            fi
            result="$(agent_status_json)"
            ;;
        agent.set_interval)
            printf '%s' "$command_payload" >/tmp/wrtmonitor-command-payload
            interval_seconds="$(json_get_number /tmp/wrtmonitor-command-payload '@.interval_seconds')"
            rm -f /tmp/wrtmonitor-command-payload
            case "$interval_seconds" in
                ""|*[!0-9]*)
                    status="failed"
                    result="$(command_failed_result "interval_seconds must be numeric")"
                    ;;
                *)
                    if [ "$interval_seconds" -lt 5 ]; then
                        status="failed"
                        result="$(command_failed_result "interval_seconds must be at least 5")"
                    else
                        uci set "$CONFIG.interval=$interval_seconds"
                        uci commit wrtmonitor
                        result="$(agent_status_json)"
                    fi
                    ;;
            esac
            ;;
        agent.rotate_token)
            old_device_token="$(device_token)"
            if token_response="$(api POST /api/v1/agent/token/rotate '{}')"; then
                printf '%s' "$token_response" >/tmp/wrtmonitor-token-rotate
                new_device_token="$(json_get_string /tmp/wrtmonitor-token-rotate '@.device_token')"
                rollback_token="$(json_get_string /tmp/wrtmonitor-token-rotate '@.rollback_token')"
                rm -f /tmp/wrtmonitor-token-rotate
            else
                new_device_token=""
                rollback_token=""
            fi
            if [ -n "$new_device_token" ] && [ -n "$rollback_token" ] \
                    && uci set "$CONFIG.device_token=$new_device_token" \
                    && uci commit wrtmonitor; then
                api POST /api/v1/agent/token/confirm '{}' >/dev/null 2>&1 || true
                result="$(command_success_result "device token rotated")"
            else
                uci set "$CONFIG.device_token=$old_device_token" >/dev/null 2>&1 || true
                uci commit wrtmonitor >/dev/null 2>&1 || true
                if [ -n "$rollback_token" ]; then
                    rollback_body="{\"rollback_token\":\"$(json_escape "$rollback_token")\"}"
                    api_using_token POST /api/v1/agent/token/rollback "$old_device_token" "$rollback_body" >/dev/null 2>&1 || true
                fi
                status="failed"
                result="$(command_failed_result "failed to persist rotated device token")"
            fi
            ;;
        *) return 1 ;;
    esac
    return 0
}
