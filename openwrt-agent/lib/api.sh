api() {
    method="$1"
    path="$2"
    body="${3:-}"
    [ -n "$body" ] || body="{}"
    if [ "$method" = "GET" ]; then
        curl -fsS --connect-timeout 5 --max-time 15 -X "$method" "$(server_url)$path" \
            -H "Authorization: Bearer $(device_token)"
    else
        curl -fsS --connect-timeout 10 --max-time 30 -X "$method" "$(server_url)$path" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $(device_token)" \
            -d "$body"
    fi
}

register_device() {
    hostname="$(json_escape "$(uci -q get system.@system[0].hostname 2>/dev/null || hostname)")"
    model="$(json_escape "$(cat /tmp/sysinfo/model 2>/dev/null || echo OpenWrt)")"
    firmware="$(json_escape "$(openwrt_firmware_description)")"
    name="$(json_escape "$(cfg name)")"
    body="{\"hostname\":\"$hostname\",\"model\":\"$model\",\"firmware\":\"$firmware\",\"name\":\"$name\",\"device_token\":\"$(json_escape "$(device_token)")\"}"
    response="$(curl -fsS -X POST "$(server_url)/api/v1/agent/register" -H "Content-Type: application/json" -d "$body")"
    printf '%s' "$response" >/tmp/wrtmonitor-register-response
    id="$(json_get_string /tmp/wrtmonitor-register-response '@.device_id')"
    rm -f /tmp/wrtmonitor-register-response
    [ -n "$id" ] || return 1
    uci set "$CONFIG.device_id=$id"
    uci commit wrtmonitor
}

poll_commands() {
    agent_enabled || return 0
    [ -n "$(device_id)" ] || register_device
    require_json_tool || return 1
    commands="$(api GET /api/v1/agent/commands)"
    printf '%s' "$commands" >/tmp/wrtmonitor-commands
    index=0
    while true; do
        command_id="$(json_get_string /tmp/wrtmonitor-commands "@[$index].id")"
        command_type="$(json_get_string /tmp/wrtmonitor-commands "@[$index].type")"
        command_payload="$(json_get_object /tmp/wrtmonitor-commands "@[$index].payload")"
        [ -n "$command_id" ] || break
        [ -n "$command_payload" ] || command_payload="{}"
        if api POST "/api/v1/agent/commands/$command_id/result" '{"status":"running","result":{}}' >/dev/null; then
            execute_command "$command_id" "$command_type" "$command_payload"
        else
            log_notice "failed to acknowledge command $command_id"
        fi
        index=$((index + 1))
    done
    rm -f /tmp/wrtmonitor-commands
}

daemon() {
    agent_enabled || exit 0
    next_update_check=0
    while true; do
        now="$(date +%s 2>/dev/null || echo 0)"
        if [ "$now" -ge "$next_update_check" ]; then
            check_for_update "scheduled" 0 0 || true
            if [ "$PENDING_AGENT_EXEC" = "1" ]; then
                handoff_to_updated_agent
            fi
            next_update_check=$((now + $(update_interval_seconds)))
        fi
        telemetry || log_notice "telemetry failed"
        poll_commands || log_notice "command polling failed"
        sleep "$(telemetry_interval_seconds)"
    done
}

debug() {
    load_status
    printf 'server_url=%s\n' "$(server_url)"
    printf 'device_id=%s\n' "$(device_id)"
    printf 'device_token=%s\n' "$(masked_token)"
    printf 'interval=%s\n' "$(telemetry_interval_seconds)"
    printf 'auto_update=%s\n' "$AUTO_UPDATE_STATUS"
    printf 'agent_version=%s\n' "$CURRENT_VERSION"
    printf 'available_version=%s\n' "$AVAILABLE_VERSION"
    printf 'last_update_status=%s\n' "$LAST_UPDATE_STATUS"
    printf 'last_update_error=%s\n' "$LAST_UPDATE_ERROR"
}

debug_telemetry() {
    payload="$(telemetry_payload)"
    printf 'telemetry_bytes=%s\n' "$(printf '%s' "$payload" | wc -c | tr -d ' ')"
    printf '%s\n' "$payload"
}

