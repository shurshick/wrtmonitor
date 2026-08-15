#!/bin/sh
set -eu

HARNESS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
AGENT_DIR="$(CDPATH= cd -- "$HARNESS_DIR/../.." && pwd)"
UCI_STATE_FILE="$HARNESS_DIR/uci.state"
CALL_LOG="${TMPDIR:-/tmp}/wrtmonitor-harness-$$.log"
trap 'rm -f "$CALL_LOG"' EXIT INT TERM

. "$AGENT_DIR/lib/common.sh"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

assert_contains() {
    printf '%s' "$1" | grep -F "$2" >/dev/null || fail "expected '$2' in '$1'"
}

uci() {
    if [ "${1:-}" = "-q" ] && [ "${2:-}" = "get" ]; then
        awk -F= -v key="$3" '$1 == key {sub(/^[^=]*=/, ""); print; found=1} END {exit !found}' "$UCI_STATE_FILE"
        return
    fi
    printf 'uci %s\n' "$*" >>"$CALL_LOG"
}

ubus() {
    printf 'ubus %s\n' "$*" >>"$CALL_LOG"
    printf '{"up":true,"pending":false}'
}

fw4() {
    printf 'fw4 %s\n' "$*" >>"$CALL_LOG"
    [ "${1:-}" = "check" ]
}

service_call() {
    printf 'service %s %s\n' "$1" "$2" >>"$CALL_LOG"
}

json_get_number() {
    case "$2" in
        '@.interval_seconds') printf 10 ;;
        '@.start') printf 100 ;;
        '@.limit') printf 150 ;;
        '@.vlan_id') printf 42 ;;
        *) return 1 ;;
    esac
}

json_get_string() {
    case "$2" in
        '@.hostname') printf OpenWrt ;;
        '@.interface') printf '%s' "$(grep -o '"interface":"[^"]*' "$1" | cut -d\" -f4)" ;;
        '@.device') printf br-lan ;;
        '@.section') printf wrtmonitor_vlan_br_lan_42 ;;
        '@.primary_interface') printf wan ;;
        '@.secondary_interface') printf wan2 ;;
        '@.protocol') printf dhcp ;;
        '@.leasetime') printf 12h ;;
        *) return 1 ;;
    esac
}

json_get_bool() {
    case "$2" in
        '@.enabled') printf true ;;
        *) return 1 ;;
    esac
}

CONFIG="wrtmonitor.main"
. "$AGENT_DIR/lib/verification_modes.sh"
. "$AGENT_DIR/lib/verification_runtime.sh"
. "$AGENT_DIR/lib/verification_client.sh"
. "$AGENT_DIR/lib/verification.sh"
. "$AGENT_DIR/lib/command_result.sh"
. "$AGENT_DIR/lib/command_dns_runtime.sh"
. "$AGENT_DIR/lib/command_wifi_runtime.sh"
. "$AGENT_DIR/lib/command_runtime.sh"

verify_command_postcondition agent.set_interval '{"interval_seconds":10}' \
    || fail "agent interval post-condition"
verify_command_postcondition system.set_hostname '{"hostname":"OpenWrt"}' \
    || fail "hostname post-condition"
verify_command_postcondition network.set_wan '{"interface":"wan","protocol":"dhcp"}' \
    || fail "WAN post-condition"
verify_command_postcondition dhcp.set_pool \
    '{"interface":"lan","start":100,"limit":150,"leasetime":"12h"}' \
    || fail "DHCP post-condition"
verify_command_postcondition network.set_vlan \
    '{"section":"wrtmonitor_vlan_br_lan_42","device":"br-lan","vlan_id":42}' \
    || fail "VLAN post-condition"
verify_command_postcondition network.set_multiwan \
    '{"enabled":true,"primary_interface":"wan","secondary_interface":"wan2"}' \
    || fail "Multi-WAN post-condition"
if verify_command_postcondition future.unknown '{}'; then
    fail "unknown commands must fail post-condition verification"
fi

ubus call network.interface.wan status >/dev/null
fw4 check
service_call network reload
assert_contains "$(cat "$CALL_LOG")" "ubus call network.interface.wan status"
assert_contains "$(cat "$CALL_LOG")" "fw4 check"
assert_contains "$(cat "$CALL_LOG")" "service network reload"

error_json="$(command_failed_result 'wifi radio not found')"
assert_contains "$error_json" '"code":"resource_unavailable"'
assert_contains "$error_json" '"retryable":false'

printf 'OpenWrt command harness: PASS\n'
