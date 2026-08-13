DEFAULT_UPDATE_INTERVAL_HOURS="1"

parse_version_parts() {
    normalized="$(printf '%s' "$1" | sed 's/^v//; s/+.*$//')"
    base="${normalized%%-*}"
    prerelease=""
    [ "$base" = "$normalized" ] || prerelease="${normalized#*-}"
    old_ifs="$IFS"
    IFS=.
    # shellcheck disable=SC2086
    set -- $base
    IFS="$old_ifs"
    [ "$#" -eq 3 ] || return 1
    major="$1"
    minor="$2"
    patch="$3"
    for part in "$major" "$minor" "$patch"; do
        case "$part" in ""|*[!0-9]*) return 1 ;; esac
    done
    case "$prerelease" in
        "") stable_rank=1; rc_number=0 ;;
        rc[0-9]*)
            rc_number="${prerelease#rc}"
            case "$rc_number" in ""|*[!0-9]*) return 1 ;; esac
            stable_rank=0
            ;;
        *) return 1 ;;
    esac
    printf '%s %s %s %s %s' "$major" "$minor" "$patch" "$stable_rank" "$rc_number"
}

compare_versions() {
    left="$(parse_version_parts "$1")"
    right="$(parse_version_parts "$2")"
    if [ -z "$left" ] || [ -z "$right" ]; then
        awk -v left_raw="$1" -v right_raw="$2" 'BEGIN {
            if (left_raw == right_raw) {
                print 0
            } else if (left_raw > right_raw) {
                print 1
            } else {
                print -1
            }
        }'
        return
    fi
    # shellcheck disable=SC2086
    set -- $left
    left_major="$1"
    left_minor="$2"
    left_patch="$3"
    left_stable="$4"
    left_rc="$5"
    # shellcheck disable=SC2086
    set -- $right
    right_major="$1"
    right_minor="$2"
    right_patch="$3"
    right_stable="$4"
    right_rc="$5"
    if [ "$left_major" -gt "$right_major" ]; then printf '1'; return; fi
    if [ "$left_major" -lt "$right_major" ]; then printf '%s' '-1'; return; fi
    if [ "$left_minor" -gt "$right_minor" ]; then printf '1'; return; fi
    if [ "$left_minor" -lt "$right_minor" ]; then printf '%s' '-1'; return; fi
    if [ "$left_patch" -gt "$right_patch" ]; then printf '1'; return; fi
    if [ "$left_patch" -lt "$right_patch" ]; then printf '%s' '-1'; return; fi
    if [ "$left_stable" -gt "$right_stable" ]; then printf '1'; return; fi
    if [ "$left_stable" -lt "$right_stable" ]; then printf '%s' '-1'; return; fi
    if [ "$left_rc" -gt "$right_rc" ]; then printf '1'; return; fi
    if [ "$left_rc" -lt "$right_rc" ]; then printf '%s' '-1'; return; fi
    printf '0'
}

update_interval_seconds() {
    hours="$(cfg update_interval_hours)"
    case "$hours" in
        ""|*[!0-9]*) hours="$DEFAULT_UPDATE_INTERVAL_HOURS" ;;
    esac
    # Six hours was the historical default. Migrate that value without
    # overriding deliberate custom schedules.
    if [ "$hours" = "6" ]; then
        hours="$DEFAULT_UPDATE_INTERVAL_HOURS"
    fi
    if [ "$hours" -le 0 ]; then
        hours="$DEFAULT_UPDATE_INTERVAL_HOURS"
    fi
    printf '%s' $((hours * 3600))
}

download_file() {
    url="$1"
    destination="$2"
    curl -fsS --connect-timeout 10 --max-time 60 -o "$destination" "$url"
}

checksum_for() {
    sha256sum "$1" | awk '{print $1}'
}

checksum_expected_for() {
    sums_file="$1"
    filename="$2"
    awk -v name="$filename" '$2 == name {print $1}' "$sums_file" | head -n 1
}

verify_checksum() {
    sums_file="$1"
    file_path="$2"
    filename="$3"
    expected="$(checksum_expected_for "$sums_file" "$filename")"
    if [ -z "$expected" ]; then
        return 1
    fi
    actual="$(checksum_for "$file_path")"
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
    tmp_dir="$1"
    public_key="$tmp_dir/update-public-key.pem"
    signature="$tmp_dir/SHA256SUMS.sig.bin"
    [ -r "$tmp_dir/SHA256SUMS.sig" ] || return 1
    write_update_public_key "$public_key"
    base64 -d <"$tmp_dir/SHA256SUMS.sig" >"$signature" 2>/dev/null || return 1
    openssl pkeyutl -verify -pubin -inkey "$public_key" -rawin \
        -in "$tmp_dir/SHA256SUMS.txt" -sigfile "$signature" >/dev/null 2>&1
}

