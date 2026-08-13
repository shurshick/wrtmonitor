#!/bin/sh
set -eu
PATH="/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export PATH

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
AGENT_INSTALL_PATH="/usr/bin/wrtmonitor-agent"
INIT_INSTALL_PATH="/etc/init.d/wrtmonitor"
LIB_INSTALL_DIR="/usr/lib/wrtmonitor"
RELEASES_DIR="$LIB_INSTALL_DIR/releases"

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

package_manager_name() {
    if command -v apk >/dev/null 2>&1; then
        printf 'apk'
    elif command -v opkg >/dev/null 2>&1; then
        printf 'opkg'
    else
        return 1
    fi
}

refresh_package_indexes() {
    case "$(package_manager_name)" in
        apk) apk update ;;
        opkg) opkg update ;;
    esac
}

install_packages() {
    case "$(package_manager_name)" in
        apk) apk add "$@" ;;
        opkg) opkg install "$@" ;;
    esac
}

ensure_dependencies() {
    add_missing_package curl curl
    add_missing_package jsonfilter jsonfilter
    add_missing_package uci uci
    add_missing_package ubus ubus
    add_missing_package sha256sum coreutils-sha256sum
    add_missing_package base64 coreutils-base64
    add_missing_package openssl openssl-util
    if ! has_ca_bundle; then
        missing_packages="$missing_packages ca-bundle"
    fi
    if [ -n "$missing_packages" ]; then
        if ! package_manager_name >/dev/null 2>&1; then
            echo "Cannot install dependencies: apk or opkg is not available" >&2
            exit 1
        fi
        echo "Installing agent dependencies:$missing_packages"
        refresh_package_indexes
        # shellcheck disable=SC2086
        install_packages $missing_packages
    fi
    for command_name in curl jsonfilter uci ubus sha256sum base64 openssl; do
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
    package_manager_name >/dev/null 2>&1 || return 0
    refresh_package_indexes >/dev/null 2>&1 || true
    if ! command -v wg >/dev/null 2>&1; then
        echo "Installing optional VPN dependency: wireguard-tools"
        install_packages wireguard-tools >/dev/null 2>&1 || echo "Optional package wireguard-tools is unavailable; WireGuard management is disabled" >&2
    fi
    if [ ! -x /etc/init.d/openvpn ]; then
        echo "Installing optional VPN dependency: openvpn-openssl"
        install_packages openvpn-openssl >/dev/null 2>&1 || echo "Optional package openvpn-openssl is unavailable; OpenVPN management is disabled" >&2
    fi
    if [ ! -x /etc/init.d/pbr ]; then
        echo "Installing optional VPN dependency: pbr"
        install_packages pbr >/dev/null 2>&1 || echo "Optional package pbr is unavailable; policy routing is disabled" >&2
    fi
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

write_update_public_key() {
    cat >"$1" <<'EOF'
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAbXo+FQit+3CFcc6Dwnww2gtXN5wOMlwxDdx/UIDth4A=
-----END PUBLIC KEY-----
EOF
}

write_update_rsa_public_key() {
    cat >"$1" <<'EOF'
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw0Oa78bfYDUZQgtbeOt+
xLqjGAcJfMUz5n8Qg76kUj8PQO1/0NDy22lyUAfii9DLsTS4zeR0wgwuEAT3wUzB
Ca/EDwuHll/PlGB4OBDNnw8zTb/jPa6KJW+NR0fu1jovEofEP6aDSMb6lIheTIEF
EHfeMfNiSHHZemiQNNBBF8xEcjKQuUP/DuGFnBMFrY0296eWSu3HhDHbCsOxnkLU
n3/349a595GVxwCYU/+sF+qsATv5KigGYkaqxcHEQJxhc4dAp8ZEEXmaROM7lKQ0
yCIhswvVwjyFXTsDcmZVnQCWtPaJusyQV9HKmUaFHQwo/oVp9Y+uxsyzTmNppn67
LwIDAQAB
-----END PUBLIC KEY-----
EOF
}

write_update_legacy_rsa_public_key() {
    cat >"$1" <<'EOF'
-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAnk2nhDg1rLY7XmxMRA81
ahLaHSD+SP3t0vaul5dnE9kKzFAMoOBWTkuhmECLJ+ZXgzHKpZCbC7K0uH1zJ/og
xQDj9ok4z4DIhyXSkvUY4WUe1MMTYpxFa6Ow6E6+ke0oBxUMOHGhOKBm/7QPcTxp
nbTSjxIHlwR2i7iyNDnjZ7xBZpep/b3FTX/O/ha1/5rGHeImd6SVRk8x2RCeCmQj
w7fprDRD//2Ko350oojyinicZmU1tp61RyW78fgrQURQJjm5p8FPEyqjvmWkjLbw
/cWDqGcZXiBsGwPCbxiXL4cYQR27FTjIDu1b30dyt4mJ80XQHuVVMqLHiwPcx1UV
uW9/XV0g6YUzHcJxXFT47R3cOCvU0qiZixxItEFc+3mNZ4fhiOudZOq7H04yZq0E
zgpi4sAWwz2IcbNj4sohxaV9hq8pPgnCzG6PYPRLpl6UmiKeLY6dmKGXFHx+GxcP
gU3H/CMcfRH8Os4zX9nhqWj3aV2wDXHkgABOGHsiNbTXAgMBAAE=
-----END PUBLIC KEY-----
EOF
}

verify_ed25519_manifest_signature() {
    tree="$1"
    public_key="$tree/update-public-key.pem"
    signature="$tree/SHA256SUMS.sig.bin"
    [ -r "$tree/SHA256SUMS.sig" ] || return 1
    write_update_public_key "$public_key"
    base64 -d <"$tree/SHA256SUMS.sig" >"$signature" 2>/dev/null || return 1
    openssl pkeyutl -verify -pubin -inkey "$public_key" -rawin \
        -in "$tree/SHA256SUMS.txt" -sigfile "$signature" >/dev/null 2>&1
}

verify_rsa_manifest_signature() {
    tree="$1"
    public_key="$tree/update-rsa-public-key.pem"
    signature="$tree/SHA256SUMS.rsa.sig.bin"
    [ -r "$tree/SHA256SUMS.rsa.sig" ] || return 1
    base64 -d <"$tree/SHA256SUMS.rsa.sig" >"$signature" 2>/dev/null || return 1
    write_update_rsa_public_key "$public_key"
    openssl dgst -sha256 -verify "$public_key" -signature "$signature" \
        "$tree/SHA256SUMS.txt" >/dev/null 2>&1 && return 0
    write_update_legacy_rsa_public_key "$public_key"
    openssl dgst -sha256 -verify "$public_key" -signature "$signature" \
        "$tree/SHA256SUMS.txt" >/dev/null 2>&1
}

verify_manifest_signature() {
    tree="$1"
    verify_ed25519_manifest_signature "$tree" && return 0
    verify_rsa_manifest_signature "$tree"
}

validate_tree() {
    tree="$1"
    manifest="$tree/openwrt-agent-files.txt"
    sums="$tree/SHA256SUMS.txt"
    [ -r "$manifest" ] || { echo "Manifest not found: $manifest" >&2; exit 1; }
    [ -r "$sums" ] || { echo "SHA256SUMS not found: $sums" >&2; exit 1; }
    if [ ! -r "$tree/SHA256SUMS.sig" ] && [ ! -r "$tree/SHA256SUMS.rsa.sig" ]; then
        echo "SHA256SUMS signature not found" >&2
        exit 1
    fi
    verify_manifest_signature "$tree" || { echo "Invalid update signature" >&2; exit 1; }
    for filename in $(manifest_entries "$manifest"); do
        case "$filename" in SHA256SUMS.txt|SHA256SUMS.sig|SHA256SUMS.rsa.sig) continue ;; esac
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
        download_file "$base/SHA256SUMS.sig" "$WORK_DIR/SHA256SUMS.sig" || rm -f "$WORK_DIR/SHA256SUMS.sig"
        download_file "$base/SHA256SUMS.rsa.sig" "$WORK_DIR/SHA256SUMS.rsa.sig" || rm -f "$WORK_DIR/SHA256SUMS.rsa.sig"
        for filename in $(manifest_entries "$WORK_DIR/openwrt-agent-files.txt"); do
            case "$filename" in SHA256SUMS.txt|SHA256SUMS.sig|SHA256SUMS.rsa.sig) continue ;; esac
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

