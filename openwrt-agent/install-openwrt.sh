#!/bin/sh
set -eu

SERVER_URL=""
DOWNLOAD_BASE=""
DEVICE_TOKEN=""
DEVICE_ID=""
NAME=""
ADMIN_USERNAME=""
ADMIN_PASSWORD=""
CLEAN_MODE="0"
REMOVE_CONFIG="0"
WORK_DIR=""
KEEP_CONFIG="1"

missing_packages=""

add_missing_package() {
    command_name="$1"
    package_name="$2"
    if ! command -v "$command_name" >/dev/null 2>&1; then
        missing_packages="$missing_packages $package_name"
    fi
}

has_ca_bundle() {
    [ -r /etc/ssl/certs/ca-certificates.crt ] \
        || [ -r /etc/ssl/cert.pem ] \
        || [ -r /etc/ssl/certs/ca-bundle.crt ]
}

ensure_dependencies() {
    add_missing_package curl curl
    add_missing_package jsonfilter jsonfilter
    add_missing_package uci uci
    add_missing_package ubus ubus
    add_missing_package sha256sum coreutils-sha256sum
    if ! has_ca_bundle; then
        missing_packages="$missing_packages ca-bundle"
    fi
    if [ -n "$missing_packages" ]; then
        if ! command -v opkg >/dev/null 2>&1; then
            echo "Cannot install dependencies: opkg is not available" >&2
            exit 1
        fi
        echo "Installing agent dependencies:$missing_packages"
        opkg update
        # shellcheck disable=SC2086
        opkg install $missing_packages
    fi
    for command_name in curl jsonfilter uci ubus sha256sum; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            echo "Required dependency is unavailable after installation: $command_name" >&2
            exit 1
        fi
    done
    if ! has_ca_bundle; then
        echo "Required dependency is unavailable after installation: ca-bundle" >&2
        exit 1
    fi
}

ensure_optional_dependencies() {
    command -v nlbw >/dev/null 2>&1 && return 0
    command -v opkg >/dev/null 2>&1 || return 0
    echo "Installing optional per-client traffic dependency: nlbwmon"
    opkg install nlbwmon >/dev/null 2>&1 || echo "Optional package nlbwmon is unavailable; per-client traffic counters are disabled" >&2
}

json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

prompt_value() {
    label="$1"
    current="$2"
    required="$3"
    while [ -z "$current" ]; do
        printf '%s: ' "$label" >&2
        read -r current
        if [ "$required" != "1" ]; then
            break
        fi
    done
    printf '%s' "$current"
}

prompt_secret() {
    label="$1"
    current="$2"
    if [ -n "$current" ]; then
        printf '%s' "$current"
        return
    fi
    printf '%s: ' "$label" >&2
    if command -v stty >/dev/null 2>&1; then
        stty -echo
        read -r current
        stty echo
        printf '\n' >&2
    else
        read -r current
    fi
    printf '%s' "$current"
}

download_file() {
    url="$1"
    destination="$2"
    curl -fsS --connect-timeout 10 --max-time 60 -o "$destination" "$url"
}

manifest_entries() {
    manifest="$1"
    sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$manifest"
}

verify_checksum() {
    sums_file="$1"
    file_path="$2"
    filename="$3"
    expected="$(awk -v name="$filename" '$2 == name {print $1}' "$sums_file" | head -n 1)"
    [ -n "$expected" ] || return 1
    actual="$(sha256sum "$file_path" | awk '{print $1}')"
    [ "$actual" = "$expected" ]
}

