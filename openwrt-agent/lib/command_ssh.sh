# PTY terminal command handler for WrtMonitor Agent.
# Transport and supervisor helpers live in command_terminal_transport.sh.
# shellcheck disable=SC2034,SC2154

handle_command_agent_ssh_session() {
    cmd_id="$1"
    payload="${2:-}"
    [ -n "$payload" ] || payload="{}"

    printf '%s' "$payload" >"/tmp/wrtmonitor-terminal-payload-$cmd_id"
    session_id="$(json_get_string "/tmp/wrtmonitor-terminal-payload-$cmd_id" '@.session_id')"
    columns="$(json_get_number "/tmp/wrtmonitor-terminal-payload-$cmd_id" '@.columns')"
    rows="$(json_get_number "/tmp/wrtmonitor-terminal-payload-$cmd_id" '@.rows')"
    rm -f "/tmp/wrtmonitor-terminal-payload-$cmd_id"

    case "$session_id" in
        ????????-????-????-????-????????????) ;;
        *)
            status="failed"
            result="$(command_failed_result 'terminal session_id is missing or invalid')"
            return 1
            ;;
    esac
    case "$columns" in ""|*[!0-9]*) columns=80 ;; esac
    case "$rows" in ""|*[!0-9]*) rows=24 ;; esac
    if ! command -v script >/dev/null 2>&1; then
        status="failed"
        result="$(command_failed_result 'PTY helper is unavailable; install script-utils')"
        return 1
    fi

    pid_file="/tmp/wrtmonitor-terminal-$session_id.pid"
    launch_file="/tmp/wrtmonitor-terminal-$session_id.launch"
    launch_log="/tmp/wrtmonitor-terminal-$session_id.log"
    printf '%s\n' starting >"$launch_file"
    rm -f "$launch_log"
    if ! start-stop-daemon -S -b -m -p "$pid_file" \
            -x "$AGENT_SCRIPT" -- \
            terminal-supervisor "$session_id" "$columns" "$rows"; then
        rm -f "$launch_file"
        status="failed"
        result="$(command_failed_result 'failed to start PTY supervisor')"
        return 1
    fi

    attempts=0
    while [ "$attempts" -lt 15 ]; do
        launch_state="$(cat "$launch_file" 2>/dev/null || true)"
        case "$launch_state" in
            ready)
                rm -f "$launch_file" "$launch_log"
                status="done"
                result="$(command_success_result 'PTY terminal session started' "\"status\":\"ssh_started\",\"session_id\":\"$(json_escape "$session_id")\"")"
                return 0
                ;;
            failed:*)
                reason="${launch_state#failed: }"
                rm -f "$launch_file"
                status="failed"
                result="$(command_failed_result "$reason")"
                return 1
                ;;
        esac
        supervisor_pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [ -n "$supervisor_pid" ] && ! kill -0 "$supervisor_pid" 2>/dev/null; then
            reason="$(tail -n 1 "$launch_log" 2>/dev/null || true)"
            [ -n "$reason" ] || reason='PTY supervisor exited during startup'
            rm -f "$launch_file"
            status="failed"
            result="$(command_failed_result "$reason")"
            return 1
        fi
        attempts=$((attempts + 1))
        sleep 1
    done

    rm -f "/tmp/wrtmonitor-terminal-$session_id/active"
    supervisor_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$supervisor_pid" ]; then
        kill "$supervisor_pid" 2>/dev/null || true
    fi
    rm -f "$launch_file"
    status="failed"
    result="$(command_failed_result 'terminal startup readiness timeout')"
    return 1
}