verify_rsa_manifest_signature() {
    tmp_dir="$1"
    public_key="$tmp_dir/update-rsa-public-key.pem"
    signature="$tmp_dir/SHA256SUMS.rsa.sig.bin"
    [ -r "$tmp_dir/SHA256SUMS.rsa.sig" ] || return 1
    base64 -d <"$tmp_dir/SHA256SUMS.rsa.sig" >"$signature" 2>/dev/null || return 1
    write_update_rsa_public_key "$public_key"
    openssl dgst -sha256 -verify "$public_key" -signature "$signature" \
        "$tmp_dir/SHA256SUMS.txt" >/dev/null 2>&1 && return 0
    write_update_legacy_rsa_public_key "$public_key"
    openssl dgst -sha256 -verify "$public_key" -signature "$signature" \
        "$tmp_dir/SHA256SUMS.txt" >/dev/null 2>&1
}

verify_manifest_signature() {
    tmp_dir="$1"
    verify_ed25519_manifest_signature "$tmp_dir" && return 0
    verify_rsa_manifest_signature "$tmp_dir"
}

remote_version_from_tmp() {
    tr -d '\r\n' <"$1/agent-version.txt"
}

prepare_backup() {
    new_version="$1"
    active_lib_dir="$LIB_INSTALL_DIR"
    current_release="$(release_directory_from_pointer "$RELEASES_DIR/current" 2>/dev/null || true)"
    if [ -r "$current_release/agent-version.txt" ] \
        && [ "$(tr -d '\r\n' <"$current_release/agent-version.txt")" = "$AGENT_VERSION" ]; then
        active_lib_dir="$current_release"
    fi
    ensure_state_dirs
    rm -rf "$BACKUP_DIR/lib.previous"
    mkdir -p "$BACKUP_DIR/lib.previous" || return 1
    cp "$AGENT_INSTALL_PATH" "$BACKUP_DIR/wrtmonitor-agent.previous" || return 1
    cp "$INIT_INSTALL_PATH" "$BACKUP_DIR/wrtmonitor.init.previous" || return 1
    if [ -d "$active_lib_dir" ]; then
        cp "$active_lib_dir"/*.sh "$BACKUP_DIR/lib.previous/" 2>/dev/null || return 1
    fi
    [ -r "$BACKUP_DIR/lib.previous/common.sh" ] || return 1
    printf '%s\n' "$AGENT_VERSION" >"$BACKUP_DIR/VERSION.previous" || return 1
    {
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'previous_version=%s\n' "$AGENT_VERSION"
        printf 'new_version=%s\n' "$new_version"
        printf 'active_lib_dir=%s\n' "$active_lib_dir"
        printf 'reason=pre-update-backup\n'
    } >"$BACKUP_DIR/backup-info.txt" || return 1
}

restore_backup_files() {
    backup_available || return 1
    sh -n "$BACKUP_DIR/wrtmonitor-agent.previous"
    sh -n "$BACKUP_DIR/wrtmonitor.init.previous"
    for path in "$BACKUP_DIR"/lib.previous/*.sh; do
        [ -e "$path" ] || return 1
        sh -n "$path"
    done
    previous_version="$(tr -d '\r\n' <"$BACKUP_DIR/VERSION.previous")"
    rollback_generation="$RELEASES_DIR/${previous_version}-rollback-$(date +%s 2>/dev/null || echo $$)"
    mkdir -p "$rollback_generation"
    cp "$BACKUP_DIR"/lib.previous/*.sh "$rollback_generation"/
    chmod 0755 "$rollback_generation"/*.sh
    printf '%s\n' "$previous_version" >"$rollback_generation/agent-version.txt"

    rollback_generation_id="$(basename "$rollback_generation")"
    atomic_pointer "$rollback_generation_id" "$RELEASES_DIR/version-$previous_version"
    cp "$BACKUP_DIR/wrtmonitor.init.previous" "$INIT_INSTALL_PATH.new"
    chmod 0755 "$INIT_INSTALL_PATH.new"
    cp "$BACKUP_DIR/wrtmonitor-agent.previous" "$AGENT_INSTALL_PATH.new"
    chmod 0755 "$AGENT_INSTALL_PATH.new"

    # Legacy libraries remain a safe fallback for pre-generational entrypoints.
    mkdir -p "$LIB_INSTALL_DIR"
    rm -f "$LIB_INSTALL_DIR"/*.sh
    cp "$BACKUP_DIR"/lib.previous/*.sh "$LIB_INSTALL_DIR"/
    chmod 0755 "$LIB_INSTALL_DIR"/*.sh
    mv "$INIT_INSTALL_PATH.new" "$INIT_INSTALL_PATH"
    mv "$AGENT_INSTALL_PATH.new" "$AGENT_INSTALL_PATH"
    atomic_pointer "$rollback_generation_id" "$RELEASES_DIR/current"
}

manifest_entries() {
    manifest_file="$1"
    sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$manifest_file"
}

directory_is_writable() {
    directory="$1"
    probe="$directory/.wrtmonitor-write-test.$$"
    [ -d "$directory" ] || return 1
    : >"$probe" 2>/dev/null || return 1
    rm -f "$probe"
}

payload_size_kb() {
    du -sk "$1" 2>/dev/null | awk 'NR == 1 { print $1 }'
}

available_space_kb() {
    df -Pk "$1" 2>/dev/null | awk 'NR == 2 { print $4 }'
}

preflight_downloaded_files() {
    tmp_dir="$1"
    INSTALL_PREFLIGHT_ERROR=""
    for directory in "$(dirname "$AGENT_INSTALL_PATH")" "$(dirname "$INIT_INSTALL_PATH")" "$LIB_INSTALL_DIR" "$STATUS_DIR"; do
        if ! directory_is_writable "$directory"; then
            INSTALL_PREFLIGHT_ERROR="filesystem is read-only or not writable: $directory"
            return 1
        fi
    done
    required_kb="$(payload_size_kb "$tmp_dir")"
    available_kb="$(available_space_kb "$LIB_INSTALL_DIR")"
    case "$required_kb:$available_kb" in
        *[!0-9:]*|:*|*:) INSTALL_PREFLIGHT_ERROR="cannot determine free disk space"; return 1 ;;
    esac
    # Staging and rollback keep two complete copies plus filesystem overhead.
    required_kb=$((required_kb * 3 + 512))
    if [ "$available_kb" -lt "$required_kb" ]; then
        INSTALL_PREFLIGHT_ERROR="not enough free space: ${available_kb} KB available, ${required_kb} KB required"
        return 1
    fi
    return 0
}

atomic_pointer() {
    generation_id="$1"
    pointer_path="$2"
    mkdir -p "$(dirname "$pointer_path")"
    printf '%s\n' "$generation_id" >"$pointer_path.new" || return 1
    mv -f "$pointer_path.new" "$pointer_path"
}

release_directory_from_pointer() {
    pointer_path="$1"
    [ -r "$pointer_path" ] || return 1
    generation_id="$(head -n 1 "$pointer_path" 2>/dev/null || true)"
    case "$generation_id" in
        ""|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
    directory="$RELEASES_DIR/$generation_id"
    [ -d "$directory" ] || return 1
    printf '%s' "$directory"
}

manifest_generation_id() {
    version="$1"
    digest="$(sha256sum "$2/SHA256SUMS.txt" | awk '{print substr($1, 1, 12)}')"
    printf '%s-%s' "$version" "$digest"
}

prune_release_generations() {
    keep_current="$(head -n 1 "$RELEASES_DIR/current" 2>/dev/null || true)"
    keep_previous="$(head -n 1 "$RELEASES_DIR/version-$AGENT_VERSION" 2>/dev/null || true)"
    for path in "$RELEASES_DIR"/*; do
        [ -d "$path" ] || continue
        name="$(basename "$path")"
        [ "$name" = "$keep_current" ] && continue
        [ -n "$keep_previous" ] && [ "$name" = "$keep_previous" ] && continue
        rm -rf "$path" 2>/dev/null || true
    done
}

apply_downloaded_files() {
    tmp_dir="$1"
    new_version="$(remote_version_from_tmp "$tmp_dir")"
    generation_id="$(manifest_generation_id "$new_version" "$tmp_dir")"
    generation_tmp="$RELEASES_DIR/.${generation_id}.$$"
    generation="$RELEASES_DIR/$generation_id"
    rm -rf "$generation_tmp"
    mkdir -p "$generation_tmp" || return 1
    for path in "$tmp_dir"/lib/*.sh; do
        [ -e "$path" ] || return 1
        name="$(basename "$path")"
        cp "$path" "$generation_tmp/$name" || return 1
        chmod 0755 "$generation_tmp/$name" || return 1
        sh -n "$generation_tmp/$name" || return 1
    done
    printf '%s\n' "$new_version" >"$generation_tmp/agent-version.txt" || return 1
    if [ -d "$generation" ]; then
        rm -rf "$generation_tmp"
    else
        mv "$generation_tmp" "$generation" || return 1
    fi

    atomic_pointer "$generation_id" "$RELEASES_DIR/version-$new_version" || return 1

    cp "$tmp_dir/wrtmonitor.init" "$INIT_INSTALL_PATH.new" || return 1
    chmod 0755 "$INIT_INSTALL_PATH.new" || return 1
    cp "$tmp_dir/wrtmonitor-agent" "$AGENT_INSTALL_PATH.new" || return 1
    chmod 0755 "$AGENT_INSTALL_PATH.new" || return 1

    # The old entrypoint rejects a current pointer with another version and
    # falls back to its own version alias. The executable is switched last.
    atomic_pointer "$generation_id" "$RELEASES_DIR/current" || return 1
    mv "$INIT_INSTALL_PATH.new" "$INIT_INSTALL_PATH" || return 1
    mv "$AGENT_INSTALL_PATH.new" "$AGENT_INSTALL_PATH" || return 1
}

validate_download_set() {
    tmp_dir="$1"
    manifest="$tmp_dir/openwrt-agent-files.txt"
    sums="$tmp_dir/SHA256SUMS.txt"
    [ -r "$manifest" ] || return 1
    [ -r "$sums" ] || return 1
    if [ ! -r "$tmp_dir/SHA256SUMS.sig" ] && [ ! -r "$tmp_dir/SHA256SUMS.rsa.sig" ]; then
        return 1
    fi
    verify_manifest_signature "$tmp_dir" || return 1

    for filename in $(manifest_entries "$manifest"); do
        case "$filename" in SHA256SUMS.txt|SHA256SUMS.sig|SHA256SUMS.rsa.sig) continue ;; esac
        [ -r "$tmp_dir/$filename" ] || return 1
        verify_checksum "$sums" "$tmp_dir/$filename" "$filename" || return 1
    done

    sh -n "$tmp_dir/wrtmonitor-agent"
    sh -n "$tmp_dir/wrtmonitor.init"
    sh -n "$tmp_dir/install-openwrt.sh"
    for path in "$tmp_dir"/lib/*.sh; do
        [ -e "$path" ] || return 1
        sh -n "$path"
    done

    remote_version="$(remote_version_from_tmp "$tmp_dir")"
    [ -n "$remote_version" ] || return 1
    parsed_version="$(sed -n 's/^AGENT_VERSION="\([^"]*\)".*/\1/p' "$tmp_dir/wrtmonitor-agent" | head -n 1)"
    [ -n "$parsed_version" ] && [ "$parsed_version" = "$remote_version" ]
}

