# Web SSH Handler for WrtMonitor Agent
# shellcheck disable=SC2034,SC2154
handle_command_agent_ssh_session() {
    cmd_id="$1"
    
    # Check if websocat is installed
    if ! command -v websocat >/dev/null 2>&1; then
        log_notice "websocat not found, attempting to install..."
        opkg update >/dev/null 2>&1
        opkg install websocat >/dev/null 2>&1
        if ! command -v websocat >/dev/null 2>&1; then
            status="failed"
            result="$(command_failed_result "websocat is required for Web SSH but could not be installed.")"
            return 0
        fi
    fi
    
    # Convert http:// to ws:// and https:// to wss://
    ws_url="$(cfg server_url | sed 's/^http/ws/')"
    
    device_id="$(cfg device_id)"
    
    log_notice "Starting Web SSH session to $ws_url/api/v1/agent/ssh/ws/$device_id"
    
    # Run in background so it doesn't block the agent loop
    # websocat bridges the WebSocket to an interactive ash shell
    # --ping-interval 30 to keep connection alive
    # sh-c:'exec /bin/ash -i 2>&1' connects stderr and stdout
    websocat -H "Authorization: Bearer $(cfg device_token)" --ping-interval 30 "$ws_url/api/v1/agent/ssh/ws/$device_id" sh-c:'exec /bin/ash -i 2>&1' &
    
    status="done"
    result="$(command_success_result "Web SSH session started" "\"status\":\"ssh_started\"")"
    return 0
}
