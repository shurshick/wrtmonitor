COMMAND_RESULT_DIR="$STATUS_DIR/command-results"
COMMAND_RESULT_LIMIT=100

valid_command_id() {
    case "$1" in
        ""|*[!0-9a-fA-F-]*) return 1 ;;
        *) [ "${#1}" -ge 32 ] && [ "${#1}" -le 40 ] ;;
    esac
}

command_result_file() {
    valid_command_id "$1" || return 1
    printf '%s/%s.json' "$COMMAND_RESULT_DIR" "$1"
}

cached_command_result() {
    path="$(command_result_file "$1")" || return 1
    [ -s "$path" ] || return 1
    cat "$path"
}

remember_command_result() {
    command_id="$1"
    body="$2"
    path="$(command_result_file "$command_id")" || return 1
    mkdir -p "$COMMAND_RESULT_DIR"
    temporary="$path.tmp.$$"
    printf '%s' "$body" >"$temporary"
    mv "$temporary" "$path"
    # BusyBox-compatible bounded journal. Oldest entries are discarded first.
    count="$(find "$COMMAND_RESULT_DIR" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
    while [ "${count:-0}" -gt "$COMMAND_RESULT_LIMIT" ]; do
        # Filenames are validated command UUIDs; ls -t is available on BusyBox.
        # shellcheck disable=SC2012
        oldest="$(ls -1tr "$COMMAND_RESULT_DIR"/*.json 2>/dev/null | head -n 1)"
        [ -n "$oldest" ] || break
        rm -f "$oldest"
        count=$((count - 1))
    done
}

report_command_result() {
    command_id="$1"
    status="$2"
    result="${3:-}"
    [ -n "$result" ] || result="{}"
    body="{\"status\":\"$(json_escape "$status")\",\"result\":$result}"
    terminal=0
    case "$status" in
        done|success|failed)
            terminal=1
            # Keep the complete result until the server confirms receipt. This is
            # required for retrying artifacts such as a backup archive.
            remember_command_result "$command_id" "$body"
            ;;
    esac
    if api POST "/api/v1/agent/commands/$command_id/result" "$body"; then
        if [ "$terminal" = "1" ]; then
            compact="{\"status\":\"$(json_escape "$status")\",\"result\":{\"message\":\"command already completed; duplicate suppressed\"}}"
            remember_command_result "$command_id" "$compact"
        fi
        return 0
    fi
    return 1
}
