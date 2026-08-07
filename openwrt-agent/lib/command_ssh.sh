# Web SSH Handler for WrtMonitor Agent
# shellcheck disable=SC2034,SC2154
handle_command_agent_ssh_session() {
    cmd_id="$1"
    
    # We use curl with chunked upload (named pipe) and infinite download.
    device_id="$(cfg device_id)"
    server_url="$(cfg server_url)"
    token="$(cfg device_token)"
    
    log_notice "Starting Web SSH session via curl streams..."
    
    # Clean up any previous session pipes
    rm -f /tmp/wrtmonitor_ssh_in /tmp/wrtmonitor_ssh_out 2>/dev/null
    
    # Create named pipes
    mkfifo /tmp/wrtmonitor_ssh_in
    mkfifo /tmp/wrtmonitor_ssh_out
    
    # Start download stream in background (reads from server, writes to pipe)
    # Using uclient-fetch if curl is somehow missing, but curl is a hard dependency so curl is preferred.
    curl -sN -H "Authorization: Bearer $token" "$server_url/api/v1/agent/ssh/down/$device_id" > /tmp/wrtmonitor_ssh_in &
    pid_down=$!
    
    # Start upload stream in background (reads from pipe, sends to server chunked)
    curl -sN -T /tmp/wrtmonitor_ssh_out -H "Authorization: Bearer $token" -H "Expect:" "$server_url/api/v1/agent/ssh/up/$device_id" &
    pid_up=$!
    
    # Connect interactive shell to the pipes in background
    (
        /bin/ash -i < /tmp/wrtmonitor_ssh_in > /tmp/wrtmonitor_ssh_out 2>&1
        
        # When shell exits, kill the curl streams
        kill -9 "$pid_down" "$pid_up" 2>/dev/null
        rm -f /tmp/wrtmonitor_ssh_in /tmp/wrtmonitor_ssh_out 2>/dev/null
    ) &
    
    status="done"
    result="$(command_success_result "Web SSH session started" "\"status\":\"ssh_started\"")"
    return 0
}
