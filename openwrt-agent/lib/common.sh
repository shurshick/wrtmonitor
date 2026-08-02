# Shared globals consumed by other sourced modules.
# shellcheck disable=SC2034
RUN_LOCK_DIR="/tmp/wrtmonitor-agent.lock"
UPDATE_LOCK_FILE="/tmp/wrtmonitor-agent-update.lock"
UPDATE_LOCK_STALE_SECONDS="1800"
STATUS_DIR="${WRTMONITOR_STATUS_DIR:-/etc/wrtmonitor}"
BACKUP_DIR="$STATUS_DIR/backup"
CONFIG_BACKUP_DIR="$STATUS_DIR/config-backups"
CONFIG_TRANSACTION_DIR="$STATUS_DIR/config-transactions"
COMMAND_RESULT_DIR="$STATUS_DIR/command-results"
STATUS_FILE="$STATUS_DIR/update-status.env"
STATE_FILE="$STATUS_DIR/agent-state.env"
LIB_INSTALL_DIR="${WRTMONITOR_LIB_INSTALL_DIR:-/usr/lib/wrtmonitor}"
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

run_with_deadline() {
    wrt_deadline_seconds="$1"
    shift
    case "$wrt_deadline_seconds" in
        ""|*[!0-9]*) wrt_deadline_seconds=20 ;;
    esac
    "$@" &
    wrt_deadline_pid=$!
    wrt_deadline_elapsed=0
    while kill -0 "$wrt_deadline_pid" 2>/dev/null; do
        if [ "$wrt_deadline_elapsed" -ge "$wrt_deadline_seconds" ]; then
            kill -TERM "$wrt_deadline_pid" 2>/dev/null || true
            sleep 1
            kill -KILL "$wrt_deadline_pid" 2>/dev/null || true
            wait "$wrt_deadline_pid" 2>/dev/null || true
            return 124
        fi
        sleep 1
        wrt_deadline_elapsed=$((wrt_deadline_elapsed + 1))
    done
    wait "$wrt_deadline_pid"
}

service_action() {
    wrt_service_name="$1"
    wrt_service_action="$2"
    wrt_service_timeout="${3:-20}"
    wrt_service_script="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/$wrt_service_name"
    [ -x "$wrt_service_script" ] || return 127
    run_with_deadline "$wrt_service_timeout" "$wrt_service_script" "$wrt_service_action"
}

service_restart_if_enabled() {
    wrt_enabled_config="$1"
    wrt_enabled_key="$2"
    wrt_enabled_service="$3"
    [ "$(uci -q get "$wrt_enabled_config.$wrt_enabled_key" 2>/dev/null || true)" = 1 ] \
        || return 0
    service_action "$wrt_enabled_service" restart 20
}

ipv4_netmask_prefix() {
    case "$1" in
        0.0.0.0) printf 0 ;; 128.0.0.0) printf 1 ;; 192.0.0.0) printf 2 ;;
        224.0.0.0) printf 3 ;; 240.0.0.0) printf 4 ;; 248.0.0.0) printf 5 ;;
        252.0.0.0) printf 6 ;; 254.0.0.0) printf 7 ;; 255.0.0.0) printf 8 ;;
        255.128.0.0) printf 9 ;; 255.192.0.0) printf 10 ;; 255.224.0.0) printf 11 ;;
        255.240.0.0) printf 12 ;; 255.248.0.0) printf 13 ;; 255.252.0.0) printf 14 ;;
        255.254.0.0) printf 15 ;; 255.255.0.0) printf 16 ;; 255.255.128.0) printf 17 ;;
        255.255.192.0) printf 18 ;; 255.255.224.0) printf 19 ;; 255.255.240.0) printf 20 ;;
        255.255.248.0) printf 21 ;; 255.255.252.0) printf 22 ;; 255.255.254.0) printf 23 ;;
        255.255.255.0) printf 24 ;; 255.255.255.128) printf 25 ;; 255.255.255.192) printf 26 ;;
        255.255.255.224) printf 27 ;; 255.255.255.240) printf 28 ;; 255.255.255.248) printf 29 ;;
        255.255.255.252) printf 30 ;; 255.255.255.254) printf 31 ;; 255.255.255.255) printf 32 ;;
        /*) printf '%s' "${1#/}" ;;
        *) return 1 ;;
    esac
}

network_interface_cycle() {
    wrt_interface="$1"
    case "$wrt_interface" in ""|*[!A-Za-z0-9_.-]*) return 2 ;; esac
    command -v ifdown >/dev/null 2>&1 && command -v ifup >/dev/null 2>&1 || return 127
    run_with_deadline 20 ifdown "$wrt_interface" >/dev/null 2>&1 || true
    sleep 2
    run_with_deadline 30 ifup "$wrt_interface" >/dev/null 2>&1
}

network_interface_has_ipv4() {
    wrt_interface="$1"
    wrt_expected_ipv4="$2"
    command -v ubus >/dev/null 2>&1 && command -v jsonfilter >/dev/null 2>&1 || return 0
    wrt_runtime_ipv4="$(ubus call "network.interface.$wrt_interface" status 2>/dev/null \
        | jsonfilter -e '@["ipv4-address"][0].address' 2>/dev/null || true)"
    [ "$wrt_runtime_ipv4" = "$wrt_expected_ipv4" ]
}

iso_now() {
    date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo ""
}

json_escape() {
    printf '%s' "$1" | awk 'BEGIN { ORS = "" } {
        if (NR > 1) printf "\\n"
        gsub(/\\/, "\\\\")
        gsub(/"/, "\\\"")
        gsub(/\r/, "\\r")
        gsub(/\t/, "\\t")
        printf "%s", $0
    }'
}

shell_escape_single() {
    printf '%s' "$1" | sed "s/'/'\"'\"'/g"
}

ensure_state_dirs() {
    mkdir -p "$STATUS_DIR" "$BACKUP_DIR" "$CONFIG_BACKUP_DIR" "$CONFIG_TRANSACTION_DIR" "$COMMAND_RESULT_DIR"
}

acquire_lock() {
    if ! mkdir "$RUN_LOCK_DIR" 2>/dev/null; then
        lock_pid="$(cat "$RUN_LOCK_DIR/pid" 2>/dev/null || true)"
        if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
            log_notice "agent is already running"
            return 1
        fi
        rm -rf "$RUN_LOCK_DIR"
        mkdir "$RUN_LOCK_DIR" 2>/dev/null || {
            log_notice "failed to acquire agent lock"
            return 1
        }
    fi
    printf '%s\n' "$$" >"$RUN_LOCK_DIR/pid"
    trap 'release_run_lock; exit 0' INT TERM HUP
}

release_run_lock() {
    rm -rf "$RUN_LOCK_DIR"
    trap - INT TERM HUP
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