stage_update_downloads() {
    tmp_dir="$1"
    mkdir -p "$tmp_dir/lib"
    base="$(update_source)"
    download_file "$base/openwrt-agent-files.txt" "$tmp_dir/openwrt-agent-files.txt"
    download_file "$base/SHA256SUMS.txt" "$tmp_dir/SHA256SUMS.txt"
    download_file "$base/SHA256SUMS.sig" "$tmp_dir/SHA256SUMS.sig" || rm -f "$tmp_dir/SHA256SUMS.sig"
    download_file "$base/SHA256SUMS.rsa.sig" "$tmp_dir/SHA256SUMS.rsa.sig" || rm -f "$tmp_dir/SHA256SUMS.rsa.sig"
    for filename in $(manifest_entries "$tmp_dir/openwrt-agent-files.txt"); do
        case "$filename" in SHA256SUMS.txt|SHA256SUMS.sig|SHA256SUMS.rsa.sig) continue ;; esac
        target="$tmp_dir/$filename"
        target_dir="$(dirname "$target")"
        mkdir -p "$target_dir"
        download_file "$base/$filename" "$target"
    done
}

verify_installed_agent() {
    expected="$1"
    installed_version="$("$AGENT_INSTALL_PATH" version 2>/dev/null || true)"
    installed_release="$(release_directory_from_pointer "$RELEASES_DIR/current" 2>/dev/null || true)"
    [ -n "$installed_version" ] \
        && [ "$installed_version" = "$expected" ] \
        && [ -r "$installed_release/common.sh" ] \
        && [ "$(tr -d '\r\n' <"$installed_release/agent-version.txt")" = "$expected" ]
}