resolve_device_identity() {
    hostname_value="$(json_escape "$(uci -q get system.@system[0].hostname 2>/dev/null || hostname)")"
    model_value="$(json_escape "$(cat /tmp/sysinfo/model 2>/dev/null || echo OpenWrt)")"
    firmware_value="$(json_escape "$(openwrt_firmware_description)")"
    name_value="$(json_escape "$NAME")"
    register_body="{\"device_token\":\"$(json_escape "$DEVICE_TOKEN")\",\"hostname\":\"$hostname_value\",\"model\":\"$model_value\",\"firmware\":\"$firmware_value\",\"name\":\"$name_value\"}"
    register_response="$(post_json /api/v1/agent/register "$register_body")"
    DEVICE_ID="$(printf '%s' "$register_response" | sed -n 's/.*"device_id":"\([^"]*\)".*/\1/p')"
    [ -n "$DEVICE_ID" ] || { echo "Failed to resolve device identity from token" >&2; exit 1; }
}

directory_is_writable() {
    directory="$1"
    probe="$directory/.wrtmonitor-install-test.$$"
    [ -d "$directory" ] || mkdir -p "$directory" || return 1
    : >"$probe" 2>/dev/null || return 1
    rm -f "$probe"
}

installation_preflight() {
    for directory in "$(dirname "$AGENT_INSTALL_PATH")" "$(dirname "$INIT_INSTALL_PATH")" "$LIB_INSTALL_DIR" /etc/config; do
        directory_is_writable "$directory" || {
            echo "Installation stopped: filesystem is read-only or not writable: $directory" >&2
            exit 1
        }
    done
    required_kb="$(du -sk "$WORK_DIR" 2>/dev/null | awk 'NR == 1 { print $1 }')"
    available_kb="$(df -Pk "$LIB_INSTALL_DIR" 2>/dev/null | awk 'NR == 2 { print $4 }')"
    case "$required_kb:$available_kb" in
        *[!0-9:]*|:*|*:) echo "Installation stopped: cannot determine free disk space" >&2; exit 1 ;;
    esac
    required_kb=$((required_kb * 2 + 512))
    [ "$available_kb" -ge "$required_kb" ] || {
        echo "Installation stopped: not enough free space (${available_kb} KB available, ${required_kb} KB required)" >&2
        exit 1
    }
}

system_preflight() {
    for directory in /usr/bin /usr/lib /etc/init.d /etc/config; do
        directory_is_writable "$directory" || {
            echo "Installation stopped before package changes: filesystem is read-only or not writable: $directory" >&2
            exit 1
        }
    done
}

atomic_pointer() {
    generation_id="$1"
    pointer_path="$2"
    printf '%s\n' "$generation_id" >"$pointer_path.new"
    mv -f "$pointer_path.new" "$pointer_path"
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

write_default_config() {
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
    option update_interval_hours '1'
    option update_channel 'stable'
    option allow_downgrade '0'
    option recovery_mode '0'
    option staged_firmware_sha256 ''
    option staged_firmware_preserve '1'
EOF
}

set_config_default() {
    option="$1"
    value="$2"
    [ -n "$(uci -q get "wrtmonitor.main.$option" 2>/dev/null || true)" ] \
        || uci set "wrtmonitor.main.$option=$value"
}

write_connection_config() {
    if [ ! -r /etc/config/wrtmonitor ] || [ "$KEEP_CONFIG" != "1" ]; then
        write_default_config
    fi

    # A reinstall can provision a new database row while an old UCI file is
    # still present. Connection identity must always follow the new provision.
    uci set "wrtmonitor.main=wrtmonitor"
    uci set "wrtmonitor.main.enabled=1"
    uci set "wrtmonitor.main.server_url=$SERVER_URL"
    uci set "wrtmonitor.main.update_source=$DOWNLOAD_BASE"
    uci set "wrtmonitor.main.device_token=$DEVICE_TOKEN"
    uci set "wrtmonitor.main.device_id=$DEVICE_ID"
    uci set "wrtmonitor.main.name=$NAME"
    set_config_default interval 60
    set_config_default auto_update 1
    set_config_default update_interval_hours 1
    set_config_default update_channel stable
    set_config_default allow_downgrade 0
    set_config_default recovery_mode 0
    set_config_default staged_firmware_sha256 ''
    set_config_default staged_firmware_preserve 1
    uci commit wrtmonitor
}

stop_existing_agent() {
    /etc/init.d/wrtmonitor stop 2>/dev/null || true
    old_pids="$(pidof wrtmonitor-agent 2>/dev/null || true)"
    for old_pid in $old_pids; do
        kill "$old_pid" 2>/dev/null || true
    done
    wait_count=0
    while [ -n "$(pidof wrtmonitor-agent 2>/dev/null || true)" ] && [ "$wait_count" -lt 5 ]; do
        wait_count=$((wait_count + 1))
        sleep 1
    done
    for old_pid in $(pidof wrtmonitor-agent 2>/dev/null || true); do
        kill -9 "$old_pid" 2>/dev/null || true
    done
    rm -rf /tmp/wrtmonitor-agent.lock
    rm -f /tmp/wrtmonitor-agent-update.lock
}

install_payload() {
    version="$(tr -d '\r\n' <"$WORK_DIR/agent-version.txt")"
    digest="$(sha256sum "$WORK_DIR/SHA256SUMS.txt" | awk '{print substr($1, 1, 12)}')"
    generation="$RELEASES_DIR/$version-$digest"
    generation_tmp="$RELEASES_DIR/.$version-$digest.$$"
    rm -rf "$generation_tmp"
    mkdir -p "$generation_tmp"
    cp "$WORK_DIR"/lib/*.sh "$generation_tmp"/
    chmod 0755 "$generation_tmp"/*.sh
    printf '%s\n' "$version" >"$generation_tmp/agent-version.txt"
    if [ -d "$generation" ]; then
        rm -rf "$generation_tmp"
    else
        mv "$generation_tmp" "$generation"
    fi
    generation_id="$(basename "$generation")"
    atomic_pointer "$generation_id" "$RELEASES_DIR/version-$version"

    cp "$WORK_DIR/wrtmonitor.init" "$INIT_INSTALL_PATH.new"
    chmod 0755 "$INIT_INSTALL_PATH.new"
    cp "$WORK_DIR/wrtmonitor-agent" "$AGENT_INSTALL_PATH.new"
    chmod 0755 "$AGENT_INSTALL_PATH.new"
    atomic_pointer "$generation_id" "$RELEASES_DIR/current"
    mv "$INIT_INSTALL_PATH.new" "$INIT_INSTALL_PATH"
    mv "$AGENT_INSTALL_PATH.new" "$AGENT_INSTALL_PATH"
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

system_preflight
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
else
    resolve_device_identity
fi

prepare_work_dir
installation_preflight

if [ "$CLEAN_MODE" = "1" ]; then
    clean_install_targets
fi

stop_existing_agent
install_payload
write_connection_config

if ! /usr/bin/wrtmonitor-agent ensure-dependencies; then
    echo "Agent installation stopped: required runtime dependencies are unavailable" >&2
    exit 1
fi

if ! /usr/bin/wrtmonitor-agent send-now; then
    echo "Agent installation failed: server rejected initial telemetry or command polling" >&2
    /etc/init.d/wrtmonitor enable
    /etc/init.d/wrtmonitor start || true
    exit 1
fi
echo "Initial telemetry accepted by WrtMonitor server"

/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor start
sleep 1
if ! /etc/init.d/wrtmonitor status >/dev/null 2>&1; then
    echo "Agent installation failed: wrtmonitor service did not start" >&2
    exit 1
fi
echo "wrtmonitor agent $(/usr/bin/wrtmonitor-agent version) installed and running"