debug_api() {
    endpoint="$(server_url)/api/v1/agent/commands"
    response_file="/tmp/wrtmonitor-debug-api-$$"
    status="$(curl -sS --connect-timeout 5 --max-time 15 -o "$response_file" -w '%{http_code}' -X GET "$endpoint" -H "Authorization: Bearer $(device_token)" || true)"
    printf 'http_status=%s\n' "$status"
    printf 'response='
    cat "$response_file" 2>/dev/null || true
    printf '\n'
    rm -f "$response_file"
}

support_bundle() {
    public_mode="${1:-}"
    bundle_dir="/tmp/wrtmonitor-agent-support-$$"
    archive="/tmp/wrtmonitor-agent-support.tar.gz"
    mkdir -p "$bundle_dir"
    printf 'agent_version=%s\n' "$AGENT_VERSION" >"$bundle_dir/version.txt"
    cat /etc/openwrt_release 2>/dev/null >>"$bundle_dir/version.txt" || true
    uci show wrtmonitor 2>/dev/null | sed -E "s/(device_token=).*/\1'***'/; s/(password=).*/\1'***'/; s/(key=).*/\1'***'/" >"$bundle_dir/wrtmonitor.conf" || true
    [ ! -r "$STATUS_FILE" ] || cp "$STATUS_FILE" "$bundle_dir/update-status.env"
    logread 2>/dev/null | grep -i wrtmonitor | tail -100 | sed -E 's/(Authorization: Bearer )[A-Za-z0-9._-]+/\1***/g; s/(device_token=).*/\1***/g; s/(password=).*/\1***/g; s/(key=).*/\1***/g' >"$bundle_dir/wrtmonitor.log" || true
    debug_api >"$bundle_dir/debug-api.txt" 2>&1 || true
    debug_telemetry >"$bundle_dir/debug-telemetry.txt" 2>&1 || true
    sed -i -E 's/(Authorization: Bearer )[A-Za-z0-9._-]+/\1***/g; s/(device_token["=: ]+)[^", ]+/\1***/g; s/(password["=: ]+)[^", ]+/\1***/g; s/(key["=: ]+)[^", ]+/\1***/g' "$bundle_dir"/debug-*.txt 2>/dev/null || true
    if [ "$public_mode" = "--public" ]; then
        sed -i -E 's/[0-9a-fA-F-]{16,}/***DEVICE***/g; s#https?://[^ /]+#https://***SERVER***#g' "$bundle_dir"/* 2>/dev/null || true
    fi
    tar -czf "$archive" -C "$bundle_dir" .
    rm -rf "$bundle_dir"
    printf '%s\n' "$archive"
}

main() {
    case "${1:-}" in
        capabilities)
            if [ "${2:-}" = "--json" ]; then
                capabilities_json
                printf '\n'
            else
                capabilities_json
                printf '\n'
            fi
            ;;
        check-server) check_server_json; printf '\n' ;;
        check-dns) check_dns_json; printf '\n' ;;
        check-route) check_route_json; printf '\n' ;;
        check-wifi) check_wifi_json; printf '\n' ;;
        check-dependencies) dependencies_json; printf '\n' ;;
        diagnostics)
            diagnostics_json
            printf '\n'
            ;;
        list-config-backups) list_config_backups ;;
        register) register_device ;;
        update) shift; manual_update "$@" ;;
        rollback) manual_rollback ;;
        update-status)
            if [ "${2:-}" = "--json" ]; then
                update_status_json
                printf '\n'
            else
                update_status_text
            fi
            ;;
        send-now) acquire_lock || exit 0; telemetry; poll_commands ;;
        daemon) acquire_lock || exit 0; daemon ;;
        debug) debug ;;
        debug-telemetry) debug_telemetry ;;
        debug-api) debug_api ;;
        version) printf '%s\n' "$AGENT_VERSION" ;;
        support-bundle) support_bundle "${2:-}" ;;
        *)
            echo "Usage: wrtmonitor-agent capabilities [--json]|check-server|check-dns|check-route|check-wifi|check-dependencies|diagnostics [--json]|list-config-backups|register|send-now|daemon|update [--force] [--allow-downgrade]|rollback|update-status [--json]|debug|debug-telemetry|debug-api|version|support-bundle [--public]" >&2
            exit 1
            ;;
    esac
}