handoff_to_updated_agent() {
    release_run_lock
    exec /usr/bin/wrtmonitor-agent daemon
}

restart_service_foreground() {
    /etc/init.d/wrtmonitor restart >/dev/null 2>&1
}

perform_rollback() {
    mode="$1"
    reason="${2:-manual rollback}"
    if ! restore_backup_files; then
        remember_update_result "failed" "rollback unavailable" "$(load_status; printf '%s' "$AVAILABLE_VERSION")"
        return 1
    fi
    remember_update_result "rollback" "$reason" "$AGENT_VERSION"
    log_notice "agent rollback completed: $reason"
    PENDING_AGENT_EXEC=1
    if [ "$mode" = "manual" ]; then
        restart_service_foreground || return 1
        PENDING_AGENT_EXEC=0
    fi
    return 0
}

acquire_update_lock() {
    now="$(date +%s 2>/dev/null || echo 0)"
    if [ -r "$UPDATE_LOCK_FILE" ]; then
        old_pid="$(awk -F= '/^pid=/{print $2}' "$UPDATE_LOCK_FILE" 2>/dev/null | head -n 1)"
        old_started="$(awk -F= '/^started=/{print $2}' "$UPDATE_LOCK_FILE" 2>/dev/null | head -n 1)"
        age=$((now - ${old_started:-0}))
        if [ -n "${old_pid:-}" ] && kill -0 "$old_pid" 2>/dev/null && [ "$age" -lt "$UPDATE_LOCK_STALE_SECONDS" ]; then
            remember_update_result "skipped" "Update already running" "$(load_status; printf '%s' "$AVAILABLE_VERSION")"
            log_notice "Update already running"
            return 1
        fi
        rm -f "$UPDATE_LOCK_FILE"
    fi
    {
        printf 'pid=%s\n' "$$"
        printf 'started=%s\n' "$now"
    } >"$UPDATE_LOCK_FILE"
}