validate_tree() {
    tree="$1"
    manifest="$tree/openwrt-agent-files.txt"
    sums="$tree/SHA256SUMS.txt"
    [ -r "$manifest" ] || { echo "Manifest not found: $manifest" >&2; exit 1; }
    [ -r "$sums" ] || { echo "SHA256SUMS not found: $sums" >&2; exit 1; }
    for filename in $(manifest_entries "$manifest"); do
        [ "$filename" = "SHA256SUMS.txt" ] && continue
        [ -r "$tree/$filename" ] || { echo "Missing file in payload: $filename" >&2; exit 1; }
        verify_checksum "$sums" "$tree/$filename" "$filename" || { echo "Checksum mismatch: $filename" >&2; exit 1; }
    done
    sh -n "$tree/wrtmonitor-agent"
    sh -n "$tree/wrtmonitor.init"
    sh -n "$tree/install-openwrt.sh"
    for path in "$tree"/lib/*.sh; do
        [ -e "$path" ] || { echo "No library files found" >&2; exit 1; }
        sh -n "$path"
    done
    version_file="$(tr -d '\r\n' <"$tree/agent-version.txt")"
    version_script="$(sed -n 's/^AGENT_VERSION="\([^"]*\)".*/\1/p' "$tree/wrtmonitor-agent" | head -n 1)"
    [ -n "$version_file" ] || { echo "agent-version.txt is empty" >&2; exit 1; }
    [ "$version_file" = "$version_script" ] || { echo "agent-version.txt does not match AGENT_VERSION" >&2; exit 1; }
}

