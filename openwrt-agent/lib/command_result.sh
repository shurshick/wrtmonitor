list_config_backups() {
    ensure_state_dirs
    find "$CONFIG_BACKUP_DIR" -maxdepth 1 -type f -name '*.bak' | sort
}

backup_wireless_config() {
    command_id="$1"
    command_type="$2"
    ensure_state_dirs
    [ -r /etc/config/wireless ] || return 1
    timestamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo unknown)"
    backup_file="$CONFIG_BACKUP_DIR/wireless-$timestamp-$command_id.bak"
    meta_file="$CONFIG_BACKUP_DIR/wireless-$timestamp-$command_id.meta"
    cp /etc/config/wireless "$backup_file"
    {
        printf 'command_id=%s\n' "$command_id"
        printf 'command_type=%s\n' "$command_type"
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'agent_version=%s\n' "$AGENT_VERSION"
        printf 'config_file=/etc/config/wireless\n'
    } >"$meta_file"
    printf '%s' "$backup_file"
}

backup_config() {
    config_name="$1"
    command_id="$2"
    command_type="$3"
    ensure_state_dirs
    config_file="/etc/config/$config_name"
    [ -r "$config_file" ] || return 1
    timestamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo unknown)"
    backup_file="$CONFIG_BACKUP_DIR/$config_name-$timestamp-$command_id.bak"
    cp "$config_file" "$backup_file"
    {
        printf 'command_id=%s\n' "$command_id"
        printf 'command_type=%s\n' "$command_type"
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'agent_version=%s\n' "$AGENT_VERSION"
        printf 'config_file=%s\n' "$config_file"
    } >"$CONFIG_BACKUP_DIR/$config_name-$timestamp-$command_id.meta"
    printf '%s' "$backup_file"
}

command_success_result() {
    message="$1"
    extra="${2:-}"
    if [ -n "$extra" ]; then
        printf '{"ok":true,"code":"ok","message":"%s",%s}' "$(json_escape "$message")" "$extra"
    else
        printf '{"ok":true,"code":"ok","message":"%s"}' "$(json_escape "$message")"
    fi
}

command_failed_result() {
    message="$1"
    code="${2:-}"
    retryable="${3:-false}"
    if [ -z "$code" ]; then
        case "$message" in
            *"not found"*|*"unavailable"*|*"not installed"*) code="resource_unavailable" ;;
            *"invalid"*|*"required"*|*"must "*|*"unsafe"*) code="invalid_request" ;;
            *"timeout"*|*"temporarily"*|*"download failed"*) code="temporary_failure"; retryable=true ;;
            *"backup"*|*"rollback"*) code="safety_check_failed" ;;
            *"permission"*|*"not allowed"*|*"blocked"*) code="operation_blocked" ;;
            *"post-condition"*) code="post_condition_failed" ;;
            *) code="command_failed" ;;
        esac
    fi
    printf '{"ok":false,"code":"%s","error":"%s","error_detail":{"code":"%s","message":"%s","retryable":%s}}' \
        "$(json_escape "$code")" \
        "$(json_escape "$message")" \
        "$(json_escape "$code")" \
        "$(json_escape "$message")" \
        "$retryable"
}
