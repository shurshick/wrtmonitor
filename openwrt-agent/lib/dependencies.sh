required_dependency_specs() {
    cat <<'EOF'
curl|curl
jsonfilter|jsonfilter
uci|uci
ubus|ubus
ip|ip-full
iw|iw
iwinfo|iwinfo
sha256sum|coreutils-sha256sum
base64|coreutils-base64
tar|tar
gzip|gzip
sysupgrade|base-files
nlbw|nlbwmon
ethtool|ethtool
EOF
}

has_ca_bundle() {
    [ -r /etc/ssl/certs/ca-certificates.crt ] \
        || [ -r /etc/ssl/cert.pem ] \
        || [ -r /etc/ssl/certs/ca-bundle.crt ]
}

required_dependency_packages() {
    {
    required_dependency_specs | while IFS='|' read -r command_name package_name; do
        command -v "$command_name" >/dev/null 2>&1 || printf '%s\n' "$package_name"
    done
    has_ca_bundle || printf '%s\n' ca-bundle
    } | awk '!seen[$0]++'
}

ensure_nlbwmon_runtime() {
    nlbwmon_init="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/nlbwmon"
    command -v nlbw >/dev/null 2>&1 || return 1
    [ -x "$nlbwmon_init" ] || return 1

    if ! uci -q get 'nlbwmon.@nlbwmon[0]' >/dev/null 2>&1; then
        uci add nlbwmon nlbwmon >/dev/null 2>&1 || return 1
    fi
    local_networks="$(uci -q get 'nlbwmon.@nlbwmon[0].local_network' 2>/dev/null || true)"
    for local_network in '192.168.0.0/16' '172.16.0.0/12' '10.0.0.0/8' lan; do
        printf '%s\n' "$local_networks" | grep -Fqx "$local_network" \
            || uci add_list "nlbwmon.@nlbwmon[0].local_network=$local_network" >/dev/null 2>&1 \
            || return 1
    done
    uci commit nlbwmon >/dev/null 2>&1 || return 1

    "$nlbwmon_init" enable >/dev/null 2>&1 || return 1
    "$nlbwmon_init" restart >/dev/null 2>&1 \
        || "$nlbwmon_init" start >/dev/null 2>&1 \
        || return 1
    wait_count=0
    while [ "$wait_count" -lt 5 ]; do
        if "$nlbwmon_init" running >/dev/null 2>&1 \
            && nlbw -c csv -g mac -n -q -s ';' >/dev/null 2>&1; then
            return 0
        fi
        wait_count=$((wait_count + 1))
        sleep 1
    done
    return 1
}

nlbwmon_runtime_status() {
    nlbwmon_init="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/nlbwmon"
    if ! command -v nlbw >/dev/null 2>&1; then
        printf 'not_installed'
    elif [ ! -x "$nlbwmon_init" ]; then
        printf 'service_missing'
    elif ! "$nlbwmon_init" running >/dev/null 2>&1; then
        printf 'service_stopped'
    elif ! nlbw -c csv -g mac -n -q -s ';' >/dev/null 2>&1; then
        printf 'query_failed'
    else
        printf 'ready'
    fi
}

dependencies_healthy() {
    required_dependency_specs | while IFS='|' read -r command_name package_name; do
        command -v "$command_name" >/dev/null 2>&1 || exit 1
    done || return 1
    has_ca_bundle || return 1
    [ "$(nlbwmon_runtime_status)" = ready ]
}

ensure_agent_dependencies() {
    missing="$(required_dependency_packages)"
    if [ -n "$missing" ]; then
        package_manager_name >/dev/null 2>&1 || {
            echo "Cannot install agent dependencies: apk or opkg is unavailable" >&2
            return 1
        }
        echo "Installing required WrtMonitor dependencies: $(printf '%s' "$missing" | tr '\n' ' ')"
        package_refresh_indexes >/dev/null 2>&1 || return 1
        printf '%s\n' "$missing" | while IFS= read -r package_name; do
            [ -n "$package_name" ] || continue
            package_apply install "$package_name" >/dev/null 2>&1 || exit 1
        done || return 1
    fi

    ensure_nlbwmon_runtime || {
        echo "nlbwmon is installed but its service is not running" >&2
        return 1
    }
    dependencies_healthy
}

dependency_manifest_json() {
    items=""
    required_dependency_specs | while IFS='|' read -r command_name package_name; do
        available=false
        command -v "$command_name" >/dev/null 2>&1 && available=true
        [ -n "$items" ] && items="$items,"
        items="$items{\"command\":\"$(json_escape "$command_name")\",\"package\":\"$(json_escape "$package_name")\",\"available\":$available}"
        printf '%s' "$items" >"/tmp/wrtmonitor-dependencies-$$"
    done
    items="$(cat "/tmp/wrtmonitor-dependencies-$$" 2>/dev/null || true)"
    rm -f "/tmp/wrtmonitor-dependencies-$$"
    nlbw_running=false
    nlbwmon_init="${WRTMONITOR_SYSTEM_ROOT:-}/etc/init.d/nlbwmon"
    [ -x "$nlbwmon_init" ] && "$nlbwmon_init" running >/dev/null 2>&1 && nlbw_running=true
    printf '{"required":[%s],"ca_bundle":%s,"nlbwmon":{"installed":%s,"running":%s,"status":"%s"}}' \
        "$items" "$(has_ca_bundle && printf true || printf false)" \
        "$(command -v nlbw >/dev/null 2>&1 && printf true || printf false)" "$nlbw_running" \
        "$(nlbwmon_runtime_status)"
}
