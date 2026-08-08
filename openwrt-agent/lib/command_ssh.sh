# PTY terminal handler for WrtMonitor Agent.
# shellcheck disable=SC2034,SC2154

terminal_status() {
    session_id="$1"
    session_status="$2"
    reason="${3:-}"
    status_body="{\"status\":\"$(json_escape "$session_status")\""
    [ -n "$reason" ] && status_body="$status_body,\"reason\":\"$(json_escape "$reason")\""
    status_body="$status_body}"
    curl -fsS --connect-timeout 10 --max-time 20 \
        -X POST "$(server_url)/api/v1/agent/terminal/sessions/$session_id/status" \
        -H "Authorization: Bearer $(device_token)" \
        -H 'Content-Type: application/json' \
        -d "$status_body" >/dev/null 2>&1
}

terminal_down_loop() {
    session_id="$1"
    work_dir="$2"
    input_fifo="$work_dir/input"
    cursor_file="$work_dir/cursor"
    size_file="$work_dir/size"
    shell_pid_file="$work_dir/shell.pid"
    frames_file="$work_dir/frames"
    frame_file="$work_dir/frame"
    token="$(device_token)"
    server="$(server_url)"

    exec 3>"$input_fifo"
    while [ -e "$work_dir/active" ]; do
        after="$(cat "$cursor_file" 2>/dev/null || printf 0)"
        if ! curl -fsS --connect-timeout 10 --max-time 35 \
                -H "Authorization: Bearer $token" \
                "$server/api/v1/agent/terminal/sessions/$session_id/down?after=$after&wait_seconds=20" \
                >"$frames_file"; then
            sleep 1
            continue
        fi
        while IFS= read -r frame; do
            [ -n "$frame" ] || continue
            printf '%s' "$frame" >"$frame_file"
            frame_id="$(json_get_number "$frame_file" '@.id')"
            frame_type="$(json_get_string "$frame_file" '@.type')"
            [ -n "$frame_id" ] && printf '%s' "$frame_id" >"$cursor_file"
            case "$frame_type" in
                data)
                    frame_data="$(json_get_string "$frame_file" '@.data')"
                    [ -n "$frame_data" ] && printf '%s' "$frame_data" | base64 -d >&3
                    ;;
                resize)
                    frame_columns="$(json_get_number "$frame_file" '@.columns')"
                    frame_rows="$(json_get_number "$frame_file" '@.rows')"
                    case "$frame_columns:$frame_rows" in
                        *[!0-9:]*|:*) ;;
                        *)
                            printf '%s %s\n' "$frame_rows" "$frame_columns" >"$size_file"
                            shell_pid="$(cat "$shell_pid_file" 2>/dev/null || true)"
                            if [ -n "$shell_pid" ]; then
                                kill -WINCH "$shell_pid" 2>/dev/null || true
                            fi
                            ;;
                    esac
                    ;;
                close)
                    rm -f "$work_dir/active"
                    break
                    ;;
                ping) ;;
            esac
        done <"$frames_file"
    done
    exec 3>&-
}

terminal_up_loop() {
    session_id="$1"
    work_dir="$2"
    output_fifo="$work_dir/output"
    token="$(device_token)"
    server="$(server_url)"

    while [ -e "$work_dir/active" ]; do
        curl -fsS --connect-timeout 10 \
            -X PUT "$server/api/v1/agent/terminal/sessions/$session_id/up" \
            -H "Authorization: Bearer $token" \
            -H 'Content-Type: application/octet-stream' \
            -H 'Expect:' \
            --upload-file "$output_fifo" >/dev/null 2>&1 || true
        [ -e "$work_dir/active" ] && sleep 1
    done
}

terminal_supervisor() {
    session_id="$1"
    columns="$2"
    rows="$3"
    work_dir="/tmp/wrtmonitor-terminal-$session_id"
    input_fifo="$work_dir/input"
    output_fifo="$work_dir/output"
    size_file="$work_dir/size"
    env_file="$work_dir/ash.env"

    rm -rf "$work_dir"
    mkdir -m 0700 "$work_dir" || return 1
    mkfifo "$input_fifo" "$output_fifo" || return 1
    chmod 0600 "$input_fifo" "$output_fifo"
    printf '0' >"$work_dir/cursor"
    printf '%s %s\n' "$rows" "$columns" >"$size_file"
    : >"$work_dir/active"
    cat >"$env_file" <<'EOF'
wrtmonitor_terminal_resize() {
    set -- $(cat "$WRTMONITOR_TERM_SIZE" 2>/dev/null || printf '24 80')
    stty rows "${1:-24}" cols "${2:-80}" 2>/dev/null || true
}
printf '%s\n' "$$" >"$WRTMONITOR_TERM_PID"
trap wrtmonitor_terminal_resize WINCH
wrtmonitor_terminal_resize
EOF

    if ! terminal_status "$session_id" connecting; then
        printf 'failed to announce terminal session %s\n' "$session_id" >&2
        rm -rf "$work_dir"
        rm -f "/tmp/wrtmonitor-terminal-$session_id.pid"
        return 1
    fi
    terminal_down_loop "$session_id" "$work_dir" &
    pid_down=$!
    terminal_up_loop "$session_id" "$work_dir" &
    pid_up=$!

    if TERM=xterm-256color \
        ENV="$env_file" \
        WRTMONITOR_TERM_SIZE="$size_file" \
        WRTMONITOR_TERM_PID="$work_dir/shell.pid" \
            script -q -f -c '/bin/ash -i' /dev/null \
            <"$input_fifo" >"$output_fifo" 2>&1; then
        exit_code=0
    else
        exit_code=$?
    fi

    rm -f "$work_dir/active"
    kill "$pid_down" "$pid_up" 2>/dev/null || true
    wait "$pid_down" "$pid_up" 2>/dev/null || true
    if [ "$exit_code" -eq 0 ]; then
        terminal_status "$session_id" closed 'PTY session ended' || true
    else
        terminal_status "$session_id" failed "PTY exited with code $exit_code" || true
    fi
    rm -rf "$work_dir"
    rm -f "/tmp/wrtmonitor-terminal-$session_id.pid"
}

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
    if ! start-stop-daemon -S -b -m -p "$pid_file" -n wrt-terminal \
            -x "$AGENT_SCRIPT" -- \
            terminal-supervisor "$session_id" "$columns" "$rows"; then
        status="failed"
        result="$(command_failed_result 'failed to start PTY supervisor')"
        return 1
    fi
    status="done"
    result="$(command_success_result 'PTY terminal session started' "\"status\":\"ssh_started\",\"session_id\":\"$(json_escape "$session_id")\"")"
    return 0
}