release_update_lock() {
    rm -f "$UPDATE_LOCK_FILE"
}

check_for_update() {
    mode="$1"
    force="${2:-0}"
    allow_downgrade="${3:-0}"
    if [ "$mode" = "scheduled" ] && ! auto_update_enabled; then
        return 0
    fi
    acquire_update_lock || return 0
    tmp_dir="/tmp/wrtmonitor-update.$$"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"
    if ! stage_update_downloads "$tmp_dir"; then
        remember_update_result "failed" "download failed" ""
        log_notice "agent update failed: download failed"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    remote_version="$(remote_version_from_tmp "$tmp_dir")"
    if ! validate_download_set "$tmp_dir"; then
        remember_update_result "failed" "checksum or syntax verification failed" "$remote_version"
        log_notice "agent update failed: checksum or syntax verification failed"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    comparison="$(compare_versions "$AGENT_VERSION" "$remote_version")"
    if [ "$comparison" = "0" ] && [ "$force" != "1" ]; then
        remember_update_result "skipped" "" "$remote_version"
        rm -rf "$tmp_dir"
        release_update_lock
        return 0
    fi
    if ! preflight_downloaded_files "$tmp_dir"; then
        error="${INSTALL_PREFLIGHT_ERROR:-installation preflight failed}"
        remember_update_result "failed" "$error" "$remote_version" || true
        log_notice "agent update failed: $error"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if [ "$comparison" = "1" ] && [ "$allow_downgrade" != "1" ] && ! allow_downgrade_enabled; then
        remember_update_result "skipped" "downgrade blocked" "$remote_version"
        log_notice "agent update skipped: downgrade blocked"
        rm -rf "$tmp_dir"
        release_update_lock
        return 0
    fi
    if ! prepare_backup "$remote_version"; then
        remember_update_result "failed" "backup failed" "$remote_version"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if ! apply_downloaded_files "$tmp_dir"; then
        perform_rollback "internal" "install failed" || true
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if ! /usr/bin/wrtmonitor-agent ensure-dependencies; then
        perform_rollback "internal" "required dependency installation failed" || true
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if ! verify_installed_agent "$remote_version"; then
        perform_rollback "internal" "installed agent validation failed" || true
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    remember_update_result "success" "" "$remote_version"
    prune_release_generations
    log_notice "agent updated: $AGENT_VERSION -> $remote_version"
    PENDING_AGENT_EXEC=1
    rm -rf "$tmp_dir"
    release_update_lock
    if [ "$mode" = "manual" ]; then
        if ! restart_service_foreground; then
            perform_rollback "manual" "service restart failed" || true
            return 1
        fi
        # shellcheck disable=SC2034
        PENDING_AGENT_EXEC=0
    fi
    return 0
}

manual_update() {
    force="0"
    allow_downgrade="0"
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --force) force="1" ;;
            --allow-downgrade) allow_downgrade="1" ;;
            *) echo "Unknown update flag: $1" >&2; exit 1 ;;
        esac
        shift
    done
    check_for_update "manual" "$force" "$allow_downgrade"
}

manual_rollback() {
    perform_rollback "manual" "manual rollback"
}
