# Shared globals consumed by other sourced modules.
# shellcheck disable=SC2034
RUN_LOCK_DIR="/tmp/wrtmonitor-agent.lock"
UPDATE_LOCK_FILE="/tmp/wrtmonitor-agent-update.lock"
UPDATE_LOCK_STALE_SECONDS="1800"
STATUS_DIR="/etc/wrtmonitor"
BACKUP_DIR="$STATUS_DIR/backup"
CONFIG_BACKUP_DIR="$STATUS_DIR/config-backups"
STATUS_FILE="$STATUS_DIR/update-status.env"
STATE_FILE="$STATUS_DIR/agent-state.env"
LIB_INSTALL_DIR="/usr/lib/wrtmonitor"
PENDING_AGENT_EXEC=0

cfg() {
    uci -q get "$CONFIG.$1" 2>/dev/null || true
}

telemetry_interval_seconds() {
    value="$(cfg interval)"
    case "$value" in
        ""|*[!0-9]*) value="60" ;;
    esac
    if [ "$value" -lt 5 ]; then
        value="5"
    fi
    printf '%s' "$value"
}

server_url() {
    cfg server_url | sed 's#/$##'
}

device_token() {
    cfg device_token
}

device_id() {
    cfg device_id
}

agent_enabled() {
    [ "$(cfg enabled)" = "1" ]
}

auto_update_enabled() {
    [ "$(cfg auto_update)" != "0" ]
}

allow_downgrade_enabled() {
    [ "$(cfg allow_downgrade)" = "1" ]
}

update_source() {
    configured="$(cfg update_source)"
    if [ -n "$configured" ]; then
        printf '%s' "$configured" | sed 's#/$##'
    else
        printf '%s/downloads/openwrt' "$(server_url)"
    fi
}

log_notice() {
    logger -t wrtmonitor "$1"
}

iso_now() {
    date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo ""
}

json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

shell_escape_single() {
    printf '%s' "$1" | sed "s/'/'\"'\"'/g"
}

ensure_state_dirs() {
    mkdir -p "$STATUS_DIR" "$BACKUP_DIR" "$CONFIG_BACKUP_DIR"
}

acquire_lock() {
    if ! mkdir "$RUN_LOCK_DIR" 2>/dev/null; then
        log_notice "agent is already running"
        return 1
    fi
    trap 'rmdir "$RUN_LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
}

release_run_lock() {
    rmdir "$RUN_LOCK_DIR" 2>/dev/null || true
    trap - EXIT INT TERM
}

require_json_tool() {
    if command -v jsonfilter >/dev/null 2>&1; then
        return 0
    fi
    log_notice "jsonfilter is required for API response parsing"
    return 1
}

json_get_string() {
    file="$1"
    expr="$2"
    require_json_tool || return 1
    jsonfilter -i "$file" -e "$expr" 2>/dev/null | head -n 1
}

json_get_number() {
    json_get_string "$1" "$2"
}

json_get_bool() {
    json_get_string "$1" "$2"
}

json_get_object() {
    file="$1"
    expr="$2"
    require_json_tool || return 1
    jsonfilter -i "$file" -e "$expr" 2>/dev/null | head -n 1
}

json_object_or_raw() {
    raw="$(tr '\n' ' ' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    case "$raw" in
        \{*\}) printf '%s' "$raw" ;;
        *) printf '{"raw":"%s"}' "$(json_escape "$raw")" ;;
    esac
}

json_command_or_fallback() {
    fallback="$1"
    shift
    tmp="/tmp/wrtmonitor-json-$$"
    if "$@" >"$tmp" 2>/dev/null; then
        json_object_or_raw <"$tmp"
    else
        printf '%s' "$fallback"
    fi
    rm -f "$tmp"
}

ubus_json() {
    object="$1"
    method="$2"
    params="${3:-{}}"
    if command -v ubus >/dev/null 2>&1; then
        json_command_or_fallback '{"available":false}' ubus call "$object" "$method" "$params"
    else
        printf '{"available":false}'
    fi
}

masked_token() {
    token="$(device_token)"
    length="${#token}"
    if [ "$length" -le 10 ]; then
        printf '%s' 'configured'
    else
        printf '%s...%s' "$(printf '%s' "$token" | cut -c1-5)" "$(printf '%s' "$token" | tail -c 5)"
    fi
}

openwrt_firmware_description() {
    if [ -r /etc/openwrt_release ]; then
        value="$(sed -n "s/^DISTRIB_DESCRIPTION='\(.*\)'/\1/p" /etc/openwrt_release | head -n 1)"
        if [ -n "$value" ]; then
            printf '%s' "$value"
            return
        fi
    fi
    printf 'OpenWrt'
}
