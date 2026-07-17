backup_available() {
    [ -r "$BACKUP_DIR/wrtmonitor-agent.previous" ] \
        && [ -r "$BACKUP_DIR/wrtmonitor.init.previous" ] \
        && [ -d "$BACKUP_DIR/lib.previous" ]
}

load_status() {
    CURRENT_VERSION="$AGENT_VERSION"
    AVAILABLE_VERSION=""
    AUTO_UPDATE_STATUS="$(cfg auto_update)"
    LAST_UPDATE_CHECK=""
    LAST_UPDATE_STATUS=""
    LAST_UPDATE_ERROR=""
    LAST_SUCCESSFUL_UPDATE=""
    BACKUP_AVAILABLE_FLAG="0"
    UPDATE_SOURCE_VALUE="$(update_source)"
    if [ -r "$STATUS_FILE" ]; then
        # shellcheck disable=SC1090
        . "$STATUS_FILE"
    fi
    if backup_available; then
        BACKUP_AVAILABLE_FLAG="1"
    else
        BACKUP_AVAILABLE_FLAG="0"
    fi
    CURRENT_VERSION="$AGENT_VERSION"
    AUTO_UPDATE_STATUS="enabled"
    if ! auto_update_enabled; then
        AUTO_UPDATE_STATUS="disabled"
    fi
    UPDATE_SOURCE_VALUE="$(update_source)"
}

write_status() {
    status_value="$1"
    error_value="$2"
    available_value="$3"
    check_value="$4"
    success_value="$5"
    ensure_state_dirs
    backup_value="0"
    if backup_available; then
        backup_value="1"
    fi
    {
        printf "CURRENT_VERSION='%s'\n" "$(shell_escape_single "$AGENT_VERSION")"
        printf "AVAILABLE_VERSION='%s'\n" "$(shell_escape_single "$available_value")"
        printf "AUTO_UPDATE_STATUS='%s'\n" "$(shell_escape_single "$(auto_update_enabled && printf enabled || printf disabled)")"
        printf "LAST_UPDATE_CHECK='%s'\n" "$(shell_escape_single "$check_value")"
        printf "LAST_UPDATE_STATUS='%s'\n" "$(shell_escape_single "$status_value")"
        printf "LAST_UPDATE_ERROR='%s'\n" "$(shell_escape_single "$error_value")"
        printf "LAST_SUCCESSFUL_UPDATE='%s'\n" "$(shell_escape_single "$success_value")"
        printf "BACKUP_AVAILABLE_FLAG='%s'\n" "$(shell_escape_single "$backup_value")"
        printf "UPDATE_SOURCE_VALUE='%s'\n" "$(shell_escape_single "$(update_source)")"
    } >"$STATUS_FILE"
}

remember_update_result() {
    status_value="$1"
    error_value="$2"
    available_value="$3"
    load_status
    last_success="$LAST_SUCCESSFUL_UPDATE"
    if [ "$status_value" = "success" ]; then
        last_success="$(iso_now)"
    fi
    write_status "$status_value" "$error_value" "$available_value" "$(iso_now)" "$last_success"
}

update_status_text() {
    load_status
    printf 'current_version=%s\n' "$CURRENT_VERSION"
    printf 'available_version=%s\n' "$AVAILABLE_VERSION"
    printf 'auto_update=%s\n' "$AUTO_UPDATE_STATUS"
    printf 'last_update_check=%s\n' "$LAST_UPDATE_CHECK"
    printf 'last_update_status=%s\n' "$LAST_UPDATE_STATUS"
    printf 'last_update_error=%s\n' "$LAST_UPDATE_ERROR"
    printf 'last_successful_update=%s\n' "$LAST_SUCCESSFUL_UPDATE"
    printf 'backup_available=%s\n' "$BACKUP_AVAILABLE_FLAG"
    printf 'update_source=%s\n' "$UPDATE_SOURCE_VALUE"
}

update_status_json() {
    load_status
    printf '{"current_version":"%s","available_version":"%s","auto_update":"%s","last_update_check":"%s","last_update_status":"%s","last_update_error":"%s","last_successful_update":"%s","backup_available":%s,"update_source":"%s"}' \
        "$(json_escape "$CURRENT_VERSION")" \
        "$(json_escape "$AVAILABLE_VERSION")" \
        "$(json_escape "$AUTO_UPDATE_STATUS")" \
        "$(json_escape "$LAST_UPDATE_CHECK")" \
        "$(json_escape "$LAST_UPDATE_STATUS")" \
        "$(json_escape "$LAST_UPDATE_ERROR")" \
        "$(json_escape "$LAST_SUCCESSFUL_UPDATE")" \
        "$( [ "$BACKUP_AVAILABLE_FLAG" = "1" ] && printf true || printf false )" \
        "$(json_escape "$UPDATE_SOURCE_VALUE")"
}

agent_status_json() {
    load_status
    printf '{"version":"%s","status":"running","platform":"openwrt","capabilities_version":%s,"auto_update_enabled":%s,"telemetry_interval_seconds":%s,"last_update_check":"%s","last_update_status":"%s","last_update_error":"%s","last_successful_update":"%s","rollback_available":%s,"update_source":"%s","available_version":"%s","capabilities":%s,"capability_details":%s}' \
        "$(json_escape "$CURRENT_VERSION")" \
        "$CAPABILITIES_VERSION" \
        "$( [ "$AUTO_UPDATE_STATUS" = "enabled" ] && printf true || printf false )" \
        "$(telemetry_interval_seconds)" \
        "$(json_escape "$LAST_UPDATE_CHECK")" \
        "$(json_escape "$LAST_UPDATE_STATUS")" \
        "$(json_escape "$LAST_UPDATE_ERROR")" \
        "$(json_escape "$LAST_SUCCESSFUL_UPDATE")" \
        "$( [ "$BACKUP_AVAILABLE_FLAG" = "1" ] && printf true || printf false )" \
        "$(json_escape "$UPDATE_SOURCE_VALUE")" \
        "$(json_escape "$AVAILABLE_VERSION")" \
        "$(agent_capabilities_json)" \
        "$(agent_capability_details_json)"
}