prepare_work_dir() {
    SCRIPT_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
    if [ -n "$DOWNLOAD_BASE" ]; then
        WORK_DIR="/tmp/wrtmonitor-install.$$"
        mkdir -p "$WORK_DIR/lib"
        base="$(printf '%s' "$DOWNLOAD_BASE" | sed 's#/$##')"
        download_file "$base/openwrt-agent-files.txt" "$WORK_DIR/openwrt-agent-files.txt"
        download_file "$base/SHA256SUMS.txt" "$WORK_DIR/SHA256SUMS.txt"
        for filename in $(manifest_entries "$WORK_DIR/openwrt-agent-files.txt"); do
            [ "$filename" = "SHA256SUMS.txt" ] && continue
            target="$WORK_DIR/$filename"
            mkdir -p "$(dirname "$target")"
            download_file "$base/$filename" "$target"
        done
    else
        WORK_DIR="$SCRIPT_DIR"
    fi
    validate_tree "$WORK_DIR"
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

post_json() {
    path="$1"
    body="$2"
    auth="${3:-}"
    if [ -n "$auth" ]; then
        curl -fsS -X POST "$SERVER_URL$path" -H "Content-Type: application/json" -H "Authorization: Bearer $auth" -d "$body"
    else
        curl -fsS -X POST "$SERVER_URL$path" -H "Content-Type: application/json" -d "$body"
    fi
}

clean_install_targets() {
    /etc/init.d/wrtmonitor stop 2>/dev/null || true
    rm -f /usr/bin/wrtmonitor-agent
    rm -rf /usr/lib/wrtmonitor
    rm -f /etc/init.d/wrtmonitor
    if [ "$REMOVE_CONFIG" = "1" ]; then
        rm -f /etc/config/wrtmonitor
    fi
}

write_config_if_needed() {
    if [ -r /etc/config/wrtmonitor ] && [ "$KEEP_CONFIG" = "1" ]; then
        return
    fi
    cat > /etc/config/wrtmonitor <<EOF
config wrtmonitor 'main'
    option enabled '1'
    option server_url '$SERVER_URL'
    option update_source '${DOWNLOAD_BASE:-$SERVER_URL/downloads/openwrt}'
    option device_token '$DEVICE_TOKEN'
    option device_id '$DEVICE_ID'
    option name '$NAME'
    option interval '60'
    option auto_update '1'
    option update_interval_hours '6'
    option update_channel 'stable'
    option allow_downgrade '0'
EOF
}

install_payload() {
    cp "$WORK_DIR/wrtmonitor-agent" /usr/bin/wrtmonitor-agent
    chmod 0755 /usr/bin/wrtmonitor-agent
    cp "$WORK_DIR/wrtmonitor.init" /etc/init.d/wrtmonitor
    chmod 0755 /etc/init.d/wrtmonitor
    mkdir -p /usr/lib/wrtmonitor
    rm -f /usr/lib/wrtmonitor/*.sh
    cp "$WORK_DIR"/lib/*.sh /usr/lib/wrtmonitor/
    chmod 0755 /usr/lib/wrtmonitor/*.sh
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --server) SERVER_URL="$2"; shift 2 ;;
        --download-base) DOWNLOAD_BASE="$2"; shift 2 ;;
        --admin-user) ADMIN_USERNAME="$2"; shift 2 ;;
        --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
        --token) DEVICE_TOKEN="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --clean) CLEAN_MODE="1"; shift ;;
        --remove-config) REMOVE_CONFIG="1"; KEEP_CONFIG="0"; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

ensure_dependencies
ensure_optional_dependencies

if [ -z "$SERVER_URL" ] && [ -n "$DOWNLOAD_BASE" ]; then
    SERVER_URL="$(printf '%s' "$DOWNLOAD_BASE" | sed 's#/downloads/openwrt$##; s#/$##')"
fi
if [ -z "$SERVER_URL" ]; then
    SERVER_URL="$(prompt_value 'WrtMonitor server URL, example https://monitor.example.ru' "$SERVER_URL" 1)"
fi
SERVER_URL="$(printf '%s' "$SERVER_URL" | sed 's#/$##')"

if [ -z "$DOWNLOAD_BASE" ]; then
    DOWNLOAD_BASE="$SERVER_URL/downloads/openwrt"
fi

if [ -z "$DEVICE_TOKEN" ]; then
    ADMIN_USERNAME="$(prompt_value 'Administrator username' "$ADMIN_USERNAME" 1)"
    ADMIN_PASSWORD="$(prompt_secret 'Administrator password' "$ADMIN_PASSWORD")"
fi

if [ -z "$NAME" ]; then
    NAME="$(prompt_value 'Router name, optional' "$NAME" 0)"
fi

if [ -z "$DEVICE_TOKEN" ]; then
    hostname_value="$(json_escape "$(uci -q get system.@system[0].hostname 2>/dev/null || hostname)")"
    model_value="$(json_escape "$(cat /tmp/sysinfo/model 2>/dev/null || echo OpenWrt)")"
    firmware_value="$(json_escape "$(openwrt_firmware_description)")"
    name_value="$(json_escape "$NAME")"
    login_body="{\"username\":\"$(json_escape "$ADMIN_USERNAME")\",\"password\":\"$(json_escape "$ADMIN_PASSWORD")\"}"
    login_response="$(post_json /api/v1/auth/login "$login_body")"
    admin_token="$(printf '%s' "$login_response" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
    [ -n "$admin_token" ] || { echo "Failed to login as administrator" >&2; exit 1; }

    provision_body="{\"hostname\":\"$hostname_value\",\"model\":\"$model_value\",\"firmware\":\"$firmware_value\",\"name\":\"$name_value\"}"
    provision_response="$(post_json /api/v1/devices/provision "$provision_body" "$admin_token")"
    DEVICE_ID="$(printf '%s' "$provision_response" | sed -n 's/.*"device_id":"\([^"]*\)".*/\1/p')"
    DEVICE_TOKEN="$(printf '%s' "$provision_response" | sed -n 's/.*"device_token":"\([^"]*\)".*/\1/p')"
    [ -n "$DEVICE_ID" ] || { echo "Failed to provision device" >&2; exit 1; }
    [ -n "$DEVICE_TOKEN" ] || { echo "Failed to receive device token" >&2; exit 1; }
fi

prepare_work_dir

if [ "$CLEAN_MODE" = "1" ]; then
    clean_install_targets
fi

install_payload
write_config_if_needed

/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor restart
echo "wrtmonitor agent installed"
